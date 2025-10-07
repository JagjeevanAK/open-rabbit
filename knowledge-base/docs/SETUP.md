# Learnings System - Setup Guide

Complete setup instructions for the CodeRabbit-inspired Learnings system.

## Prerequisites

- **Python 3.11+**
- **Docker & Docker Compose** (for Redis and Qdrant)
- **OpenAI API Key**

## Step-by-Step Setup

### 1. Install Dependencies

Using `uv` (recommended):
```bash
uv sync
```

Or using `pip`:
```bash
pip install -e .
```

### 2. Configure Environment

```bash
# Copy the environment template
cp .env.example .env

# Edit .env and add your OpenAI API key
# Required: OPENAI_API_KEY=sk-...
nano .env
```

**Important environment variables:**
- `OPENAI_API_KEY`: Your OpenAI API key (required)
- `EMBEDDING_MODEL`: `text-embedding-3-large` (recommended) or `text-embedding-3-small` (cheaper)
- `LLM_MODEL`: `gpt-4o-mini` (default) or `gpt-4o` for better extraction
- `QDRANT_URL`: Qdrant server URL (default: `http://localhost:6333`)
- `REDIS_URL`: Redis server URL (default: `redis://localhost:6379/0`)

### 3. Start Infrastructure Services

Using Docker Compose (recommended):
```bash
# Start Redis and Qdrant
docker-compose up -d

# Check services are running
docker-compose ps
```

Or using the Makefile:
```bash
make start-services
```

**Manual setup (alternative):**

**Redis:**
```bash
# Using Docker
docker run -d -p 6379:6379 redis:7-alpine

# Or system Redis
redis-server
```

**Qdrant:**
```bash
# Using Docker
docker run -d -p 6333:6333 -p 6334:6334 qdrant/qdrant
```

### 4. Start Celery Worker

Open a new terminal:
```bash
celery -A celery_worker worker --loglevel=info
```

Or using the Makefile:
```bash
make start-worker
```

You should see:
```
[2025-10-07 10:00:00,000: INFO/MainProcess] Connected to redis://localhost:6379/0
[2025-10-07 10:00:00,000: INFO/MainProcess] mingle: searching for neighbors
[2025-10-07 10:00:00,000: INFO/MainProcess] mingle: all alone
[2025-10-07 10:00:00,000: INFO/MainProcess] celery@hostname ready.
```

### 5. Start FastAPI Server

Open another terminal:
```bash
uvicorn main:app --reload --port 8000
```

Or using the Makefile:
```bash
make start-api
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
```

### 6. Verify Installation

**Check health endpoints:**
```bash
# API health
curl http://localhost:8000/health

# Worker health
curl http://localhost:8000/worker-health

# Collection stats
curl http://localhost:8000/stats
```

Or using the Makefile:
```bash
make test-health
```

**Expected responses:**
```json
// /health
{
  "status": "healthy",
  "service": "learnings-api",
  "version": "1.0.0"
}

// /worker-health
{
  "status": "healthy",
  "workers": "online",
  "result": {
    "status": "healthy",
    "timestamp": "2025-10-07T10:00:00.000000",
    "worker": "learnings-worker"
  }
}
```

### 7. Run Example Script

Open another terminal:
```bash
python example.py
```

Or using the Makefile:
```bash
make example
```

This will:
1. Check health endpoints
2. Ingest 5 sample review comments
3. Search for learnings with various queries
4. Test PR-specific retrieval
5. Display formatted context for LLM injection
6. Show collection statistics

## Quick Start with Makefile

```bash
# Complete setup (install, configure, start services)
make setup

# Then in separate terminals:
make start-worker  # Terminal 2
make start-api     # Terminal 3
make example       # Terminal 4 (to test)
```

## Architecture Overview

```
Terminal 1: docker-compose up -d      (Redis + Qdrant)
Terminal 2: make start-worker          (Celery workers)
Terminal 3: make start-api             (FastAPI server)
Terminal 4: make example               (Test script)
```

## Troubleshooting

### "Connection refused" errors

**Problem:** Cannot connect to Redis or Qdrant
**Solution:**
```bash
# Check if services are running
docker-compose ps

# Restart services
docker-compose restart

# Check logs
docker-compose logs redis
docker-compose logs qdrant
```

