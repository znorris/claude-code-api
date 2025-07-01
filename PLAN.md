# Claude Code API Development Plan - Developer Ready

## 🎯 **Critical Missing Features (Start Here)**

### **Phase 1.5: Must-Fix Issues Before Real Usage**

**Priority Order:**
1. **Session Persistence** (2-3 hours) - Critical for multi-turn conversations
2. **Model Mapping** (1-2 hours) - Required for proper model selection  
3. **JSON Input Format** (1 hour) - Improve Claude Code integration reliability

**Current Status:** Phase 1 MVP works for demos but lacks conversation memory and model selection.

---

## ✅ **What's Working (Phase 1 Complete)**

- [x] FastAPI server with proper startup/shutdown lifecycle
- [x] SQLite database with sessions and messages tables
- [x] OpenAI Pydantic models with full validation
- [x] `/v1/chat/completions` endpoint (streaming + non-streaming)
- [x] Claude Code subprocess integration with JSON output parsing
- [x] Comprehensive test suite (unit + integration + live server tests)
- [x] Conda environment configuration
- [x] Documentation and README

**Working Features:**
- Server runs on `http://localhost:8000`
- Full OpenAI Python client compatibility
- Real-time streaming responses
- Parameter validation and error handling

**🚨 Critical Issues (Phase 1.5 Required):**
- ❌ **No session persistence** - Each call is independent 
- ❌ **Model names ignored** - Always uses default Claude model
- ❌ **Text input only** - Not using Claude Code's JSON input capabilities

---

## 📋 **Task 1: Session Persistence Implementation**

### **Goal:** Enable conversation memory across API calls via session headers

**Session Flow:**
```
Client Request → Check X-Session-ID header → Load/Create Session → 
Merge History + New Messages → Send to Claude → Save Response → Return with Session ID
```

**API Specification:**
- **Request Header:** `X-Session-ID: uuid-string` (optional)
- **Response Header:** `X-Session-ID: uuid-string` (always returned)
- **Session Lifecycle:** 24 hours default, extensible

### **Implementation Steps:**

#### Step 1: Modify `/v1/chat/completions` endpoint
**File:** `src/routes/openai.py`

**Current signature:**
```python
async def chat_completions(
    request: ChatCompletionRequest,
    authorization: Optional[str] = Header(None)
):
```

**New signature:**
```python
async def chat_completions(
    request: ChatCompletionRequest,
    response: Response,
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    authorization: Optional[str] = Header(None)
):
```

#### Step 2: Add session logic to chat_completions function
**Replace the current function body with:**

```python
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
```

#### Step 3: Create session-aware completion functions
**Add these functions to `src/routes/openai.py`:**

```python
async def complete_chat_with_session(
    request: ChatCompletionRequest, 
    full_messages: List[ChatMessage], 
    session_id: str
) -> ChatCompletionResponse:
    
    result = await claude_interface.complete_chat(full_messages, request.model)
    
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
        
        async for chunk in claude_interface.stream_chat(full_messages, request.model):
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
```

#### Step 4: Add required imports
**Add to top of `src/routes/openai.py`:**
```python
from fastapi import APIRouter, HTTPException, Header, Response
```

### **Testing Requirements:**

**Add to `tests/test_live_server.py`:**
```python
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
```

### **Acceptance Criteria:**
- [ ] Multi-turn conversations maintain context
- [ ] Session IDs are returned in all responses
- [ ] Invalid session IDs create new sessions gracefully
- [ ] Both streaming and non-streaming support sessions
- [ ] All existing tests still pass
- [ ] New session tests pass

---

## 📋 **Task 2: Model Mapping Implementation**

### **Goal:** Map OpenAI model names to Claude models and pass correct model to Claude Code

### **Research Results:**
**Claude Code Model Support:**
- **Available models:** `sonnet`, `opus`, `haiku` (aliases)
- **Full names:** `claude-sonnet-4-20250514`, etc.
- **Command syntax:** `claude --model sonnet --print --output-format json "prompt"`

### **Implementation Steps:**

#### Step 1: Create model mapping configuration
**File:** `src/models/config.py` (new file)

