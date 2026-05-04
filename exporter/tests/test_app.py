from pathlib import Path

import pytest
from guardian_exporter.app import create_app, parse_snapshot


def test_parse_snapshot_rejects_non_numeric_value() -> None:
    with pytest.raises(ValueError):
        parse_snapshot(
            {
                "active_rooms": "many",
                "websocket_connections": 10,
                "events_per_second": 1.2,
                "swiftbatch_queue_depth": 5,
                "swiftbatch_worker_count": 2,
                "swiftbatch_dlq_size": 0,
            }
        )


def test_metrics_endpoint_emits_expected_metrics(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    state_file.write_text(
        (
            '{"active_rooms": 7, "websocket_connections": 12, "events_per_second": 3.5, '
            '"swiftbatch_queue_depth": 4, "swiftbatch_worker_count": 2, "swiftbatch_dlq_size": 0}'
        ),
        encoding="utf-8",
    )

    app = create_app(state_file)
    client = app.test_client()
    response = client.get("/metrics")

    assert response.status_code == 200
    body = response.data.decode("utf-8")
    assert "guardian_app_active_rooms 7.0" in body
    assert "guardian_swiftbatch_queue_depth 4.0" in body

