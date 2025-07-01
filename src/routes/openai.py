import time
import uuid
import logging
from fastapi import APIRouter, HTTPException, Header, Response
from fastapi.responses import StreamingResponse
from typing import Optional, AsyncIterator, List
import json

try:
    from ..models.openai import (
        ChatCompletionRequest, 
        ChatCompletionResponse, 
        ChatCompletionChoice,
        ChatCompletionResponseMessage,
        ChatCompletionStreamResponse,
        ChatCompletionStreamChoice,
        ChatCompletionStreamDelta,
        Usage,
        ErrorResponse,
        ErrorDetail,
        ChatMessage
    )
    from ..claude_interface import claude_interface
    from ..database import session_service
except ImportError:
    from models.openai import (
        ChatCompletionRequest, 
        ChatCompletionResponse, 
        ChatCompletionChoice,
        ChatCompletionResponseMessage,
        ChatCompletionStreamResponse,
        ChatCompletionStreamChoice,
        ChatCompletionStreamDelta,
        Usage,
        ErrorResponse,
        ErrorDetail,
        ChatMessage
    )
    from claude_interface import claude_interface
    from database import session_service

router = APIRouter(prefix="/v1")
logger = logging.getLogger(__name__)

@router.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    response: Response,
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    authorization: Optional[str] = Header(None)
):
    # Session Management
    if x_session_id and await session_service.session_exists(x_session_id):
        session_id = x_session_id
        # Load conversation history
        history = await session_service.get_session_messages(session_id)
        # Combine with new messages
        full_messages = history + request.messages
    else:
        # Create new session
        session_id = await session_service.create_session()
        full_messages = request.messages

    # Set response header
    response.headers["X-Session-ID"] = session_id

    try:
        if request.stream:
            return StreamingResponse(
                stream_chat_completion_with_session(request, full_messages, session_id),
                media_type="text/event-stream",
                headers={"X-Session-ID": session_id}
            )
        else:
            return await complete_chat_with_session(request, full_messages, session_id)
            
    except Exception as e:
        logger.error(f"Chat completion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def complete_chat_with_session(
    request: ChatCompletionRequest, 
    full_messages: List[ChatMessage], 
    session_id: str
) -> ChatCompletionResponse:
    
    result = await claude_interface.complete_chat(full_messages)
    
    # Save new messages to session
    for msg in request.messages:
        await session_service.add_message(session_id, msg.role, msg.content)
    await session_service.add_message(session_id, "assistant", result.get("result", ""))
    
    # Create response (existing logic)
    response_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"
    created = int(time.time())
    
    return ChatCompletionResponse(
        id=response_id,
        created=created,
        model=request.model,
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatCompletionResponseMessage(
                    role="assistant",
                    content=result.get("result", "")
                ),
                finish_reason="stop"
            )
        ],
        usage=Usage(
            prompt_tokens=result.get("usage", {}).get("input_tokens", 0),
            completion_tokens=result.get("usage", {}).get("output_tokens", 0),
            total_tokens=result.get("usage", {}).get("input_tokens", 0) + result.get("usage", {}).get("output_tokens", 0)
        )
    )

async def stream_chat_completion_with_session(
    request: ChatCompletionRequest, 
    full_messages: List[ChatMessage], 
    session_id: str
) -> AsyncIterator[str]:
    
    content_buffer = ""
    
    try:
        response_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"
        created = int(time.time())
        
        async for chunk in claude_interface.stream_chat(full_messages):
            if chunk.get("type") == "assistant":
                message = chunk.get("message", {})
                content = message.get("content", [])
                
                for content_block in content:
                    if content_block.get("type") == "text":
                        text = content_block.get("text", "")
                        if text:
                            content_buffer += text
                            
                            stream_response = ChatCompletionStreamResponse(
                                id=response_id,
                                created=created,
                                model=request.model,
                                choices=[
                                    ChatCompletionStreamChoice(
                                        index=0,
                                        delta=ChatCompletionStreamDelta(content=text)
                                    )
                                ]
                            )
                            
                            yield f"data: {stream_response.model_dump_json()}\n\n"
            
            elif chunk.get("type") == "result":
                final_response = ChatCompletionStreamResponse(
                    id=response_id,
                    created=created,
                    model=request.model,
                    choices=[
                        ChatCompletionStreamChoice(
                            index=0,
                            delta=ChatCompletionStreamDelta(),
                            finish_reason="stop"
                        )
                    ]
                )
                
                yield f"data: {final_response.model_dump_json()}\n\n"
                yield "data: [DONE]\n\n"
                break
        
        # Save to session after streaming completes
        for msg in request.messages:
            await session_service.add_message(session_id, msg.role, msg.content)
        await session_service.add_message(session_id, "assistant", content_buffer)
        
    except Exception as e:
        logger.error(f"Streaming failed: {e}")
        error_response = {
            "error": {
                "message": f"Streaming failed: {str(e)}",
                "type": "internal_server_error"
            }
        }
        yield f"data: {json.dumps(error_response)}\n\n"