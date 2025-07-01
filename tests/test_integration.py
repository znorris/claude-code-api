import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from src.main import app

client = TestClient(app)

@pytest.fixture
def mock_claude_result():
    return {
        "type": "result",
        "is_error": False,
        "result": "Hello! How can I help you today?",
        "session_id": "test-session",
        "usage": {
            "input_tokens": 10,
            "output_tokens": 8
        }
    }

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Claude Code API Server"}

@patch('src.claude_interface.claude_interface.complete_chat')
def test_chat_completions_endpoint(mock_complete_chat, mock_claude_result):
    mock_complete_chat.return_value = mock_claude_result
    
    request_data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "user", "content": "Hello"}
        ]
    }
    
    response = client.post("/v1/chat/completions", json=request_data)
    assert response.status_code == 200
    
    data = response.json()
    assert data["object"] == "chat.completion"
    assert data["model"] == "gpt-3.5-turbo"
    assert len(data["choices"]) == 1
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert data["choices"][0]["message"]["content"] == mock_claude_result["result"]
    assert data["usage"]["prompt_tokens"] == 10
    assert data["usage"]["completion_tokens"] == 8

def test_chat_completions_validation_error():
    request_data = {
        "model": "gpt-3.5-turbo",
        "messages": [],  # Empty messages should cause validation error
        "temperature": 3.0  # Invalid temperature
    }
    
    response = client.post("/v1/chat/completions", json=request_data)
    assert response.status_code == 422  # Validation error

@patch('src.claude_interface.claude_interface.stream_chat')
def test_chat_completions_streaming(mock_stream_chat):
    async def mock_stream():
        yield {"type": "assistant", "message": {"content": [{"type": "text", "text": "Hello"}]}}
        yield {"type": "assistant", "message": {"content": [{"type": "text", "text": " there!"}]}}
        yield {"type": "result", "result": "Hello there!"}
    
    mock_stream_chat.return_value = mock_stream()
    
    request_data = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": True
    }
    
    response = client.post("/v1/chat/completions", json=request_data)
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"