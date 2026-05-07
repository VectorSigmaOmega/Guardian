from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify
from prometheus_client import CollectorRegistry, Gauge, generate_latest
from prometheus_client.exposition import CONTENT_TYPE_LATEST


@dataclass(frozen=True)
class MetricsSnapshot:
    active_rooms: float
    websocket_connections: float
    events_per_second: float
    photon_queue_depth: float
    photon_worker_count: float
    photon_dlq_size: float


def _to_float(field_name: str, value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric")
    if isinstance(value, (int, float)):
        return float(value)
    raise ValueError(f"{field_name} must be numeric")


def parse_snapshot(payload: Mapping[str, Any]) -> MetricsSnapshot:
    return MetricsSnapshot(
        active_rooms=_to_float("active_rooms", payload["active_rooms"]),
        websocket_connections=_to_float(
            "websocket_connections", payload["websocket_connections"]
        ),
        events_per_second=_to_float("events_per_second", payload["events_per_second"]),
        photon_queue_depth=_to_float(
            "photon_queue_depth", payload["photon_queue_depth"]
        ),
        photon_worker_count=_to_float(
            "photon_worker_count", payload["photon_worker_count"]
        ),
        photon_dlq_size=_to_float("photon_dlq_size", payload["photon_dlq_size"]),
    )


def read_snapshot(state_file: Path) -> MetricsSnapshot:
    with state_file.open("r", encoding="utf-8") as file_handle:
        payload = json.load(file_handle)
    if not isinstance(payload, dict):
        raise ValueError("state file must contain a JSON object")
    return parse_snapshot(payload)


def create_app(state_file: Path | None = None) -> Flask:
    app = Flask(__name__)
    snapshot_file = state_file or Path(
        os.getenv("GUARDIAN_EXPORTER_STATE_FILE", "/app/state/sample_metrics.json")
    )

    registry = CollectorRegistry()
    gauges = {
        "active_rooms": Gauge(
            "guardian_app_active_rooms",
            "Current active collaborative rooms",
            registry=registry,
        ),
        "websocket_connections": Gauge(
            "guardian_app_websocket_connections",
            "Current open websocket connections",
            registry=registry,
        ),
        "events_per_second": Gauge(
            "guardian_app_events_per_second",
            "Current processed events per second",
            registry=registry,
        ),
        "photon_queue_depth": Gauge(
            "guardian_photon_queue_depth",
            "Current Photon queue depth",
            registry=registry,
        ),
        "photon_worker_count": Gauge(
            "guardian_photon_worker_count",
            "Current Photon worker count",
            registry=registry,
        ),
        "photon_dlq_size": Gauge(
            "guardian_photon_dlq_size",
            "Current Photon dead-letter queue size",
            registry=registry,
        ),
    }

    @app.get("/healthz")
    def healthz() -> Response:
        return jsonify({"status": "ok"})

    @app.get("/metrics")
    def metrics() -> Response:
        snapshot = read_snapshot(snapshot_file)
        gauges["active_rooms"].set(snapshot.active_rooms)
        gauges["websocket_connections"].set(snapshot.websocket_connections)
        gauges["events_per_second"].set(snapshot.events_per_second)
        gauges["photon_queue_depth"].set(snapshot.photon_queue_depth)
        gauges["photon_worker_count"].set(snapshot.photon_worker_count)
        gauges["photon_dlq_size"].set(snapshot.photon_dlq_size)
        return Response(generate_latest(registry), mimetype=CONTENT_TYPE_LATEST)

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("GUARDIAN_EXPORTER_PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
