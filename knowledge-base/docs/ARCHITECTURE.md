# Architecture & Design Decisions

## System Overview

The Learnings system is designed to extract, store, and retrieve project-specific knowledge from code review comments, enabling AI reviewers to provide context-aware feedback based on past learnings.

## Core Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Review System (External)                    │
│                 (GitHub, GitLab, Review Agent)                  │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      │ Review Comment Payload
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI REST API                           │
│                     (routes.py / main.py)                       │
├─────────────────────────────────────────────────────────────────┤
│  POST /learnings/ingest         │  GET /learnings/search        │
│  POST /learnings/pr-context     │  GET /learnings/{id}          │
│  POST /learnings/format-context │  GET /health, /stats          │
└─────────┬───────────────────────┴───────────────────────────────┘
          │                                   ▲
          │ Queue Task                        │ Query
          ▼                                   │
┌─────────────────────────┐        ┌──────────┴──────────────────┐
│   Redis (Celery)        │        │  Retriever (retriever.py)   │
│   - Task Queue          │        │  - Semantic Search          │
│   - Result Backend      │        │  - Context Formatting       │
└─────────┬───────────────┘        │  - Ranking Logic            │
          │                        └─────────┬──────────────────┘
          │ Consume Task                     │
          ▼                                  │
┌─────────────────────────┐                  │
│  Celery Worker          │                  │
│  (ingestor.py)          │                  │
├─────────────────────────┤                  │
│  1. Extract Learning    │◄─────────────────┘
│     (extractor.py)      │     Read/Write
│  2. Generate Embedding  │
│  3. Store in Vector DB  │
│     (storage.py)        │
└─────────┬───────────────┘
          │
          │ Persist
          ▼
┌─────────────────────────┐
│   Qdrant Vector DB      │
│   - Embeddings          │
│   - Metadata            │
│   - Similarity Search   │
└─────────────────────────┘

External Dependencies:
┌─────────────────────────┐
│   OpenAI API            │
│   - text-embedding-3-*  │
│   - gpt-4o-mini/gpt-4o  │
└─────────────────────────┘
```

## Module Responsibilities

### 1. **models.py** - Data Schemas
- **Purpose**: Define Pydantic models for type safety and validation
- **Key Types**:
  - `ReviewComment`: Input from review system
  - `Learning`: Core entity with metadata + embedding
  - `LearningSource`: Contextual metadata (repo, PR, file)
  - `FeedbackType`: Human feedback classification
  - Request/Response models for API
- **Design**: Immutable data transfer objects (DTOs)

### 2. **config.py** - Configuration Management
- **Purpose**: Centralized settings with environment variable loading
- **Pattern**: Singleton via `@lru_cache`
- **Features**:
  - Type-safe settings using Pydantic BaseSettings
  - Default values with overrides via `.env`
  - Configurable prompts for extraction
- **Design Principle**: 12-factor app configuration

### 3. **extractor.py** - Learning Extraction
- **Purpose**: Convert raw comments → normalized learnings using LLM
- **Architecture**:
  - `LearningExtractor`: Single comment extraction
  - `BatchLearningExtractor`: Batch processing for efficiency
- **Process**:
  1. Pre-filter trivial comments (regex heuristics)
  2. Build context-aware prompt
  3. Call LLM (GPT-4o-mini by default)
  4. Parse and validate response
  5. Return extracted learning or None
- **Design**: Strategy pattern (swappable extraction logic)

### 4. **storage.py** - Vector Database Layer
- **Purpose**: Repository pattern for Qdrant operations
- **Operations**:
  - `store_learning()`: Embed + persist
  - `search_similar()`: Semantic search with filters
  - `get_learning_by_id()`: Point lookup
  - `delete_learning()`: Removal
- **Features**:
  - Auto-collection creation
  - Rich metadata storage
  - Filter support (repo, language, confidence)
- **Design**: Repository pattern with abstraction over Qdrant

### 5. **retriever.py** - Search & Context Formatting
- **Purpose**: High-level API for learning retrieval
- **Key Methods**:
  - `search()`: Semantic search with ranking
  - `get_learnings_for_pr_context()`: PR-specific retrieval
  - `format_for_context()`: LLM-ready formatting
- **Ranking Factors**:
  - Vector similarity (primary)
  - Confidence score
  - Feedback type (positive > negative)
  - File/directory relevance
  - Recency (future)
- **Design**: Facade pattern over storage layer

### 6. **ingestor.py** - Async Task Pipeline
- **Purpose**: Celery tasks for background processing
- **Tasks**:
  - `ingest_learning_task`: Single comment → learning
  - `batch_ingest_learnings_task`: Bulk processing
  - `health_check_task`: Worker monitoring
- **Features**:
  - Retry logic with exponential backoff
  - Confidence scoring
  - Error handling and logging
- **Design**: Command pattern with async execution

### 7. **routes.py** - REST API Endpoints
- **Purpose**: FastAPI routes for external integration
- **Endpoint Groups**:
  - Ingestion: `/learnings/ingest`, `/learnings/ingest/batch`
  - Retrieval: `/learnings/search`, `/learnings/pr-context`
  - Management: `/learnings/{id}` (GET, DELETE)
  - Monitoring: `/health`, `/stats`, `/worker-health`
  - Integration: `/learnings/format-context`
- **Design**: RESTful with dependency injection

### 8. **langgraph_integration.py** - Workflow Integration
- **Purpose**: LangGraph nodes for review workflows
- **Components**:
  - `LearningsNode`: Retrieval node
  - `ReviewState`: Workflow state schema
  - Helper functions for prompt construction
- **Usage**: Drop-in node for LangGraph pipelines
- **Design**: Node pattern (callable state transformer)

## Key Design Decisions

### 1. Async Ingestion via Celery
**Rationale**: Learning extraction involves LLM calls (100-500ms) and embedding generation (50-100ms). Async processing ensures API remains responsive.

**Alternative Considered**: Sync processing
**Why Rejected**: Would block API for 500ms+ per comment

### 2. Vector DB (Qdrant) for Storage
**Rationale**: 
- Semantic search is core requirement
- Qdrant offers best performance for Python
- Rich metadata filtering support
- Mature ecosystem

**Alternatives Considered**: 
- Pinecone (cloud-only, more expensive)
- pgvector (requires PostgreSQL expertise)
- Chroma (less mature)

### 3. LLM-Based Extraction vs. Rule-Based
**Rationale**: Rule-based extraction (regex, NLP) is brittle and language-specific. LLMs provide flexible, high-quality extraction across languages.

**Tradeoff**: Higher cost/latency, but acceptable given async processing.

### 4. Rich Metadata Storage
**Rationale**: Storing repo, PR, file, author, feedback enables:
- Filtered retrieval (same repo/language)
- Quality signals (accepted > rejected feedback)
- Analytics and auditing
- A/B testing of learnings

**Tradeoff**: Larger payload, but enables powerful retrieval.

### 5. Confidence Scoring
**Rationale**: Not all learnings are equal. Scoring by feedback type, comment quality enables:
- Filtering low-quality learnings
- Weighted ranking in search
- Continuous improvement via feedback

**Formula**: Base score + feedback boost + context boost - penalties

### 6. Separation of Concerns
**Rationale**: Clean boundaries between:
- Data (models)
- Config (settings)
- Business Logic (extractor, retriever)
- I/O (storage, API)
- Tasks (ingestor)

**Benefit**: Testable, maintainable, swappable components

## Data Flow

### Ingestion Flow
```
1. POST /learnings/ingest
   └─> Validate ReviewComment
   └─> Queue Celery task
   └─> Return task_id

