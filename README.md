# Open Rabbit

An open-source AI-powered code review system inspired by CodeRabbit. Open Rabbit automatically reviews pull requests, provides actionable feedback, and learns from user interactions to improve over time.

![Architecture Overview](public/image.png)

## Features

- **Automated PR Reviews**: Automatically reviews pull requests when opened or updated
- **Multi-Agent Architecture**: Supervisor-orchestrated pipeline with specialized agents
- **Knowledge Base Integration**: Learns from user feedback to improve future reviews
- **Multiple LLM Support**: Works with OpenAI, Anthropic Claude, and OpenRouter
- **Static Analysis**: AST-based code parsing, security scanning, and complexity detection
- **GitHub Integration**: Seamless integration via GitHub App

## Architecture

Open Rabbit uses a multi-agent architecture for comprehensive code review:

![Cloud Architecture](public/code-rabbit%20architecture.jpeg)

### Components

| Component | Description |
|-----------|-------------|
| **Bot** | Probot-based GitHub App that handles PR events and webhook integration |
| **Backend** | FastAPI server with multi-agent orchestration system |
| **Knowledge Base** | Elasticsearch-powered semantic search for storing and retrieving learnings |
| **Database** | PostgreSQL for persistent storage and checkpointing |
| **Redis** | Task queue and caching layer |

### Multi-Agent System

```
┌─────────────────────────────────────────────────────────────┐
│                    SUPERVISOR AGENT                          │
│  - Orchestrates review pipeline                              │
│  - Manages agent coordination                                │
│  - Aggregates and filters results                           │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  PARSER AGENT   │  │  REVIEW AGENT   │  │ UNIT TEST AGENT │
│                 │  │                 │  │                 │
│ - AST Analysis  │  │ - LLM Review    │  │ - Test Gen      │
│ - Security Scan │  │ - KB Context    │  │ - Coverage      │
│ - Complexity    │  │ - Suggestions   │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Node.js 18+
- Python 3.11+
- GitHub App credentials

### 1. Clone the Repository

```bash
git clone https://github.com/JagjeevanAK/open-rabbit.git
cd open-rabbit
```

### 2. Start Infrastructure Services

```bash
docker compose up -d
```

This starts:
- PostgreSQL (port 5432)
- Redis (port 6379)
- Elasticsearch (port 9200)

### 3. Setup Backend

```bash
cd backend
cp .env.example .env
# Edit .env with your configuration

# Install dependencies
uv sync

# Run migrations
uv run alembic upgrade head

# Start the server
uv run uvicorn main:app --port 8080
```

### 4. Setup Bot

```bash
cd bot
cp .env.example .env
# Edit .env with your GitHub App credentials

# Install dependencies
npm install

# Start the bot
npm start
```

### 5. Setup Knowledge Base (Optional)

```bash
cd knowledge-base
cp .env.example .env
# Edit .env with your OpenAI API key

# Install dependencies
uv sync

# Start the service
uv run uvicorn app:app --port 8000
```

## Configuration

### Environment Variables

#### Backend (`backend/.env`)

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/openrabbit
REDIS_URL=redis://localhost:6379/0
LLM_PROVIDER=openai          # openai, anthropic, openrouter
OPENAI_API_KEY=sk-...
KB_ENABLED=true
KNOWLEDGE_BASE_URL=http://localhost:8000
```

#### Bot (`bot/.env`)

```bash
APP_ID=your-github-app-id
PRIVATE_KEY_PATH=./private-key.pem
WEBHOOK_SECRET=your-webhook-secret
BACKEND_URL=http://localhost:8080
```

#### Knowledge Base (`knowledge-base/.env`)

```bash
OPENAI_API_KEY=sk-...
ELASTICSEARCH_URL=http://localhost:9200
```

## Usage

### Automatic Reviews

Open Rabbit automatically reviews PRs when:
- A new PR is opened
- New commits are pushed to a PR

### Manual Reviews

Comment on a PR with:
```
/review
```

### Generate Unit Tests

Comment on an issue with:
```
/create-unit-test
```

### Feedback Loop

React to review comments to help Open Rabbit learn:
- 👍 Helpful suggestion
- 👎 Not helpful / false positive
- Reply with corrections for the AI to learn from

## API Endpoints

### Bot Service

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/bot/health` | GET | Health check |
| `/bot/review` | POST | Trigger manual review |
| `/bot/task-status/{id}` | GET | Get task status |
| `/bot/tasks` | GET | List all tasks |

### Knowledge Base

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/learnings` | POST | Add new learning |
| `/learnings/search` | GET | Search learnings |
| `/learnings/pr-context` | POST | Get PR-relevant learnings |

## Project Structure

```
open-rabbit/
├── backend/                 # FastAPI backend server
│   ├── agent/              # Multi-agent system
│   │   ├── supervisor/     # Orchestration layer
│   │   ├── subagents/      # Specialized agents
│   │   ├── schemas/        # Pydantic models
│   │   └── services/       # External integrations
│   ├── db/                 # Database models & CRUD
│   ├── routes/             # API endpoints
│   └── services/           # Business logic
├── bot/                    # Probot GitHub App
│   └── src/               # TypeScript source
├── knowledge-base/         # Elasticsearch KB service
├── public/                 # Static assets
└── docker-compose.yml      # Infrastructure setup
```

## Development

### Running Tests

```bash
# Backend tests
cd backend
uv run pytest

# Bot tests
cd bot
npm test
```

### Code Style

```bash
# Backend
cd backend
uv run ruff check .
uv run ruff format .

# Bot
cd bot
npm run lint
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is open source and available under the [MIT License](LICENSE).

## Acknowledgments

- Inspired by [CodeRabbit](https://coderabbit.ai)
- Built with [Probot](https://probot.github.io), [FastAPI](https://fastapi.tiangolo.com), and [LangChain](https://langchain.com)
