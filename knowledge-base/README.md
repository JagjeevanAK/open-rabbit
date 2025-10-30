# Knowledge Base API

A structured knowledge base system for storing and retrieving code learnings using Elasticsearch, OpenAI embeddings, and asynchronous processing with Celery.

## Features

- **FastAPI REST API** for submitting learnings
- **Celery** for asynchronous processing
- **Elasticsearch** for vector search
- **OpenAI Embeddings** for semantic search
- **Redis** as message broker and result backend

## Prerequisites

- Python 3.13+
- Elasticsearch 8.x
- Redis 6.x+
- OpenAI API key

## Installation

1. Clone the repository and navigate to the project directory:

```bash
cd knowledge-base
```

2. Install dependencies using uv:

```bash
uv sync
```

3. Set up environment variables:

```bash
cp .env.example .env
```

Edit `.env` and add your OpenAI API key and other configuration.

4. Start Elasticsearch:

```bash
# Using Docker
docker run -d --name elasticsearch \
  -p 9200:9200 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  elasticsearch:8.16.0
```

5. Start Redis:

```bash
# Using Docker
docker run -d --name redis -p 6379:6379 redis:7
```

6. Initialize the Elasticsearch index:

```bash
uv run python elastic/hybrid_search.py
```

## Running the Application

You need to run three separate processes:

### 1. Start the API Server

```bash
uv run uvicorn app:app --reload
```

The API will be available at `http://localhost:8000`

### 2. Start Celery Worker

```bash
uv run celery -A celery_app worker --loglevel=info
```

### 3. (Optional) Start Celery Flower for monitoring

```bash
uv run celery -A celery_app flower
```

Visit `http://localhost:5555` to monitor tasks.

## API Usage

### Add a Single Learning

```bash
curl -X POST "http://localhost:8000/learnings" \
  -H "Content-Type: application/json" \
  -d '{
    "learning": "The Zero project prefers to handle dependency updates through automated tools like Dependabot rather than manual updates.",
    "learnt_from": "JagjeevanAK",
    "pr": "Mail-0/Zero#1583",
    "file": "apps/docs/package.json:1-0",
    "timestamp": "2025-07-01T12:53:32.467Z"
  }'
```

Response:
```json
{
  "status": "queued",
  "message": "Learning has been queued for processing",
  "task_id": "abc123-def456-..."
}
```

### Check Task Status

```bash
curl "http://localhost:8000/tasks/{task_id}"
```

Response:
```json
{
  "task_id": "abc123-def456-...",
  "status": "SUCCESS",
  "result": {
    "status": "success",
    "document_id": "xyz789",
    "index": "open_rabbit_knowledge_base"
  }
}
```

### Add Multiple Learnings (Batch)

```bash
curl -X POST "http://localhost:8000/learnings/batch" \
  -H "Content-Type: application/json" \
  -d '[
    {
      "learning": "First learning...",
      "learnt_from": "User1"
    },
    {
      "learning": "Second learning...",
      "learnt_from": "User2"
    }
  ]'
```

## Data Model

### Learning Request

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `learning` | string | Yes | The learning or insight to store |
| `learnt_from` | string | No | Source or author of the learning |
| `pr` | string | No | Related PR reference (e.g., 'repo/project#123') |
| `file` | string | No | Related file reference (e.g., 'path/to/file.py:10-20') |
| `timestamp` | string | No | ISO format timestamp (auto-generated if not provided) |

## Querying the Knowledge Base

Use the `main.py` script to query stored learnings:

```bash
uv run python main.py
```

Or use it programmatically:

```python
from main import query_knowledge_base

response = query_knowledge_base("What are the best practices for dependency management?")
print(response)
```

## Project Structure

```
knowledge-base/
├── app.py                 # FastAPI application
├── celery_app.py         # Celery configuration
├── tasks.py              # Celery tasks
├── config.py             # Configuration settings
├── main.py               # Query interface
├── elastic/
│   └── hybrid_search.py  # Elasticsearch setup
├── pyproject.toml        # Project dependencies
└── README.md
```

## API Documentation

Once the API is running, visit:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Environment Variables

See `.env.example` for all available configuration options:

- `ELASTICSEARCH_URL`: Elasticsearch connection URL
- `INDEX_NAME`: Elasticsearch index name
- `REDIS_URL`: Redis connection URL
- `OPENAI_API_KEY`: Your OpenAI API key
- `OPENAI_EMBEDDING_MODEL`: Embedding model (default: text-embedding-3-small)
- `OPENAI_CHAT_MODEL`: Chat model for queries (default: gpt-4)
- `API_HOST`: API server host (default: 0.0.0.0)
- `API_PORT`: API server port (default: 8000)

## Development

### Install Development Dependencies

```bash
uv sync --dev
```

### Run Tests

```bash
uv run pytest
```

## Troubleshooting

### Celery worker not processing tasks

- Ensure Redis is running: `redis-cli ping`
- Check Celery worker logs for errors
- Verify `CELERY_BROKER_URL` in `.env` matches your Redis instance

### Elasticsearch connection errors

- Ensure Elasticsearch is running: `curl http://localhost:9200`
- Verify `ELASTICSEARCH_URL` in `.env`
- Check Elasticsearch logs

### OpenAI API errors

- Verify your `OPENAI_API_KEY` is valid
- Check your OpenAI API usage limits
- Ensure you have access to the embedding model specified

## License

MIT
