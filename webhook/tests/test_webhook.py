import logging
import stat
from pathlib import Path

from app import compute_hmac_signature, create_app


def _make_payload(alert_name: str = "HighCPU") -> dict:
    return {
        "alerts": [
            {
                "labels": {
                    "alertname": alert_name,
                    "instance": "demo-host:9100",
                }
            }
        ]
    }


def test_create_app_requires_secrets(tmp_path: Path, monkeypatch) -> None:
    runbooks_dir = tmp_path / "runbooks"
    runbooks_dir.mkdir()

    monkeypatch.delenv("GUARDIAN_HMAC_SECRET", raising=False)
    monkeypatch.delenv("GUARDIAN_INTERNAL_TOKEN", raising=False)

    try:
        create_app(runbook_map={"HighCPU": "restart.sh"}, runbooks_dir=runbooks_dir)
    except RuntimeError as error:
        assert "GUARDIAN_HMAC_SECRET is required" in str(error)
    else:
        raise AssertionError("create_app should require explicit secrets")


def test_internal_remediation_success(tmp_path: Path, monkeypatch) -> None:
    runbooks_dir = tmp_path / "runbooks"
    runbooks_dir.mkdir()

    script_path = runbooks_dir / "restart.sh"
    script_path.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\necho remediated-$1\n",
        encoding="utf-8",
    )
    script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)

    monkeypatch.setenv("GUARDIAN_HMAC_SECRET", "super-secret")
    monkeypatch.setenv("GUARDIAN_INTERNAL_TOKEN", "internal-token")
    app = create_app(runbook_map={"HighCPU": "restart.sh"}, runbooks_dir=runbooks_dir)
    client = app.test_client()

    response = client.post(
        "/remediate/internal",
        json=_make_payload("HighCPU"),
        headers={"Authorization": "Bearer internal-token"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["exit_code"] == 0
    assert "remediated-demo-host:9100" in body["stdout"]


def test_internal_remediation_logs_success(tmp_path: Path, monkeypatch, caplog) -> None:
    runbooks_dir = tmp_path / "runbooks"
    runbooks_dir.mkdir()

    script_path = runbooks_dir / "restart.sh"
    script_path.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\necho remediated-$1\n",
        encoding="utf-8",
    )
    script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)

    monkeypatch.setenv("GUARDIAN_HMAC_SECRET", "super-secret")
    monkeypatch.setenv("GUARDIAN_INTERNAL_TOKEN", "internal-token")
    app = create_app(runbook_map={"HighCPU": "restart.sh"}, runbooks_dir=runbooks_dir)
    client = app.test_client()

    with caplog.at_level(logging.INFO):
        response = client.post(
            "/remediate/internal",
            json=_make_payload("HighCPU"),
            headers={"Authorization": "Bearer internal-token"},
        )

    assert response.status_code == 200
    assert (
        "Processing remediation alert=HighCPU instance=demo-host:9100 "
        "runbook=restart.sh" in caplog.text
    )
    assert (
        "Remediation completed alert=HighCPU instance=demo-host:9100 "
        "runbook=restart.sh exit_code=0" in caplog.text
    )


def test_unknown_alert_returns_400(tmp_path: Path, monkeypatch) -> None:
    runbooks_dir = tmp_path / "runbooks"
    runbooks_dir.mkdir()

    script_path = runbooks_dir / "restart.sh"
    script_path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)

    monkeypatch.setenv("GUARDIAN_HMAC_SECRET", "super-secret")
    monkeypatch.setenv("GUARDIAN_INTERNAL_TOKEN", "internal-token")
    app = create_app(runbook_map={"HighCPU": "restart.sh"}, runbooks_dir=runbooks_dir)
    client = app.test_client()

    response = client.post(
        "/remediate/internal",
        json=_make_payload("ServiceDown"),
        headers={"Authorization": "Bearer internal-token"},
    )

    assert response.status_code == 400
    assert "no runbook configured" in response.get_json()["error"]


def test_hmac_endpoint_rejects_invalid_signature(tmp_path: Path, monkeypatch) -> None:
    runbooks_dir = tmp_path / "runbooks"
    runbooks_dir.mkdir()

    script_path = runbooks_dir / "restart.sh"
    script_path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)

    monkeypatch.setenv("GUARDIAN_HMAC_SECRET", "super-secret")
    monkeypatch.setenv("GUARDIAN_INTERNAL_TOKEN", "internal-token")
    app = create_app(runbook_map={"HighCPU": "restart.sh"}, runbooks_dir=runbooks_dir)
    client = app.test_client()

    response = client.post(
        "/remediate",
        json=_make_payload("HighCPU"),
        headers={"X-Guardian-Signature": "sha256=invalid"},
    )

    assert response.status_code == 401


def test_hmac_endpoint_accepts_valid_signature(tmp_path: Path, monkeypatch) -> None:
    runbooks_dir = tmp_path / "runbooks"
    runbooks_dir.mkdir()

    script_path = runbooks_dir / "restart.sh"
    script_path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)

    monkeypatch.setenv("GUARDIAN_HMAC_SECRET", "super-secret")
    monkeypatch.setenv("GUARDIAN_INTERNAL_TOKEN", "internal-token")
    app = create_app(runbook_map={"HighCPU": "restart.sh"}, runbooks_dir=runbooks_dir)
    client = app.test_client()

    raw = (
        b'{"alerts":[{"labels":{"alertname":"HighCPU","instance":"demo-host:9100"}}]}'
    )
    signature = compute_hmac_signature(raw, "super-secret")

    response = client.post(
        "/remediate",
        data=raw,
        headers={"Content-Type": "application/json", "X-Guardian-Signature": signature},
    )

    assert response.status_code == 200


def test_resolved_alert_is_ignored_without_running_runbook(
    tmp_path: Path, monkeypatch
) -> None:
    runbooks_dir = tmp_path / "runbooks"
    runbooks_dir.mkdir()

    script_path = runbooks_dir / "restart.sh"
    marker = tmp_path / "ran"
    script_path.write_text(
        f"#!/usr/bin/env bash\nset -euo pipefail\ntouch {marker}\n",
        encoding="utf-8",
    )
    script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)

    monkeypatch.setenv("GUARDIAN_HMAC_SECRET", "super-secret")
    monkeypatch.setenv("GUARDIAN_INTERNAL_TOKEN", "internal-token")
    app = create_app(runbook_map={"HighCPU": "restart.sh"}, runbooks_dir=runbooks_dir)
    client = app.test_client()

    payload = _make_payload("HighCPU")
    payload["alerts"][0]["status"] = "resolved"

    response = client.post(
        "/remediate/internal",
        json=payload,
        headers={"Authorization": "Bearer internal-token"},
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "ignored"
    assert not marker.exists()
