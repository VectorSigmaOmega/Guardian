# Guardian — Deployment Guide

## 1. Scope

This document describes the current, working setup and deployment path for Guardian as it runs today.

Guardian is deployed with Ansible. The control plane runs on one VPS with Docker Compose. Monitored hosts run `node_exporter` and the custom Python exporter as system services.

## 2. Current operating model

- Deployment is manual from an SSH-capable operator machine.
- GitHub-hosted Actions are not the active deployment path because they cannot currently reach the fleet over SSH.
- The control plane renders Prometheus file-based service discovery targets from Ansible inventory.
- Adding or removing hosts is an inventory change followed by an Ansible run.

## 3. Inventory model

The fleet is defined in `ansible/inventory/hosts.ini`.

Current shape:

```ini
[control_plane]
guardian-control ansible_host=<CONTROL_PLANE_IP> ansible_user=<DEPLOY_USER>

[monitored_fleet]
photon-host ansible_host=<PHOTON_IP> ansible_user=<DEPLOY_USER> guardian_role=photon node_exporter_port=9100 python_exporter_port=8000
guardian-host ansible_host=<GUARDIAN_IP> ansible_user=<DEPLOY_USER> guardian_role=guardian node_exporter_port=9100 python_exporter_port=8001
drill-host ansible_host=<DRILL_IP> ansible_user=<DEPLOY_USER> guardian_role=drill node_exporter_port=9100 python_exporter_port=8000
```

Host lifecycle:

1. add host details to inventory
2. ensure SSH access works from the Ansible runner
3. run the playbook
4. verify Prometheus targets

## 4. Host prerequisites

Each monitored host needs:

- SSH reachable from the Ansible runner
- Python installed
- a deploy user with the required sudo rights
- `22/tcp` open for SSH
- exporter ports reachable from the control plane only:
  - `9100/tcp` for `node_exporter`
  - `8000/tcp` or the configured custom exporter port

Recommended hardening:

- key-only SSH
- `PermitRootLogin no`
- `PasswordAuthentication no`
- `ufw`
- `fail2ban`
- `unattended-upgrades`

The control-plane VPS also needs:

- DNS records for `grafana.<domain>` and `webhook.<domain>`
- `80/tcp` and `443/tcp` open publicly

## 5. Secrets and runtime configuration

Ansible expects these values in the deploy runner environment:

- `SLACK_WEBHOOK_URL`
- `SLACK_CHANNEL`
- `GRAFANA_ADMIN_PASSWORD`
- `WEBHOOK_INTERNAL_TOKEN`
- `GUARDIAN_HMAC_SECRET`
- `GRAFANA_HOST`
- `WEBHOOK_HOST`

At deploy time, the control-plane role writes them to:

- `/opt/guardian/.env`

with permissions:

- `0600`

The drill remediation path also copies the shared deploy SSH key to:

- `/opt/guardian/secrets/ssh/guardian_deploy_ed25519`

That key is used only by the webhook runbook path that remediates the drill host.

## 6. Manual deploy

Validate syntax:

```bash
uv run --with ansible-core ansible-playbook --syntax-check -i ansible/inventory/hosts.ini ansible/site.yml
```

Generic deploy:

```bash
uv run --with ansible-core ansible-playbook --private-key ~/.ssh/guardian_deploy_ed25519 -i ansible/inventory/hosts.ini ansible/site.yml
```

Current live operator workflow:

```bash
set -a
source <(ssh guardian-skyserver 'sudo cat /opt/guardian/.env')
set +a
uv run --with ansible-core ansible-playbook --private-key ~/.ssh/guardian_deploy_ed25519 -i ansible/inventory/hosts.ini ansible/site.yml
```

## 7. What the playbook does

For monitored hosts:

- installs common packages
- installs `stress-ng` on hosts with `guardian_role=drill`
- installs and enables `node_exporter`
- installs and enables the custom Python exporter

For the control plane:

- installs Docker and Compose
- copies `docker-compose.yml`, `Caddyfile`, Prometheus config, Grafana config, webhook code, and exporter code to `/opt/guardian`
- renders `/opt/guardian/.env`
- renders Prometheus service discovery files from inventory
- renders Alertmanager config
- starts or updates the stack with:
  - `docker compose up -d --build`

## 8. Verification after deploy

Check public endpoints:

- `https://grafana.guardian.abhinash.dev/`
- `https://webhook.guardian.abhinash.dev/remediate`

Check Prometheus targets from the control plane:

```bash
ssh guardian-skyserver "curl -sf http://localhost:9090/api/v1/targets | jq -r '.data.activeTargets[] | select(.labels.job==\"fleet-node-exporter\" or .labels.job==\"fleet-python-exporter\") | [.labels.job,.labels.instance,.health] | @tsv'"
```

Expected result:

- all active targets report `up`

Check control-plane containers:

```bash
ssh guardian-skyserver "cd /opt/guardian && sudo docker compose ps"
```

## 9. Drill preparation

The CPU drill path depends on:

- `stress-ng` installed on `drill-host`
- `HighCPU` alert loaded in Prometheus
- webhook runbook `stop-cpu-stress.sh`
- webhook container SSH access to the drill host

Trigger the drill:

```bash
scripts/induce-cpu-spike.sh drill-skyserver 180
```

The current remediation path for `HighCPU` is intentionally restricted to the configured drill host. It kills `stress-ng` and refuses non-drill hosts.

## 10. CI and GitHub Actions

Current state:

- CI can be used for lint and tests
- deploy is not the default GitHub-hosted path

Prepared repository settings for a future self-hosted or otherwise network-reachable runner:

Secrets:

- `ANSIBLE_SSH_PRIVATE_KEY`
- `ANSIBLE_KNOWN_HOSTS`
- `SLACK_WEBHOOK_URL`
- `GRAFANA_ADMIN_PASSWORD`
- `WEBHOOK_INTERNAL_TOKEN`
- `GUARDIAN_HMAC_SECRET`

Variables:

- `SLACK_CHANNEL`
- `GRAFANA_HOST`
- `WEBHOOK_HOST`

## 11. Known current limitation

- `collaborate-host` is parked because its public scrape path is not stable from the control plane.
- Re-enable it only after moving it behind a stable route, tunnel, or private path.
