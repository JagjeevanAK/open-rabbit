# Quick Reference Guide

## 🚀 Quick Start Commands

```bash
# 1. Initial Setup (one time)
cp .env.example .env                    # Create environment file
# Edit .env and add OPENAI_API_KEY

# 2. Install Dependencies
uv sync                                 # or: pip install -e .

# 3. Start Services (Terminal 1)
docker-compose up -d                    # Redis + Qdrant

# 4. Start Worker (Terminal 2)
celery -A celery_worker worker --loglevel=info

# 5. Start API (Terminal 3)
uvicorn main:app --reload --port 8000

# 6. Test System (Terminal 4)
python example.py
```

## 📡 API Endpoints Cheat Sheet

### Ingestion
```bash
# Ingest single comment (async)
POST /learnings/ingest
Content-Type: application/json
{
  "comment": {
    "comment_id": "c123",
    "raw_comment": "Use const instead of let...",
    "language": "javascript",
    "source": {
      "repo_name": "org/repo",
      "pr_number": 123,
      "file_path": "src/file.js",
      "author": "bot"
    }
  }
}

# Check ingestion status
GET /learnings/ingest/{task_id}

# Batch ingest
POST /learnings/ingest/batch
Body: [ReviewComment, ReviewComment, ...]
```

### Retrieval
```bash
# Semantic search
GET /learnings/search?q=error+handling&k=5&repo=org/repo

# PR-specific retrieval
POST /learnings/pr-context
{
  "pr_description": "Add auth feature",
  "changed_files": ["src/auth.py"],
  "repo_name": "org/repo",
  "k": 5
}

# Get by ID
GET /learnings/{learning_id}

# Delete learning
DELETE /learnings/{learning_id}
```

### Integration
```bash
# Get formatted context for LLM
POST /learnings/format-context?q=best+practices&k=3

# Response:
{
  "formatted_context": "## Relevant Project Learnings:\n\n1. ...",
  "total_learnings": 3,
  "query": "best practices"
}
```

### Monitoring
```bash
# Health checks
GET /health              # API health
GET /worker-health       # Worker health
GET /stats               # Collection stats
```

## 🔧 Environment Variables

```bash
# Required
OPENAI_API_KEY=sk-...

# Embedding (choose one)
EMBEDDING_MODEL=text-embedding-3-large  # Better quality
EMBEDDING_MODEL=text-embedding-3-small  # 5x cheaper
EMBEDDING_DIMENSIONS=3072               # for -large (1536 for -small)

# LLM
LLM_MODEL=gpt-4o-mini                   # Cost-effective
LLM_MODEL=gpt-4o                        # Better quality
LLM_TEMPERATURE=0.0

# Infrastructure
QDRANT_URL=http://localhost:6333
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

## 📚 Python Usage Examples

### Direct Import
```python
from retriever import LearningRetriever
from storage import LearningStorage
from config import get_settings
from models import LearningSearchRequest

# Initialize
settings = get_settings()
storage = LearningStorage(settings)
retriever = LearningRetriever(storage, settings)

# Search
request = LearningSearchRequest(
    query="error handling best practices",
    k=5,
    repo_filter="acme/backend",
    min_confidence=0.7
)
response = retriever.search(request)

for learning in response.results:
    print(f"{learning.learning_text} (confidence: {learning.confidence_score})")
```

### PR Context Retrieval
```python
learnings = retriever.get_learnings_for_pr_context(
    pr_description="Add authentication feature",
    changed_files=["src/auth.py", "src/middleware.py"],
    repo_name="acme/backend",
    k=5
)

# Format for LLM
context = retriever.format_for_context(learnings)
prompt = f"{base_prompt}\n\n{context}\n\nNow review this code..."
```

### LangGraph Integration
```python
from langgraph_integration import LearningsNode
from langgraph.graph import StateGraph

workflow = StateGraph(ReviewState)
workflow.add_node("inject_learnings", LearningsNode())
workflow.add_edge("fetch_pr", "inject_learnings")
workflow.add_edge("inject_learnings", "review_code")
```

### REST API Integration
```python
import requests

# Ingest
response = requests.post(
    "http://localhost:8000/learnings/ingest",
    json={"comment": {...}, "async_processing": True}
)
task_id = response.json()["task_id"]

# Search
response = requests.get(
    "http://localhost:8000/learnings/search",
    params={"q": "dependency updates", "k": 3}
)
learnings = response.json()["results"]
```

## 🐛 Troubleshooting

### Service Not Running
```bash
# Check services
docker-compose ps

# Restart
docker-compose restart

# View logs
docker-compose logs redis
docker-compose logs qdrant
```

### Worker Issues
```bash
# Test Redis connection
redis-cli ping  # Should return: PONG

# Check worker connectivity
celery -A celery_worker inspect ping

# Check active workers
celery -A celery_worker inspect active
```

### API Errors
```bash
# Check API logs
uvicorn main:app --log-level debug

