import pytest
from pydantic import ValidationError
from src.models.openai import (
    ChatMessage, 
    ChatCompletionRequest, 
    ChatCompletionResponse,
    Role
)

def test_chat_message_creation():
    message = ChatMessage(role=Role.USER, content="Hello")
    assert message.role == Role.USER
    assert message.content == "Hello"
    assert message.name is None

def test_chat_completion_request_basic():
    request = ChatCompletionRequest(
        model="gpt-3.5-turbo",
        messages=[
            ChatMessage(role=Role.USER, content="Hello")
        ]
    )
    assert request.model == "gpt-3.5-turbo"
    assert len(request.messages) == 1
    assert request.stream is False
    assert request.temperature == 1.0

def test_chat_completion_request_validation():
    with pytest.raises(ValidationError):
        ChatCompletionRequest(
            model="gpt-3.5-turbo",
            messages=[],
            temperature=3.0  # Invalid temperature
        )

def test_chat_completion_request_with_stream():
    request = ChatCompletionRequest(
        model="gpt-3.5-turbo",
        messages=[ChatMessage(role=Role.USER, content="Hello")],
        stream=True
    )
    assert request.stream is True