```python
from typing import Dict, Optional

# Mapping from OpenAI model names to Claude model names
MODEL_MAPPING: Dict[str, str] = {
    # OpenAI models → Claude models
    "gpt-3.5-turbo": "sonnet",
    "gpt-4": "opus", 
    "gpt-4-turbo": "sonnet",
    "gpt-4o": "sonnet",
    "gpt-4o-mini": "haiku",
    
    # Direct Claude model names (pass through)
    "claude-sonnet": "sonnet",
    "claude-opus": "opus", 
    "claude-haiku": "haiku",
    "sonnet": "sonnet",
    "opus": "opus",
    "haiku": "haiku",
}

DEFAULT_MODEL = "sonnet"

def get_claude_model(requested_model: str) -> str:
    """Convert OpenAI model name to Claude model name."""
    return MODEL_MAPPING.get(requested_model, DEFAULT_MODEL)

def get_supported_models() -> list[str]:
    """Get list of all supported model names."""
    return list(MODEL_MAPPING.keys())
```

#### Step 2: Update Claude Code interface
**File:** `src/claude_interface.py`

**Add import:**
```python
try:
    from .models.config import get_claude_model
except ImportError:
    from models.config import get_claude_model
```

**Modify `_build_command` method:**
```python
def _build_command(self, messages: List[ChatMessage], model: str, stream: bool = False) -> List[str]:
    cmd = [self.claude_command]
    
    # Add model selection
    claude_model = get_claude_model(model)
    cmd.extend(["--model", claude_model])
    
    if stream:
        cmd.extend(["--print", "--output-format", "stream-json", "--verbose"])
    else:
        cmd.extend(["--print", "--output-format", "json"])
    
    prompt = self._format_messages_as_prompt(messages)
    cmd.append(prompt)
    
    return cmd
```

**Update method signatures:**
```python
async def complete_chat(self, messages: List[ChatMessage], model: str = "gpt-3.5-turbo") -> Dict[str, Any]:
    cmd = self._build_command(messages, model, stream=False)
    # ... rest of method unchanged

async def stream_chat(self, messages: List[ChatMessage], model: str = "gpt-3.5-turbo") -> AsyncIterator[Dict[str, Any]]:
    cmd = self._build_command(messages, model, stream=True)
    # ... rest of method unchanged
```

### **Testing Requirements:**

**Add to `tests/test_live_server.py`:**
```python
@pytest.mark.asyncio
async def test_model_mapping(client):
    # Test OpenAI model mapping
    response = await client.post("/v1/chat/completions", json={
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "What model are you?"}]
    })
    assert response.status_code == 200
    data = response.json()
    assert data["model"] == "gpt-4"  # Should return requested model
    
@pytest.mark.asyncio
async def test_claude_model_names(client):
    # Test direct Claude model names
    response = await client.post("/v1/chat/completions", json={
        "model": "claude-sonnet",
        "messages": [{"role": "user", "content": "Hello"}]
    })
    assert response.status_code == 200

@pytest.mark.asyncio  
async def test_unsupported_model_fallback(client):
    response = await client.post("/v1/chat/completions", json={
        "model": "invalid-model-name",
        "messages": [{"role": "user", "content": "Hello"}]
    })
    assert response.status_code == 200
    # Should not fail, uses fallback model
```

### **Acceptance Criteria:**
- [ ] OpenAI model names correctly map to Claude models
- [ ] Direct Claude model names work
- [ ] Invalid model names fall back gracefully
- [ ] Response always returns the originally requested model name
- [ ] All existing tests pass

---

## 🧪 **Validation & Testing Plan**

### **End-to-End Integration Test:**
```python
@pytest.mark.asyncio
async def test_full_integration(client):
    """Test session persistence + model mapping together"""
    
    # Call 1: Introduce with GPT-4
    response1 = await client.post("/v1/chat/completions", json={
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "My name is Alice. Remember this."}]
    })
    session_id = response1.headers["X-Session-ID"]
    
    # Call 2: Switch to GPT-3.5 but maintain session
    response2 = await client.post("/v1/chat/completions",
        headers={"X-Session-ID": session_id},
        json={
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": "What is my name?"}]
        }
    )
    
    # Verify session persistence and model handling
    content = response2.json()["choices"][0]["message"]["content"]
    assert "alice" in content.lower()
    assert response2.json()["model"] == "gpt-3.5-turbo"
```

