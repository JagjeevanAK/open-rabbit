# Knowledge Base

A structured knowledge base for storing and retrieving code learnings using Elasticsearch and OpenAI embeddings.

## Features

- **Semantic Search**: Uses OpenAI embeddings for intelligent document retrieval
- **Async Processing**: Celery-based background task processing for document indexing
- **REST API**: FastAPI-based API for CRUD operations
- **PR Context**: Specialized endpoint for retrieving learnings relevant to code reviews

## Installation

```bash
cd knowledge-base
uv sync
```

## Usage

### Start the API server

```bash
uv run uvicorn knowledge_base.app:app --reload --host 0.0.0.0 --port 8001
```

### Start the Celery worker

```bash
uv run celery -A knowledge_base.celery_app worker --loglevel=info
```

### Initialize Elasticsearch index

```bash
uv run python -c "from knowledge_base.elastic import init_index; init_index()"
```

## API Endpoints

- `POST /learnings` - Add a new learning
- `GET /learnings/search` - Search learnings semantically
- `POST /learnings/pr-context` - Get learnings relevant to a PR
- `GET /learnings/{id}` - Get a specific learning
- `DELETE /learnings/{id}` - Delete a learning
- `GET /health` - Health check

## Configuration

Environment variables (in `.env`):

- `ELASTICSEARCH_URL` - Elasticsearch connection URL
- `OPENAI_API_KEY` - OpenAI API key for embeddings
- `REDIS_URL` - Redis URL for Celery broker
