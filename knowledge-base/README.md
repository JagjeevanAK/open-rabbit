# Learnings System - CodeRabbit Architecture

A production-ready **Learnings** subsystem inspired by CodeRabbit's architecture for extracting, storing, and retrieving project-specific learnings from code review comments.

## 🎯 Overview

This system enables AI code reviewers to learn from past feedback and inject relevant context into future reviews. It implements:

- **LLM-based learning extraction** from review comments
- **Vector database storage** for semantic search (Qdrant)
- **Async ingestion pipeline** using Celery workers
- **FastAPI REST endpoints** for integration
- **Context injection** for LangGraph/LangChain workflows

## 🏗️ Architecture

```
Review Comment → Ingestion Endpoint → Celery Queue
                                          ↓
                                   Extract Learning (LLM)
                                          ↓
                                   Generate Embedding
                                          ↓
                                   Store in Qdrant
                                          
Future Review → Search Endpoint → Retrieve Relevant Learnings → Inject into Prompt
```

### Components

| Module | Purpose |
|--------|---------|
| `models.py` | Pydantic schemas for learnings, comments, and requests |
| `config.py` | Settings and environment configuration |
| `extractor.py` | LLM-based learning extraction from raw comments |
| `storage.py` | Qdrant vector database persistence layer |
| `retriever.py` | Semantic search and context formatting |
| `ingestor.py` | Celery tasks for async processing |
| `routes.py` | FastAPI endpoints |
| `main.py` | Application entry point |
| `celery_worker.py` | Celery worker entry point |

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Redis (for Celery)
- Qdrant (vector database)
- OpenAI API key

### Installation

```bash
# Install dependencies
uv sync  # or pip install -e .

# Copy environment template
cp .env.example .env

# Edit .env with your credentials
# - Set OPENAI_API_KEY
# - Configure Qdrant URL (default: http://localhost:6333)
# - Configure Redis URL (default: redis://localhost:6379/0)
```

### Start Services

**Terminal 1: Start Qdrant**
```bash
docker run -p 6333:6333 qdrant/qdrant
```

**Terminal 2: Start Redis**
```bash
docker run -p 6379:6379 redis:latest
# Or use system Redis: redis-server
```

**Terminal 3: Start Celery Worker**
```bash
celery -A celery_worker worker --loglevel=info
```

**Terminal 4: Start FastAPI Server**
```bash
uvicorn main:app --reload --port 8000
```

Visit: http://localhost:8000/docs for interactive API documentation

## 📡 API Usage

### Ingest a Review Comment

```bash
curl -X POST http://localhost:8000/learnings/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "comment": {
      "comment_id": "c123",
      "raw_comment": "Always use const instead of let for variables that never change.",
      "code_snippet": "let config = { ... };",
      "language": "javascript",
      "source": {
        "repo_name": "acme/web-app",
        "pr_number": 1234,
        "file_path": "src/config.js",
        "author": "coderabbit-bot"
      }
    },
    "async_processing": true
  }'
```

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "learning_id": null
}
```

### Search for Learnings

```bash
curl "http://localhost:8000/learnings/search?q=dependency%20updates&k=3&repo=acme/web-app"
```

**Response:**
```json
{
  "query": "dependency updates",
  "results": [
    {
      "learning_id": "...",
      "learning_text": "The project requires regular dependency updates with security audits.",
      "original_comment": "Bump outdated dependencies...",
      "language": "javascript",
      "source": { ... },
      "confidence_score": 0.95
    }
  ],
  "total_results": 1,
  "search_time_ms": 45.2
}
```

### Get PR Context Learnings

```bash
curl -X POST http://localhost:8000/learnings/pr-context \
  -H "Content-Type: application/json" \
  -d '{
    "pr_description": "Add automated dependency update workflow",
    "changed_files": ["package.json", ".github/workflows/deps.yml"],
    "repo_name": "acme/web-app",
    "k": 5
  }'
