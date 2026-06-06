import os
import uuid

import requests
from flask import Flask, jsonify
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


SERVICE_NAME = "service-a"
SERVICE_B_URL = os.getenv("SERVICE_B_URL", "http://localhost:8081")
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


@app.get("/")
def create_order():
    order_id = str(uuid.uuid4())
    current_span = trace.get_current_span()
    current_span.set_attribute("order.id", order_id)
    current_span.set_attribute("order.system", "alexandrite")
    current_span.set_attribute("downstream.service", "service-b")

    response = requests.get(
        f"{SERVICE_B_URL}/manufacturing-plan",
        params={"order_id": order_id},
        timeout=5,
    )
    current_span.set_attribute("downstream.status_code", response.status_code)
    response.raise_for_status()

    return jsonify(
        {
            "order_id": order_id,
            "downstream_status": response.status_code,
            "manufacturing_plan": response.json(),
        }
    )


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": SERVICE_NAME})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
