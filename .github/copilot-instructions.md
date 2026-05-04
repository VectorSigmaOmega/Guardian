# Copilot instructions for Guardian

## Build, test, and lint commands

- **Start local stack:** `docker compose up --build`
- **Validate compose config:** `docker compose config --quiet`
- **Run exporter tests only:** `uv run --project exporter --extra dev pytest exporter/tests`
- **Run webhook tests only:** `uv run --project webhook --extra dev pytest webhook/tests`
- **Run a single exporter test:** `uv run --project exporter --extra dev pytest exporter/tests/test_app.py::test_metrics_endpoint_emits_expected_metrics`
- **Run a single webhook test:** `uv run --project webhook --extra dev pytest webhook/tests/test_webhook.py::test_unknown_alert_returns_400`
- **Python lint:** `uv run --with ruff ruff check exporter webhook`
- **Ansible syntax check:** `uv run --with ansible-core ansible-playbook --syntax-check -i ansible/inventory/hosts.ini ansible/site.yml`
- **Ansible lint:** `uv run --with ansible-core --with ansible-lint ansible-lint ansible/site.yml`

## High-level architecture

Treat these files as source of truth:

1. `docs/PRD.md` (what/why/scope)
2. `docs/ARCHITECTURE.md` (how/system design)
3. `docs/AGENT_BRIEF.md` (execution constraints and frozen assumptions)

Target architecture (from docs) is:

- A **single control-plane VM** (minimum 4 GB RAM) running `docker-compose` services: Prometheus, Alertmanager, Grafana, remediation webhook (Flask), and Caddy for TLS.
- A **small monitored Linux fleet** (at least 3 hosts): existing workload hosts plus one chaos host.
- Metrics collection via `node_exporter` + custom Python exporter(s), scraped by Prometheus.
- Alert flow: Prometheus rule breach -> Alertmanager routing -> Slack; firing auto-remediable alerts also call the internal webhook -> mapped whitelisted runbook -> remediation result recorded for operator review.
- Public demo surface is intentionally small: read-only Grafana over HTTPS plus the signed remediation webhook endpoint.
- Deployment/provisioning is Ansible-driven (`ansible-playbook -i ansible/inventory/hosts.ini ansible/site.yml`), with control-plane updates via `docker-compose` orchestrated by Ansible.

## Key project-specific conventions

- This is a **portfolio-focused MVP**, not a product. Optimize for a clear, defensible end-to-end monitoring/remediation demo over feature breadth.
- Respect strict scope boundaries in `docs/PRD.md` and `docs/AGENT_BRIEF.md` (for example: no custom Guardian web console in MVP, no managed Kubernetes, no HA/federation work).
- Keep changes **small and boring** unless a larger change is required for correctness.
- If a meaningful plan/design change is needed, record it in `docs/decisions/` and keep docs updated in the same change.
- Do not introduce secrets into the repository; use runtime environment variables, `ansible-vault`, and CI secret storage.
- Preserve the documented deployment reality: mixed-provider hosts over public internet with SSH hardening/firewalling (not a shared private VPC assumption).
- Follow the documented delivery order: establish end-to-end alert/remediation loop first, then polish.
- If ambiguity would materially change implementation, stop and clarify before coding.