### "No module named 'xxx'" errors

**Problem:** Missing dependencies
**Solution:**
```bash
# Reinstall dependencies
uv sync
# or
pip install -e .
```

### "OpenAI API key not found"

**Problem:** OPENAI_API_KEY not set
**Solution:**
```bash
# Edit .env file
nano .env

# Add your key:
OPENAI_API_KEY=sk-your-key-here
```

### Celery workers not processing tasks

**Problem:** Worker is not connected to Redis
**Solution:**
```bash
# Check Redis is running
redis-cli ping
# Should return: PONG

# Check Celery can connect
celery -A celery_worker inspect ping
```

### Qdrant collection errors

**Problem:** Collection not created or inaccessible
**Solution:**
```bash
# Check Qdrant is running
curl http://localhost:6333/

# Check collections
curl http://localhost:6333/collections

# Delete and recreate collection
curl -X DELETE http://localhost:6333/collections/learnings

# Restart API to recreate
# (collection is auto-created on first request)
```

### "Embedding dimensions mismatch"

**Problem:** Changed embedding model but collection exists with old dimensions
**Solution:**
```bash
# Delete existing collection
curl -X DELETE http://localhost:6333/collections/learnings

# Update .env with new model and dimensions
nano .env

# Restart services to recreate collection
```

## Development Workflow

### Daily Development

```bash
# Terminal 1: Services (leave running)
docker-compose up -d

# Terminal 2: Worker (restart on code changes)
celery -A celery_worker worker --loglevel=info

# Terminal 3: API (auto-reloads on code changes)
uvicorn main:app --reload --port 8000

# Terminal 4: Testing
python example.py
# or
curl -X POST http://localhost:8000/learnings/ingest -H "Content-Type: application/json" -d @test_payload.json
```

### Testing Changes

```bash
# After making code changes:

# 1. Restart Celery worker (Ctrl+C, then restart)
celery -A celery_worker worker --loglevel=info

# 2. API auto-reloads (no restart needed if using --reload)

# 3. Test your changes
python example.py
```

### Viewing API Documentation

```bash
# Open in browser:
open http://localhost:8000/docs

# Or using Makefile:
make docs
```

This opens interactive Swagger UI where you can:
- View all endpoints
- Test API calls
- See request/response schemas

## Production Deployment

### Environment Variables

Create production `.env`:
```bash
OPENAI_API_KEY=sk-prod-key

# Use text-embedding-3-large for better quality
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_DIMENSIONS=3072

# Use gpt-4o for better extraction (or gpt-4o-mini for cost)
LLM_MODEL=gpt-4o-mini

# Production Qdrant (cloud or self-hosted)
QDRANT_URL=https://your-qdrant-cluster.cloud
QDRANT_API_KEY=your-qdrant-api-key

# Production Redis
REDIS_URL=redis://your-redis-host:6379/0
CELERY_BROKER_URL=redis://your-redis-host:6379/0
CELERY_RESULT_BACKEND=redis://your-redis-host:6379/0
```

### Docker Deployment

```bash
# Build Docker image (future enhancement)
# docker build -t learnings-api .

# Run with docker-compose
# docker-compose -f docker-compose.prod.yml up -d
```

### Scaling

**Horizontal scaling:**
```bash
# Run multiple Celery workers
celery -A celery_worker worker --concurrency=8

# Or scale workers in Docker
docker-compose up -d --scale worker=4
```

**Load balancing:**
- Use Nginx or Traefik for API load balancing
- Use Redis cluster for Celery broker
- Use Qdrant cluster for vector DB

## Next Steps

1. **Integrate with review agent**: See `README.md` for integration examples
2. **Add to LangGraph workflow**: See `langgraph_integration.py`
3. **Ingest historical data**: Use batch ingestion endpoint
4. **Monitor performance**: Use `/stats` endpoint and Flower
5. **Customize extraction prompts**: Edit `config.py`

## Resources

- **API Documentation**: http://localhost:8000/docs
- **Qdrant Dashboard**: http://localhost:6333/dashboard
- **Main README**: See `README.md` for architecture details
- **Example Usage**: See `example.py` for comprehensive examples