# Test health
curl http://localhost:8000/health

# Check Qdrant
curl http://localhost:6333/
```

### Missing Dependencies
```bash
# Reinstall
uv sync
# or
pip install -e .
```

## 📊 Collection Management

### View Collections
```bash
curl http://localhost:6333/collections
```

### Delete Collection (start fresh)
```bash
curl -X DELETE http://localhost:6333/collections/learnings
# Restart API to recreate
```

### Get Collection Info
```bash
curl http://localhost:6333/collections/learnings
```

## 🔍 Monitoring & Debugging

### Check Worker Status
```bash
celery -A celery_worker inspect stats
celery -A celery_worker inspect active
celery -A celery_worker inspect registered
```

### API Logs
```bash
# Development
uvicorn main:app --log-level debug

# Production
uvicorn main:app --log-level info --access-log
```

### Celery Flower (Web UI)
```bash
pip install flower
celery -A celery_worker flower --port=5555
# Open: http://localhost:5555
```

## 💾 Data Management

### Export Learnings
```python
# Get all learnings (future feature)
# Currently: query with high k
response = requests.get(
    "http://localhost:8000/learnings/search",
    params={"q": "", "k": 1000}
)
```

### Backup Qdrant
```bash
# Docker volume backup
docker run --rm -v learnings-qdrant:/data -v $(pwd):/backup \
  ubuntu tar cvf /backup/qdrant-backup.tar /data
```

### Restore Qdrant
```bash
# Docker volume restore
docker run --rm -v learnings-qdrant:/data -v $(pwd):/backup \
  ubuntu tar xvf /backup/qdrant-backup.tar -C /
```

## 🎨 Custom Configuration

### Change Embedding Model
```bash
# Edit .env
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536

# Delete existing collection
curl -X DELETE http://localhost:6333/collections/learnings

# Restart API (auto-creates with new dimensions)
```

### Customize Extraction Prompt
```python
# Edit config.py
extraction_system_prompt: str = """
Your custom extraction prompt here...
"""
```

### Change Collection Name
```bash
# Edit .env
QDRANT_COLLECTION_NAME=my-custom-collection

# Restart services
```

## 📈 Performance Tuning

### Scale Workers
```bash
# Single machine - more concurrency
celery -A celery_worker worker --concurrency=8

# Multiple machines
celery -A celery_worker worker --hostname=worker1@%h
celery -A celery_worker worker --hostname=worker2@%h
```

### Optimize Embeddings
```bash
# Use batch embeddings (future feature)
# Currently: process is already optimized per-request
```

### Cache Queries
```python
# Add caching layer (future enhancement)
from functools import lru_cache

@lru_cache(maxsize=1000)
def cached_search(query: str, k: int) -> list:
    # Implementation
```

## 🔐 Security Best Practices

### API Authentication (Future)
```python
# Add API key middleware
from fastapi import Header, HTTPException

async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401)
```

### Rate Limiting (Future)
```python
from fastapi_limiter import FastAPILimiter

@app.get("/learnings/search")
@limiter.limit("10/minute")
async def search_learnings(...):
    ...
```

### Environment Security
```bash
# Never commit .env
echo ".env" >> .gitignore

# Use secrets management in production
# - AWS Secrets Manager
# - Vault
# - Kubernetes Secrets
```

## 🌐 Production Deployment

### Docker Build
```dockerfile
# Dockerfile (future)
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -e .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Kubernetes Deployment
```yaml
# deployment.yaml (future)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: learnings-api
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: api
        image: learnings-api:latest
        ports:
        - containerPort: 8000
```

### Load Balancing
```nginx
# nginx.conf
upstream learnings_api {
    server api1:8000;
    server api2:8000;
    server api3:8000;
}

server {
    location / {
        proxy_pass http://learnings_api;
    }
}
```

## 📱 Client SDKs (Future)

### Python Client
```python
from learnings_client import LearningsClient

client = LearningsClient(base_url="http://api.example.com")
learnings = client.search("error handling", k=5)
```

### TypeScript Client
```typescript
import { LearningsClient } from '@learnings/client';

const client = new LearningsClient({ baseUrl: 'http://api.example.com' });
const learnings = await client.search('error handling', { k: 5 });
```

## 🎓 Learning Resources

- **FastAPI**: https://fastapi.tiangolo.com/
- **Celery**: https://docs.celeryq.dev/
- **Qdrant**: https://qdrant.tech/documentation/
- **LangChain**: https://python.langchain.com/
- **LangGraph**: https://langchain-ai.github.io/langgraph/
- **OpenAI Embeddings**: https://platform.openai.com/docs/guides/embeddings

## 📞 Support

For issues or questions:
1. Check `SETUP.md` for detailed troubleshooting
2. Review `ARCHITECTURE.md` for design decisions
3. Run `python example.py` to test end-to-end
4. Check API docs: http://localhost:8000/docs

---

**Remember:** This is a reference implementation. Adapt to your needs!
