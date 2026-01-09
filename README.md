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
│                    SUPERVISOR AGENT                         │
│  - Orchestrates review pipeline                             │
│  - Manages agent coordination                               │
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

### Agent Workflow Sequence Diagram

The following diagram illustrates the complete workflow when a pull request is reviewed:

```mermaid
sequenceDiagram
    autonumber
    participant GH as GitHub
    participant Bot as Bot Service
    participant API as Backend API
    participant Sup as Supervisor Agent
    participant KB as Knowledge Base
    participant Sandbox as E2B Sandbox
    participant Parser as Parser Agent
    participant Review as Review Agent
    participant Test as Unit Test Agent
    participant Agg as Result Aggregator

    %% PR Event Trigger
    GH->>Bot: Webhook (PR opened/updated)
    Bot->>Bot: Validate payload
    Bot->>API: POST /review (ReviewRequest)
    API->>Sup: run(request, session_id)

    %% Intent Parsing
    Sup->>Sup: Parse intent from request

    %% Sandbox Setup
    Sup->>Sandbox: Create isolated environment
    Sandbox-->>Sup: sandbox_id, repo_path
    Sup->>Sandbox: Clone repository
    Sandbox-->>Sup: Clone complete

    %% Knowledge Base Fetch
    Sup->>KB: Fetch learnings for PR context
    KB-->>Sup: KBContext (past learnings, patterns)

    %% Parser Agent Execution
    Sup->>Parser: Analyze files (with sandbox access)
    Parser->>Sandbox: Read file contents
    Sandbox-->>Parser: File data
    Parser->>Parser: AST analysis
    Parser->>Parser: Security scanning
    Parser->>Parser: Complexity detection
    Parser-->>Sup: ParserOutput (issues, metrics)

    %% Review Agent Execution
    Sup->>Review: Review code (with KB context)
    Review->>Review: LLM-based review
    Review->>Review: Apply KB learnings
    Review-->>Sup: ReviewOutput (comments, suggestions)

    %% Conditional: Unit Test Generation
    alt Intent includes test generation
        Sup->>Test: Generate unit tests
        Test->>Sandbox: Analyze test coverage
        Sandbox-->>Test: Coverage data
        Test->>Test: Generate test code
        Test-->>Sup: TestOutput (test files)
    end

    %% Result Aggregation
    Sup->>Agg: Aggregate all results
    Agg->>Agg: Merge parser findings
    Agg->>Agg: Merge review comments
    Agg->>Agg: Filter duplicates
    Agg->>Agg: Prioritize issues
    Agg-->>Sup: SupervisorOutput

    %% Sandbox Cleanup
    Sup->>Sandbox: Kill sandbox
    Sandbox-->>Sup: Cleanup complete

    %% Response Chain
    Sup-->>API: SupervisorOutput
    API-->>Bot: Review results
    Bot->>GH: Post PR comments
    Bot->>GH: Create review summary
```

### Feedback Learning Sequence

When users react to review comments, Open Rabbit learns from the feedback:

```mermaid
sequenceDiagram
    autonumber
    participant User as Developer
    participant GH as GitHub
    participant Bot as Bot Service
    participant API as Backend API
    participant Feedback as Feedback Agent
    participant KB as Knowledge Base

    User->>GH: React to comment (thumbs up/down)
    GH->>Bot: Webhook (issue_comment reaction)
    Bot->>API: POST /feedback

    API->>Feedback: Process feedback
    Feedback->>Feedback: Extract context
    Feedback->>Feedback: Determine sentiment
    Feedback->>Feedback: Generate learning

    alt Positive feedback
        Feedback->>KB: Store as positive pattern
        KB-->>Feedback: Learning stored
    else Negative feedback
        Feedback->>KB: Store as anti-pattern
        KB-->>Feedback: Learning stored
    end

    Feedback-->>API: FeedbackResult
    API-->>Bot: Acknowledgment
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Node.js 18+
- Python 3.11+ & UV
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