### **Manual Testing Checklist:**
- [ ] Run server with new changes
- [ ] Test with OpenAI Python client
- [ ] Test with curl commands
- [ ] Verify session headers in browser dev tools
- [ ] Test VS Code extension integration
- [ ] Performance test with multiple concurrent sessions

---

## 📁 **Files to Modify Summary**

| File | Changes | Estimated Time |
|------|---------|----------------|
| `src/routes/openai.py` | Add session management, update signatures | 1.5 hours |
| `src/claude_interface.py` | Add model mapping, update method signatures | 1 hour |
| `src/models/config.py` | New file - model mappings | 0.5 hours |
| `tests/test_live_server.py` | Add session and model tests | 1 hour |
| Update documentation | README, examples | 0.5 hours |

**Total Estimated Time: 4.5 hours**

---

## 🎯 **Success Metrics**

### **Phase 1.5 Complete When:**
- ✅ Multi-turn conversations work with session persistence
- ✅ OpenAI model names properly map to Claude models  
- ✅ All 21+ tests pass (existing + new)
- ✅ Manual VS Code integration test succeeds
- ✅ Performance is acceptable (no significant degradation)

### **Ready for Production Integration:**
After Phase 1.5, the API will be fully ready for:
- VS Code extensions (Continue, Cursor, etc.)
- OpenAI SDK integrations
- Custom applications
- Multi-turn conversations
- Model selection

---

## 🚀 **Quick Start for Developer**

1. **Setup:**
   ```bash
   conda activate claude-code-api
   cd /path/to/claude-code-api
   ```

2. **Start with Task 1 (Session Persistence):**
   - Open `src/routes/openai.py`
   - Follow Step 1-4 implementation guide above
   - Run tests: `python -m pytest tests/test_live_server.py::test_session_persistence -v`

3. **Proceed to Task 2 (Model Mapping):**
   - Create `src/models/config.py`
   - Modify `src/claude_interface.py`
   - Test model switching

4. **Validation:**
   - Run full test suite
   - Start server and test manually
   - Try VS Code integration

---

## 📋 **Integration Readiness Assessment**

### **Current Status (Phase 1):**
- ✅ Basic OpenAI chat completions format
- ✅ Streaming responses  
- ✅ Parameter validation
- ✅ Error handling
- ❌ **No session persistence** - Each call is independent 
- ❌ **Model names ignored** - Always uses default Claude model
- ❌ **No conversation memory** - Cannot maintain context across calls

### **Integration Recommendations:**

**For Simple Testing/Demos:**
- ✅ Can integrate immediately with VS Code extensions
- ✅ Works for single-turn conversations
- ✅ Good for API compatibility testing

**For Production/Real Usage:**
- ⚠️ **Wait for Phase 1.5** - Session persistence is critical
- ⚠️ Model mapping needed for proper model selection
- ⚠️ Multi-turn conversations won't work properly

### **VS Code Integration Impact:**
Most VS Code AI extensions expect conversation context to persist. Without Phase 1.5:
- ❌ Follow-up questions won't remember previous context
- ❌ Code editing sessions lose continuity  
- ❌ Complex multi-step tasks will fail

---

## 📋 **Future Phases (After 1.5 Complete)**

### **Phase 2: OpenAI Feature Completion**
- `/v1/completions` legacy endpoint
- Function calling support  
- Enhanced streaming with heartbeat
- Better error recovery

### **Phase 3: Anthropic API Compatibility**
- `/v1/messages` endpoint
- Multi-content message support
- Anthropic streaming format
- Cross-API session management

### **Phase 4: Production Features**
- Configuration management
- Performance optimizations
- Monitoring and health checks
- Optional security features

---

## 🔧 **Development Workflow Reference**

### **Running the Server:**
```bash
# From project root
PYTHONPATH=/path/to/claude-code-api conda run -n claude-code-api python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### **Testing Commands:**
```bash
# All tests
python -m pytest tests/ -v

# Live server tests (requires running server)
python -m pytest tests/test_live_server.py -v

# Specific test
python -m pytest tests/test_live_server.py::test_session_persistence -v
```

### **Manual API Testing:**
```bash
# Test session persistence
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "My name is Alice"}]
  }'

# Use returned session ID in next call
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Session-ID: <session-id-from-above>" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "What is my name?"}]
  }'
```

---

**📝 Note:** Focus on Phase 1.5 first - it's critical for real-world usage. Future phases can be planned once core functionality is solid.