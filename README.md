# Guardian

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Prometheus](https://img.shields.io/badge/Prometheus-Observability-E6522C?logo=prometheus&logoColor=white)](https://prometheus.io/)
[![Grafana](https://img.shields.io/badge/Grafana-Dashboards-F46800?logo=grafana&logoColor=white)](https://grafana.com/)
[![Alertmanager](https://img.shields.io/badge/Alertmanager-Alerting-E6522C?logo=prometheus&logoColor=white)](https://prometheus.io/docs/alerting/latest/alertmanager/)
[![Ansible](https://img.shields.io/badge/Ansible-Config%20Management-EE0000?logo=ansible&logoColor=white)](https://www.ansible.com/)
[![Docker](https://img.shields.io/badge/Docker-Self--Hosted-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Deploy](https://img.shields.io/badge/Deploy-Manual-6C757D)](#deployment)
[![Live Grafana](https://img.shields.io/badge/Live-Grafana-0A7CFF)](https://grafana.guardian.abhinash.dev/)

Guardian is a monitoring and auto-remediation platform for a Linux fleet. It combines Prometheus, Alertmanager, Grafana, Ansible, and controlled webhook runbooks to detect unhealthy conditions, notify operators, and execute bounded recovery actions.

<img width="1840" height="899" alt="Screenshot 2026-05-10 160257" src="https://github.com/user-attachments/assets/c491b701-d0d2-4d52-8080-35743affade1" />


## Live Links

- Public Grafana: `https://grafana.guardian.abhinash.dev/`
- Architecture: `docs/ARCHITECTURE.md`
- Deployment guide: `docs/DEPLOYMENT.md`
- Product scope: `docs/PRD.md`

## What Guardian Does

- Collects host-level and application-level metrics from a Linux fleet.
- Uses Prometheus and Alertmanager for rule evaluation and routing.
- Sends alerts to Slack and a remediation webhook.
- Executes whitelisted runbooks for safe, bounded recovery actions.
- Uses Ansible for inventory-driven host onboarding and control-plane rollout.

## How It Works

1. `node_exporter` and the custom Python exporter expose host and application metrics.
2. Prometheus scrapes those metrics and evaluates alert rules.
3. Alertmanager routes alerts to Slack and, when allowed, to the remediation webhook.
4. The webhook selects a mapped runbook and executes it against the intended target.
5. Grafana shows the fleet before, during, and after recovery.

## Demo Flow

Guardian includes a controlled failure-injection path for demonstration and validation:

1. A drill host is placed under sustained synthetic CPU load with `stress-ng`.
2. The `HighCPU` alert fires after the configured hold period.
3. Alertmanager sends the event to Slack and the remediation webhook.
4. The webhook runs a drill-safe runbook that stops the synthetic load.
5. CPU usage returns to normal and the alert clears.

The current `HighCPU` remediation is intentionally scoped to a drill-safe host and stops synthetic `stress-ng`. In a real workload, the same pipeline would invoke a host-role-specific recovery action instead of a generic process kill.

## Local Run

1. Copy the environment template:
   ```bash
   cp .env.example .env
   ```
2. Set `SLACK_WEBHOOK_URL` in `.env`.
3. Start the stack:
   ```bash
   docker compose up --build
   ```
4. Access the local services:
   - Prometheus: `http://localhost:9090`
   - Alertmanager: `http://localhost:9093`
   - Grafana (direct): `http://localhost:3000`
   - Grafana via Caddy TLS: `https://grafana.localtest.me`
   - Webhook via Caddy TLS: `https://webhook.localtest.me/remediate`

## Test and Validation

Run local checks from the repo root:

- Exporter tests: `uv run --project exporter --extra dev pytest exporter/tests`
- Webhook tests: `uv run --project webhook --extra dev pytest webhook/tests`
- Python lint: `uv run --with ruff ruff check exporter webhook`
- Ansible lint: `uv run --with ansible-core --with ansible-lint ansible-lint ansible/site.yml`
- Playbook syntax check: `uv run --with ansible-core ansible-playbook --syntax-check -i ansible/inventory/hosts.ini ansible/site.yml`

Subproject `uv.lock` files are intentionally not tracked. Use `uv run --project ...` instead of creating committed per-subproject lockfiles.

## Deployment

Guardian is currently deployed manually with Ansible. Inventory is the source of truth for monitored hosts and control-plane rollout.

Short version:

1. Configure `ansible/inventory/hosts.ini`.
2. Ensure target hosts have SSH access, Python, and the required sudo permissions.
3. Provide runtime secrets to the Ansible runner.
4. Validate the playbook:
   ```bash
   uv run --with ansible-core ansible-playbook --syntax-check -i ansible/inventory/hosts.ini ansible/site.yml
   ```
5. Apply the deployment:
   ```bash
   uv run --with ansible-core ansible-playbook -i ansible/inventory/hosts.ini ansible/site.yml
   ```

The full operator workflow, runtime variable requirements, and live deploy procedure are documented in `docs/DEPLOYMENT.md`.

## Repository Layout

```text
ansible/             Fleet and control-plane provisioning playbooks/roles
exporter/            Custom Python exporter service and tests
webhook/             Remediation webhook service, runbooks, tests
prometheus/          Scrape config and alert rules
alertmanager/        Alert routing config
grafana/             Datasource and dashboard provisioning
runbooks/            Human-readable runbooks
scripts/             Drill and operator helper scripts
docs/                PRD, architecture, deployment, SLO, MTTR, postmortem template
```

## Documentation

- `docs/PRD.md` for scope and functional requirements
- `docs/ARCHITECTURE.md` for system design and data flow
- `docs/DEPLOYMENT.md` for setup and operator workflow
- `docs/SLO.md` for service-level targets
- `docs/MTTR.md` for drill timing and recovery measurements
- `docs/POSTMORTEM_TEMPLATE.md` for incident writeups
