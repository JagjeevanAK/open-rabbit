# Quick Start Guide

Get your Knowledge Base API up and running in 5 minutes!

## Step 1: Install Dependencies

```bash
uv sync
```

## Step 2: Set Up Environment

```bash
cp .env.example .env
```

Edit `.env` and add your OpenAI API key:
```
OPENAI_API_KEY=sk-your-key-here
```

## Step 3: Start Infrastructure

Start Elasticsearch and Redis using Docker:

```bash
docker-compose up -d
```

Wait a few seconds for services to start, then verify:

```bash
# Check Elasticsearch
curl http://localhost:9200

# Check Redis
redis-cli ping
```

## Step 4: Initialize Elasticsearch Index

```bash
uv run python elastic/hybrid_search.py
```

## Step 5: Start the Application

Open **3 separate terminals** and run:

**Terminal 1 - API Server:**
```bash
./run.sh api
```

**Terminal 2 - Celery Worker:**
```bash
./run.sh worker
```

**Terminal 3 (Optional) - Monitoring:**
```bash
./run.sh flower
```

## Step 6: Test the API

In a new terminal, run the example script:

```bash
uv run python example_usage.py
```

Or test manually with curl:

```bash
curl -X POST "http://localhost:8000/learnings" \
  -H "Content-Type: application/json" \
  -d '{
    "learning": "Always use type hints in Python for better code clarity",
    "learnt_from": "BestPractices"
  }'
```

## Step 7: Query the Knowledge Base

```bash
uv run python main.py
```

## What's Next?

- Visit `http://localhost:8000/docs` for interactive API documentation
- Visit `http://localhost:5555` for Celery task monitoring (if Flower is running)
- Check out the full README.md for more details

## Troubleshooting

**API won't start?**
- Make sure port 8000 is available
- Check if `.env` file exists

**Celery worker errors?**
- Verify Redis is running: `redis-cli ping`
- Check your OpenAI API key is set

**Elasticsearch errors?**
- Ensure Elasticsearch is running: `curl http://localhost:9200`
- Check Docker logs: `docker-compose logs elasticsearch`

## Stopping the Services

```bash
# Stop Docker services
docker-compose down

# Stop with data cleanup
docker-compose down -v
```