```

## 🔧 Integration Examples

### With LangGraph

```python
from langgraph.graph import StateGraph
from retriever import LearningRetriever
from storage import LearningStorage
from config import get_settings

settings = get_settings()
storage = LearningStorage(settings)
retriever = LearningRetriever(storage, settings)

def inject_learnings_node(state):
    """LangGraph node that injects learnings into review context."""
    pr_context = state["pr_description"]
    changed_files = state["changed_files"]
    repo_name = state["repo_name"]
    
    # Retrieve relevant learnings
    learnings = retriever.get_learnings_for_pr_context(
        pr_description=pr_context,
        changed_files=changed_files,
        repo_name=repo_name,
        k=5
    )
    
    # Format for prompt injection
    context = retriever.format_for_context(learnings)
    
    # Add to state
    state["learnings_context"] = context
    return state

# Add to your LangGraph workflow
workflow = StateGraph(...)
workflow.add_node("inject_learnings", inject_learnings_node)
```

### With Review Agent

```python
import requests

def get_learnings_for_review(pr_description, changed_files, repo_name):
    """Fetch learnings to inject into review prompt."""
    response = requests.post(
        "http://localhost:8000/learnings/pr-context",
        json={
            "pr_description": pr_description,
            "changed_files": changed_files,
            "repo_name": repo_name,
            "k": 5
        }
    )
    return response.json()

# In your review flow:
learnings = get_learnings_for_review(
    pr_description="Fix auth bug",
    changed_files=["src/auth.py"],
    repo_name="acme/backend"
)

# Inject into LLM prompt:
prompt = f"""
{base_review_prompt}

## Past Project Learnings:
{format_learnings(learnings)}

Now review this PR...
"""
```

## 🧪 Testing

### Health Check

```bash
# API health
curl http://localhost:8000/health

# Worker health
curl http://localhost:8000/worker-health

# Collection stats
curl http://localhost:8000/stats
```

### Manual Testing

```python
# Test extraction
from extractor import LearningExtractor
from config import get_settings

settings = get_settings()
extractor = LearningExtractor(settings)

learning = extractor.extract_learning(
    raw_comment="Always validate user input before database queries.",
    code_snippet="db.query(user_input)",
    language="python"
)
print(learning)
# Output: "The project requires input validation before database operations to prevent injection attacks."
```

## 📊 Monitoring

- **API Docs**: http://localhost:8000/docs
- **Stats Endpoint**: http://localhost:8000/stats
- **Celery Flower** (optional): Install and run for worker monitoring
  ```bash
  pip install flower
  celery -A celery_worker flower --port=5555
  ```

## 🎨 Design Principles

This implementation follows CodeRabbit's architecture:

1. **Separation of Concerns**: Clear module boundaries for extraction, storage, retrieval
2. **Async Processing**: Non-blocking ingestion via Celery
3. **Rich Metadata**: Store context (repo, PR, file, feedback) for intelligent filtering
4. **Semantic Search**: Vector embeddings enable finding similar learnings by meaning
5. **Confidence Scoring**: Weight learnings by feedback type and quality signals
6. **Context Injection**: Format learnings for easy LLM prompt integration
7. **Scalability**: Stateless API, distributed workers, vector DB

## 🔮 Future Enhancements

- [ ] Add relational DB for structured queries (PostgreSQL with pgvector)
- [ ] Implement learning deduplication and merging
- [ ] Add learning lifecycle (draft → approved → archived)
- [ ] Implement user feedback collection endpoint
- [ ] Add analytics dashboard for learning insights
- [ ] Support multi-tenancy with organization isolation
- [ ] Add learning quality scoring model
- [ ] Implement A/B testing for learning effectiveness
- [ ] Add export/import for learning migration

## 📝 License

MIT License - See LICENSE file for details

## 🤝 Contributing

This is a reference implementation. Feel free to adapt for your needs.

---

**Built with ❤️ inspired by CodeRabbit's learning architecture**
