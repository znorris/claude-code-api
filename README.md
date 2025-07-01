# Claude Code API

HTTP server with OpenAI API compatibility that translates requests to Claude Code shell commands.

## Overview

This project provides a local development server that exposes OpenAI-compatible API endpoints while using Claude Code as the backend. Any OpenAI client can communicate with this server without modification.

**Current Status**: Phase 1.6 Complete - OpenAI chat completions with Claude CLI limitations documented

## Features

- ✅ OpenAI `/v1/chat/completions` endpoint (streaming and non-streaming)
- ✅ SQLite session management with conversation history
- ✅ Claude Code subprocess integration with text-only support
- ✅ Comprehensive test suite with CLI limitations analysis
- ✅ System message conversion (API format → CLI workarounds)
- ⚠️ **Limited by Claude CLI JSON input restrictions** (see [Technical Limitations](#technical-limitations))
- 🚧 Anthropic API compatibility (planned)
- 🚧 OpenAI legacy completions endpoint (planned)

## Quick Start

### Prerequisites

- [Claude Code](https://claude.ai/code) installed and configured
- [Conda](https://docs.conda.io/en/latest/) or Python 3.11+

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd claude-code-api
```

2. Create conda environment:
```bash
conda env create -f environment.yml
conda activate claude-code-api
```

3. Run the server:
```bash
cd src
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Usage

The server exposes OpenAI-compatible endpoints at `http://localhost:8000`.

#### Example with curl:
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

#### Example with OpenAI Python client:
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="dummy"  # Not validated in local mode
)

response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)
```

## Development

### Running Tests
```bash
conda activate claude-code-api
python -m pytest tests/ -v
```

### Project Structure
```
src/
├── main.py              # FastAPI app entry point
├── database.py          # SQLite session management  
├── models/openai.py     # OpenAI Pydantic models
├── routes/openai.py     # OpenAI endpoints
├── claude_interface.py  # Claude Code integration
└── utils.py             # Shared utilities

tests/
├── test_models.py       # Model validation tests
├── test_database.py     # Database operation tests
└── test_integration.py  # API endpoint tests
```

### API Endpoints

| Endpoint | Status | Description |
|----------|---------|-------------|
| `GET /` | ✅ | Health check |
| `GET /health` | ✅ | Health status |
| `POST /v1/chat/completions` | ✅ | OpenAI chat completions |
| `POST /v1/completions` | 🚧 | OpenAI legacy completions |
| `POST /v1/messages` | 🚧 | Anthropic messages |

### Configuration

The server uses SQLite for session storage by default. Database file: `sessions.db`

Session expiration: 24 hours (configurable)

## Roadmap

### Phase 2: Enhanced Features (Within CLI Limitations)
- [ ] Enhanced HTTP server logging
- [ ] Enhanced streaming support
- [ ] Performance optimization with persistent CLI processes
- [ ] Error recovery and fallback mechanisms

### Phase 3: Anthropic API Fallback Integration
- [ ] Direct Anthropic API client for advanced features
- [ ] Automatic fallback for image/function call requests
- [ ] `/v1/messages` endpoint with full Messages API support
- [ ] Hybrid routing (CLI for text, API for advanced features)

### Phase 4: Production Features
- [ ] `/v1/completions` legacy endpoint
- [ ] Model parameter mapping
- [ ] API key validation
- [ ] Rate limiting
- [ ] Enhanced session management

## Technical Limitations

**Important**: Claude Code CLI has significant JSON input limitations that restrict this API's capabilities:

### ❌ **Not Supported** (Claude CLI Restrictions)
- **Images/Multi-modal**: No image content blocks supported
- **Function Calling**: No tool use/tool result content blocks  
- **Multiple Content Blocks**: Only single text content per message
- **Assistant/System Roles**: Only user messages accepted
- **Conversation Arrays**: Single message per request only

### ✅ **Supported** 
- **Text-only messages**: Full text processing capabilities
- **Large content**: 15KB+ text handling confirmed
- **Unicode support**: Emoji, international languages
- **Response prefilling**: Via `assistant_prefill` field (CLI-specific)
- **Session management**: Built-in CLI session support

### 🔄 **Workarounds Implemented**
- **System messages**: Converted to text prompts (system field doesn't work)
- **Multi-content**: Text blocks combined automatically
- **Image requests**: Fallback to direct Anthropic API (planned)
- **Function calls**: Fallback to direct Anthropic API (planned)

For complete analysis, see: [Claude CLI vs Anthropic API Comparison](./Claude_CLI_vs_Anthropic_API_Comparison.md)

## Architecture Decision

This project uses a **hybrid approach**:
- **Claude CLI**: For simple text-only conversations (cost optimization)
- **Anthropic API**: For advanced features requiring full Messages API (planned fallback)

The current implementation provides maximum compatibility within Claude CLI constraints while maintaining OpenAI API compatibility.

## Contributing

1. Ensure tests pass: `python -m pytest tests/ -v`
2. Follow existing code style
3. Add tests for new features
4. Run CLI limitation tests: `python comprehensive_cli_verification.py`

## License

Local development use only.
