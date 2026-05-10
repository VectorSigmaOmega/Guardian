from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, request
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest
from prometheus_client.exposition import CONTENT_TYPE_LATEST

DEFAULT_BASE_DIR = Path(__file__).resolve().parent
LOG_FIELD_LIMIT = 200


def compute_hmac_signature(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_hmac_signature(body: bytes, received_signature: str | None, secret: str) -> bool:
    if received_signature is None:
        return False
    expected = compute_hmac_signature(body, secret)
    return hmac.compare_digest(expected, received_signature)


def require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        raise RuntimeError(f"{name} is required")
    return value


def load_runbook_map(runbook_map_path: Path) -> dict[str, str]:
    with runbook_map_path.open("r", encoding="utf-8") as file_handle:
        payload = json.load(file_handle)
    if not isinstance(payload, dict):
        raise ValueError("runbook map must be a JSON object")
    typed_payload: dict[str, str] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("runbook map keys and values must be strings")
        typed_payload[key] = value
    return typed_payload


def extract_alert(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    alerts = payload.get("alerts")
    if not isinstance(alerts, list) or not alerts:
        raise ValueError("payload must include at least one alert")
    first = alerts[0]
    if not isinstance(first, dict):
        raise ValueError("alert entry must be an object")
    return first


def resolve_runbook_path(runbooks_dir: Path, relative_script: str) -> Path:
    candidate = (runbooks_dir / relative_script).resolve()
    root = runbooks_dir.resolve()
    if root not in candidate.parents and candidate != root:
        raise ValueError("runbook path escapes runbooks directory")
    return candidate


def execute_runbook(
    script_path: Path,
    instance: str,
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(script_path), instance],
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )


def truncate_for_log(value: str, limit: int = LOG_FIELD_LIMIT) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]}..."


def create_app(
    runbook_map: dict[str, str] | None = None,
    runbooks_dir: Path | None = None,
    *,
    hmac_secret: str | None = None,
    internal_token: str | None = None,
) -> Flask:
    app = Flask(__name__)
    app.logger.setLevel(logging.INFO)

    runbook_map_path = Path(
        os.getenv(
            "GUARDIAN_RUNBOOK_MAP",
            str(DEFAULT_BASE_DIR / "config" / "runbook_map.json"),
        )
    )
    configured_runbooks_dir = runbooks_dir or Path(
        os.getenv("GUARDIAN_RUNBOOKS_DIR", str(DEFAULT_BASE_DIR / "runbooks"))
    )
    effective_runbook_map = runbook_map or load_runbook_map(runbook_map_path)
    effective_hmac_secret = hmac_secret or require_env("GUARDIAN_HMAC_SECRET")
    effective_internal_token = internal_token or require_env("GUARDIAN_INTERNAL_TOKEN")
    timeout_seconds = int(os.getenv("GUARDIAN_RUNBOOK_TIMEOUT_SECONDS", "60"))

    registry = CollectorRegistry()
    request_counter = Counter(
        "guardian_webhook_requests_total",
        "Total remediation webhook requests",
        ["endpoint", "outcome"],
        registry=registry,
    )
    duration_histogram = Histogram(
        "guardian_webhook_runbook_duration_seconds",
        "Runbook execution duration in seconds",
        registry=registry,
    )

    def process_payload(payload: Mapping[str, Any]) -> tuple[dict[str, Any], int]:
        try:
            alert = extract_alert(payload)
        except ValueError as error:
            return {"error": str(error)}, 400

        alert_status = alert.get("status", payload.get("status"))
        if alert_status == "resolved":
            return {"status": "ignored", "reason": "resolved alert"}, 200

        labels = alert.get("labels")
        if not isinstance(labels, dict):
            return {"error": "alert labels are required"}, 400

        alert_name = labels.get("alertname")
        if not isinstance(alert_name, str):
            return {"error": "alertname label is required"}, 400

        runbook_name = effective_runbook_map.get(alert_name)
        if runbook_name is None:
            return {"error": f"no runbook configured for alert {alert_name}"}, 400

        try:
            script_path = resolve_runbook_path(configured_runbooks_dir, runbook_name)
        except ValueError as error:
            return {"error": str(error)}, 400

        if not script_path.is_file():
            return {"error": f"configured runbook not found: {runbook_name}"}, 400

        instance = labels.get("instance")
        target_instance = instance if isinstance(instance, str) else "unknown-instance"

        app.logger.info(
            "Processing remediation alert=%s instance=%s runbook=%s",
            alert_name,
            target_instance,
            runbook_name,
        )

        with duration_histogram.time():
            result = execute_runbook(script_path, target_instance, timeout_seconds)

        body = {
            "alertname": alert_name,
            "instance": target_instance,
            "runbook": runbook_name,
            "exit_code": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }

        if result.returncode == 0:
            app.logger.info(
                (
                    "Remediation completed alert=%s instance=%s runbook=%s "
                    "exit_code=%s stdout=%r stderr=%r"
                ),
                alert_name,
                target_instance,
                runbook_name,
                result.returncode,
                truncate_for_log(body["stdout"]),
                truncate_for_log(body["stderr"]),
            )
            return body, 200
        app.logger.warning(
            (
                "Remediation failed alert=%s instance=%s runbook=%s "
                "exit_code=%s stdout=%r stderr=%r"
            ),
            alert_name,
            target_instance,
            runbook_name,
            result.returncode,
            truncate_for_log(body["stdout"]),
            truncate_for_log(body["stderr"]),
        )
        return body, 502

    @app.get("/healthz")
    def healthz() -> Response:
        return jsonify({"status": "ok"})

    @app.get("/metrics")
    def metrics() -> Response:
        return Response(generate_latest(registry), mimetype=CONTENT_TYPE_LATEST)

    @app.post("/remediate")
    def remediate_hmac() -> Response:
        body = request.get_data()
        signature = request.headers.get("X-Guardian-Signature")
        if not verify_hmac_signature(body, signature, effective_hmac_secret):
            request_counter.labels(endpoint="hmac", outcome="unauthorized").inc()
            return jsonify({"error": "invalid signature"}), 401

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            request_counter.labels(endpoint="hmac", outcome="invalid").inc()
            return jsonify({"error": "invalid JSON payload"}), 400

        result_body, status = process_payload(payload)
        outcome = "success" if status == 200 else "error"
        request_counter.labels(endpoint="hmac", outcome=outcome).inc()
        return jsonify(result_body), status

    @app.post("/remediate/internal")
    def remediate_internal() -> Response:
        auth_header = request.headers.get("Authorization", "")
        if auth_header != f"Bearer {effective_internal_token}":
            request_counter.labels(endpoint="internal", outcome="unauthorized").inc()
            return jsonify({"error": "unauthorized"}), 401

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            request_counter.labels(endpoint="internal", outcome="invalid").inc()
            return jsonify({"error": "invalid JSON payload"}), 400

        result_body, status = process_payload(payload)
        outcome = "success" if status == 200 else "error"
        request_counter.labels(endpoint="internal", outcome=outcome).inc()
        return jsonify(result_body), status

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000)
