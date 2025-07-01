from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union, Literal
from enum import Enum

class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"

class ContentText(BaseModel):
    type: Literal["text"] = "text"
    text: str

class ContentImageUrl(BaseModel):
    type: Literal["image_url"] = "image_url"
    image_url: Dict[str, Any]  # Contains "url" and optional "detail"

ContentItem = Union[ContentText, ContentImageUrl]

class ChatMessage(BaseModel):
    role: Role
    content: Union[str, List[ContentItem]]
    name: Optional[str] = None

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    max_tokens: Optional[int] = None
    temperature: Optional[float] = Field(default=1.0, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)
    n: Optional[int] = Field(default=1, ge=1)
    stream: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None
    presence_penalty: Optional[float] = Field(default=0.0, ge=-2.0, le=2.0)
    frequency_penalty: Optional[float] = Field(default=0.0, ge=-2.0, le=2.0)
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None

class ChatCompletionResponseMessage(BaseModel):
    role: Role
    content: str

class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatCompletionResponseMessage
    finish_reason: Optional[Literal["stop", "length", "content_filter"]] = None

class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: Usage

class ChatCompletionStreamDelta(BaseModel):
    role: Optional[Role] = None
    content: Optional[str] = None

class ChatCompletionStreamChoice(BaseModel):
    index: int
    delta: ChatCompletionStreamDelta
    finish_reason: Optional[Literal["stop", "length", "content_filter"]] = None

class ChatCompletionStreamResponse(BaseModel):
    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: List[ChatCompletionStreamChoice]

class ErrorDetail(BaseModel):
    message: str
    type: str
    param: Optional[str] = None
    code: Optional[str] = None

class ErrorResponse(BaseModel):
    error: ErrorDetail