2. Celery Worker picks up task
   └─> Extract learning (LLM)
   └─> Generate embedding (OpenAI)
   └─> Store in Qdrant (with metadata)
   └─> Return learning_id

3. Client polls GET /learnings/ingest/{task_id}
   └─> Return status + result
```

### Retrieval Flow
```
1. POST /learnings/pr-context
   └─> Build query from PR description
   └─> Embed query (OpenAI)
   └─> Search Qdrant (cosine similarity)
   └─> Apply metadata filters
   └─> Rank by relevance + confidence
   └─> Return top-K learnings

2. Format for context injection
   └─> Format learnings with metadata
   └─> Inject into LLM prompt
```

## Scalability Considerations

### Horizontal Scaling
- **API**: Stateless, scale with load balancer
- **Celery Workers**: Scale to N workers
- **Qdrant**: Cluster mode for large datasets
- **Redis**: Cluster mode for high throughput

### Performance Optimizations
- **Batch Processing**: Reduce LLM calls via batch extraction
- **Caching**: Cache embeddings for common queries (future)
- **Async I/O**: Non-blocking Qdrant/Redis clients
- **Connection Pooling**: Reuse OpenAI/Qdrant connections

### Cost Optimizations
- **text-embedding-3-small**: 5x cheaper, 2% quality loss
- **gpt-4o-mini**: 60x cheaper than GPT-4o for extraction
- **Batch Embeddings**: Up to 50% cost reduction
- **Pre-filtering**: Avoid LLM calls for trivial comments

## Security & Privacy

### API Security (Future)
- [ ] API key authentication
- [ ] Rate limiting
- [ ] Request validation
- [ ] CORS configuration

### Data Privacy
- [ ] PII detection in comments
- [ ] Configurable retention policies
- [ ] Access control per repository
- [ ] Audit logging

## Testing Strategy

### Unit Tests
- Model validation
- Extraction logic
- Confidence scoring
- Ranking algorithms

### Integration Tests
- API endpoints
- Celery tasks
- Qdrant operations
- End-to-end flows

### Load Tests
- Concurrent ingestion
- High-volume search
- Worker capacity

## Future Enhancements

### Short Term
1. **Learning Deduplication**: Merge similar learnings
2. **Quality Feedback Loop**: Track learning effectiveness
3. **Analytics Dashboard**: Visualize learning trends
4. **A/B Testing**: Test learning impact on reviews

### Medium Term
5. **Multi-modal Learnings**: Support images, diagrams
6. **Cross-repo Learning**: Learn across organization
7. **Learning Evolution**: Update learnings over time
8. **Collaborative Filtering**: User-based recommendations

### Long Term
9. **Autonomous Learning**: Self-improving extraction
10. **Learning Graph**: Connect related learnings
11. **Predictive Suggestions**: Proactive learning injection
12. **Multi-language Support**: i18n for learnings

## CodeRabbit Alignment

This architecture mirrors CodeRabbit's approach:

| Feature | CodeRabbit | Our Implementation |
|---------|-----------|-------------------|
| Learning Extraction | ✓ LLM-based | ✓ GPT-4o-mini |
| Vector Storage | ✓ Proprietary | ✓ Qdrant |
| Async Processing | ✓ Background | ✓ Celery |
| Metadata Filtering | ✓ Rich context | ✓ Repo/file/language |
| Context Injection | ✓ Prompt augmentation | ✓ format_for_context() |
| Quality Signals | ✓ Feedback tracking | ✓ FeedbackType enum |

## References

- **CodeRabbit Blog**: https://coderabbit.ai/blog/how-coderabbit-learns
- **LangGraph Docs**: https://langchain-ai.github.io/langgraph/
- **Qdrant Docs**: https://qdrant.tech/documentation/
- **Celery Best Practices**: https://docs.celeryq.dev/en/stable/userguide/tasks.html
