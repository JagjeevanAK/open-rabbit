"""
OpenTelemetry configuration for the Learnings system.
"""

import os
from opentelemetry import trace, metrics, baggage
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor


def setup_telemetry(service_name: str, service_version: str = "1.0.0"):
    """
    Setup OpenTelemetry for a service.
    
    Args:
        service_name: Name of the service (e.g., 'learnings-api', 'learnings-worker')
        service_version: Version of the service
    """
    
    # OTLP endpoint (can be Jaeger, Grafana, etc.)
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    
    # Resource represents the entity producing telemetry
    resource = Resource.create({
        ResourceAttributes.SERVICE_NAME: service_name,
        ResourceAttributes.SERVICE_VERSION: service_version,
        ResourceAttributes.SERVICE_INSTANCE_ID: os.getenv("HOSTNAME", "localhost"),
    })
    
    # Setup Tracing
    trace_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(trace_provider)
    
    otlp_trace_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    span_processor = BatchSpanProcessor(otlp_trace_exporter)
    trace_provider.add_span_processor(span_processor)
    
    # Setup Metrics
    otlp_metric_exporter = OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True)
    metric_reader = PeriodicExportingMetricReader(
        exporter=otlp_metric_exporter,
        export_interval_millis=10000  # Export every 10 seconds
    )
    metric_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(metric_provider)
    
    # Auto-instrument libraries
    FastAPIInstrumentor.instrument()
    RequestsInstrumentor.instrument()
    CeleryInstrumentor.instrument()
    RedisInstrumentor.instrument()
    
    print(f"OpenTelemetry configured for {service_name}")
    print(f"  - Endpoint: {otlp_endpoint}")
    print(f"  - Resource: {service_name} v{service_version}")


def get_tracer(name: str):
    """Get a tracer for the given name."""
    return trace.get_tracer(name)


def get_meter(name: str):
    """Get a meter for the given name."""
    return metrics.get_meter(name)