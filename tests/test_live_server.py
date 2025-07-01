import pytest
import httpx
import json
import asyncio
import pytest_asyncio
from typing import AsyncGenerator

BASE_URL = "http://localhost:8000"

@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        yield client

@pytest.mark.asyncio
async def test_server_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_server_root(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Claude Code API Server"}

@pytest.mark.asyncio
async def test_openapi_docs(client):
    response = await client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

@pytest.mark.asyncio
async def test_chat_completions_live(client):
    request_data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "user", "content": "Say hello in one word"}
        ],
        "max_tokens": 10
    }
    
    response = await client.post("/v1/chat/completions", json=request_data)
    assert response.status_code == 200
    
    data = response.json()
    assert data["object"] == "chat.completion"
    assert data["model"] == "gpt-3.5-turbo"
    assert len(data["choices"]) == 1
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert data["choices"][0]["message"]["content"]
    assert data["usage"]["prompt_tokens"] > 0
    assert data["usage"]["completion_tokens"] > 0

@pytest.mark.asyncio
async def test_chat_completions_streaming_live(client):
    request_data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "user", "content": "Count to 3"}
        ],
        "stream": True
    }
    
    async with client.stream("POST", "/v1/chat/completions", json=request_data) as response:
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        
        chunks = []
        async for chunk in response.aiter_text():
            if chunk.strip() and chunk.startswith("data: "):
                data_part = chunk[6:].strip()
                if data_part != "[DONE]":
                    try:
                        chunk_data = json.loads(data_part)
                        chunks.append(chunk_data)
                    except json.JSONDecodeError:
                        continue
        
        assert len(chunks) > 0
        first_chunk = chunks[0]
        assert first_chunk["object"] == "chat.completion.chunk"
        assert first_chunk["model"] == "gpt-3.5-turbo"

@pytest.mark.asyncio
async def test_chat_completions_validation_error_live(client):
    request_data = {
        "model": "gpt-3.5-turbo",
        "messages": [],
        "temperature": 3.0
    }
    
    response = await client.post("/v1/chat/completions", json=request_data)
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_conversation_with_context(client):
    messages = [
        {"role": "user", "content": "My name is Alice"},
        {"role": "assistant", "content": "Hello Alice! Nice to meet you."},
        {"role": "user", "content": "What's my name?"}
    ]
    
    request_data = {
        "model": "gpt-3.5-turbo",
        "messages": messages,
        "max_tokens": 20
    }
    
    response = await client.post("/v1/chat/completions", json=request_data)
    assert response.status_code == 200
    
    data = response.json()
    assert data["choices"][0]["message"]["content"]

@pytest.mark.asyncio
async def test_different_parameters(client):
    request_data = {
        "model": "claude-sonnet",
        "messages": [{"role": "user", "content": "Hello"}],
        "temperature": 0.5,
        "max_tokens": 50,
        "top_p": 0.9
    }
    
    response = await client.post("/v1/chat/completions", json=request_data)
    assert response.status_code == 200
    
    data = response.json()
    assert data["model"] == "claude-sonnet"
    assert data["choices"][0]["message"]["content"]

@pytest.mark.asyncio
async def test_session_persistence(client):
    # First call - create session
    response1 = await client.post("/v1/chat/completions", json={
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": "My name is Alice"}]
    })
    assert response1.status_code == 200
    session_id = response1.headers.get("X-Session-ID")
    assert session_id is not None
    
    # Second call - use session
    response2 = await client.post("/v1/chat/completions", 
        headers={"X-Session-ID": session_id},
        json={
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": "What is my name?"}]
        }
    )
    assert response2.status_code == 200
    assert response2.headers.get("X-Session-ID") == session_id
    
    # Verify response shows awareness of previous context
    data = response2.json()
    content = data["choices"][0]["message"]["content"].lower()
    assert "alice" in content

@pytest.mark.asyncio
async def test_session_creation_without_header(client):
    response = await client.post("/v1/chat/completions", json={
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": "Hello"}]
    })
    assert response.status_code == 200
    assert "X-Session-ID" in response.headers

@pytest.mark.asyncio
async def test_invalid_session_id(client):
    response = await client.post("/v1/chat/completions",
        headers={"X-Session-ID": "invalid-uuid"},
        json={
            "model": "gpt-3.5-turbo", 
            "messages": [{"role": "user", "content": "Hello"}]
        }
    )
    assert response.status_code == 200
    # Should create new session if invalid ID provided
    new_session_id = response.headers.get("X-Session-ID")
    assert new_session_id != "invalid-uuid"