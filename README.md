# Guardian

Guardian is a monitoring and auto-remediation system for a small Linux fleet.
It demonstrates Prometheus + Alertmanager + Grafana observability, Ansible-driven configuration, and a controlled webhook runbook loop.

## Architecture at a glance

- **Control plane:** Prometheus, Alertmanager, Grafana, remediation webhook, Caddy (TLS ingress) via `docker-compose`.
- **Fleet model:** workload hosts plus a dedicated drill host for safe failure injection.
- **Alert loop:** metric breach -> Alertmanager -> Slack + webhook -> whitelisted runbook -> recovery signal.

Source-of-truth docs:
- `docs/PRD.md`
- `docs/ARCHITECTURE.md`
- `docs/DEPLOYMENT.md`

## Repository layout

```text
ansible/             Fleet and control-plane provisioning playbooks/roles
exporter/            Custom Python exporter service and tests
webhook/             Remediation webhook service, runbooks, tests
prometheus/          Scrape config and alert rules
alertmanager/        Alert routing config
grafana/             Datasource/dashboard provisioning
runbooks/            Human-readable runbooks
scripts/             Drill and operator helper scripts
docs/                PRD, architecture, SLO, MTTR, postmortem template
```

## Local run

1. Copy environment template:
   ```bash
   cp .env.example .env
   ```
   Set `SLACK_WEBHOOK_URL` to your Slack incoming webhook. The Slack destination is configuration, not application state.
2. Start stack:
   ```bash
   docker compose up --build
   ```
3. Access:
   - Prometheus: `http://localhost:9090`
   - Alertmanager: `http://localhost:9093`
   - Grafana (direct): `http://localhost:3000`
   - Grafana via Caddy TLS: `https://grafana.localtest.me`
   - Public remediation endpoint via Caddy TLS: `https://webhook.localtest.me/remediate`

## Build, test, and lint commands

- **Exporter tests:** `uv run --project exporter --extra dev pytest exporter/tests`
- **Webhook tests:** `uv run --project webhook --extra dev pytest webhook/tests`
- **Run one exporter test:** `uv run --project exporter --extra dev pytest exporter/tests/test_app.py::test_metrics_endpoint_emits_expected_metrics`
- **Run one webhook test:** `uv run --project webhook --extra dev pytest webhook/tests/test_webhook.py::test_unknown_alert_returns_400`
- **Python lint:** `uv run --with ruff ruff check exporter webhook`
- **Ansible lint:** `uv run --with ansible-core --with ansible-lint ansible-lint ansible/site.yml`
- **Deploy syntax check:** `uv run --with ansible-core ansible-playbook --syntax-check -i ansible/inventory/hosts.ini ansible/site.yml`

## Deployment path

The full operator guide is in `docs/DEPLOYMENT.md`. The short version is:

1. Configure inventory in `ansible/inventory/hosts.ini`. Adding or removing monitored hosts is an inventory change followed by an Ansible run.
2. Ensure each host has:
   - SSH access from the Ansible runner
   - Python installed
   - a deploy user with the required sudo rights
   - firewall rules allowing the control plane to scrape exporter ports
3. Provide runtime secrets to the Ansible runner. Ansible writes them to `/opt/guardian/.env` on the control-plane VPS with `0600` permissions.
4. Manual deploy is the default operating path. GitHub-hosted runners cannot currently reach the fleet over SSH, so CI deploy remains disabled unless you later introduce a self-hosted or otherwise network-reachable runner.
5. Configure GitHub Actions repository settings if deploys will later run from a self-hosted or otherwise network-reachable runner:
   Secrets:
   `ANSIBLE_SSH_PRIVATE_KEY`, `ANSIBLE_KNOWN_HOSTS`, `SLACK_WEBHOOK_URL`, `GRAFANA_ADMIN_PASSWORD`, `WEBHOOK_INTERNAL_TOKEN`, `GUARDIAN_HMAC_SECRET`
   Variables:
   `SLACK_CHANNEL`, `GRAFANA_HOST`, `WEBHOOK_HOST`
6. Validate playbooks:
   ```bash
   uv run --with ansible-core ansible-playbook --syntax-check -i ansible/inventory/hosts.ini ansible/site.yml
   ```
7. Apply playbook:
   ```bash
   uv run --with ansible-core ansible-playbook -i ansible/inventory/hosts.ini ansible/site.yml
   ```
8. For the current live environment, the operator workflow is:
   ```bash
   set -a
   source <(ssh guardian-skyserver 'sudo cat /opt/guardian/.env')
   set +a
   uv run --with ansible-core ansible-playbook --private-key ~/.ssh/guardian_deploy_ed25519 -i ansible/inventory/hosts.ini ansible/site.yml
   ```

## Demo drill path

Trigger synthetic stress on a target host:

```bash
scripts/induce-cpu-spike.sh <ssh-host> [duration-seconds]
```

Record timings in `docs/MTTR.md` after each drill.

The current live inventory is:
- `guardian-host`
- `swiftbatch-host`
- `drill-host`

`collaborate-host` is intentionally parked until its scrape path is moved behind a stable route or tunnel.
