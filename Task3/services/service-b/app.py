import os

from flask import Flask, jsonify, request
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


SERVICE_NAME = "service-b"
OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")


def configure_tracing() -> None:
    resource = Resource.create({"service.name": SERVICE_NAME})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=f"{OTLP_ENDPOINT}/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)


configure_tracing()

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()


@app.get("/manufacturing-plan")
def manufacturing_plan():
    order_id = request.args.get("order_id", "unknown")
    plan_id = f"plan-{order_id[:8]}"
    current_span = trace.get_current_span()
    current_span.set_attribute("order.id", order_id)
    current_span.set_attribute("manufacturing.plan_id", plan_id)
    current_span.set_attribute("manufacturing.line", "alexandrite-line-1")
    current_span.set_attribute("manufacturing.priority", "standard")

    return jsonify(
        {
            "order_id": order_id,
            "plan_id": plan_id,
            "status": "planned",
            "line": "alexandrite-line-1",
        }
    )


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": SERVICE_NAME})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
