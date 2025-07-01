import time
import uuid
import logging
from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import StreamingResponse
from typing import Optional, AsyncIterator
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
        ErrorDetail
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
        ErrorDetail
    )
    from claude_interface import claude_interface
    from database import session_service

router = APIRouter(prefix="/v1")
logger = logging.getLogger(__name__)

@router.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    authorization: Optional[str] = Header(None)
):
    try:
        if request.stream:
            return StreamingResponse(
                stream_chat_completion(request),
                media_type="text/event-stream"
            )
        else:
            return await complete_chat(request)
    
    except Exception as e:
        logger.error(f"Chat completion error: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(
                    message=str(e),
                    type="internal_server_error"
                )
            ).dict()
        )

async def complete_chat(request: ChatCompletionRequest) -> ChatCompletionResponse:
    try:
        result = await claude_interface.complete_chat(request.messages)
        
        response_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"
        created = int(time.time())
        
        response = ChatCompletionResponse(
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
        
        return response
        
    except Exception as e:
        logger.error(f"Claude completion failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(
                    message=f"Claude completion failed: {str(e)}",
                    type="internal_server_error"
                )
            ).dict()
        )

async def stream_chat_completion(request: ChatCompletionRequest) -> AsyncIterator[str]:
    try:
        response_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"
        created = int(time.time())
        
        content_buffer = ""
        
        async for chunk in claude_interface.stream_chat(request.messages):
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
        
    except Exception as e:
        logger.error(f"Streaming failed: {e}")
        error_response = {
            "error": {
                "message": f"Streaming failed: {str(e)}",
                "type": "internal_server_error"
            }
        }
        yield f"data: {json.dumps(error_response)}\n\n"