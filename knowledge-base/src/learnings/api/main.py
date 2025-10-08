"""
Main entry point for the Learnings API with OpenTelemetry.
"""

import os
from src.learnings.observability.telemetry import setup_telemetry, get_tracer, get_meter
from src.learnings.api.routes import app

# Setup telemetry before importing other modules
setup_telemetry(
    service_name="learnings-api",
    service_version=os.getenv("SERVICE_VERSION", "1.0.0")
)

# Get tracer and meter for custom instrumentation
tracer = get_tracer("learnings-api")
meter = get_meter("learnings-api")

# Custom metrics
learning_ingestion_counter = meter.create_counter(
    "learnings_ingested_total",
    description="Total number of learnings ingested"
)

learning_search_counter = meter.create_counter(
    "learnings_searches_total", 
    description="Total number of learning searches"
)

learning_retrieval_duration = meter.create_histogram(
    "learnings_retrieval_duration_seconds",
    description="Time spent retrieving learnings"
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
