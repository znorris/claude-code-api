# Claude Code API

HTTP server with OpenAI API compatibility that translates requests to Claude Code shell commands.

## Overview

This project provides a local development server that exposes OpenAI-compatible API endpoints while using Claude Code as the backend. Any OpenAI client can communicate with this server without modification.

**Current Status**: Phase 1 MVP - OpenAI chat completions support

## Features

- ✅ OpenAI `/v1/chat/completions` endpoint (streaming and non-streaming)
- ✅ SQLite session management with conversation history
- ✅ Claude Code subprocess integration  
- ✅ Comprehensive test suite
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

### Phase 2: OpenAI Feature Completion
- [ ] `/v1/completions` legacy endpoint
- [ ] Enhanced streaming support
- [ ] Function calling support

### Phase 3: Anthropic API Support  
- [ ] `/v1/messages` endpoint
- [ ] Multi-content message format
- [ ] Anthropic streaming format

### Phase 4: Advanced Features
- [ ] Model parameter mapping
- [ ] Enhanced session management
- [ ] API key validation
- [ ] Rate limiting

## Contributing

1. Ensure tests pass: `python -m pytest tests/ -v`
2. Follow existing code style
3. Add tests for new features

## License

Local development use only.
