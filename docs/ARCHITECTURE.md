# Guardian — Architecture

## 1. Scope of this document

This document describes **how** Guardian is built. For **what** it does and **why**, see `PRD.md`. For the working agreement governing how the build is executed, see `AGENT_BRIEF.md`.

## 2. High-Level Topology

```
┌────────────────────── MONITORED FLEET ──────────────────────┐
│                                                             │
│  VM-A: Collaborate (existing workload host)                 │
│        node_exporter + custom_py_exporter                   │
│          (active rooms, ws connections, events/s)           │
│                                                             │
│  VM-B: SwiftBatch demo stack (existing workload host)       │
│        node_exporter + custom_py_exporter                   │
│          (queue depth, worker count, DLQ size)              │
│                                                             │
│  VM-C: Synthetic chaos host (AWS Lightsail)                 │
│        node_exporter + stress-ng (on demand)                │
│                                                             │
└──────────────────────────────┬──────────────────────────────┘
                               │ scrape (HTTPS / public internet with firewalling)
                               ▼
┌──────────────────── CONTROL PLANE VM ───────────────────────┐
│                                                             │
│   Prometheus ──► Alertmanager ──► Slack #guardian-alerts    │
│        │                │                                   │
│        │                ▼                                   │
│        │        remediation-webhook (Flask, HMAC)           │
│        │                │                                   │
│        ▼                ▼                                   │
│     Grafana       SSH → bash runbook → diagnostic capture   │
│   (public RO)                                               │
│                                                             │
│   Caddy (ingress + auto-TLS)                                │
│   Loki + Promtail  (optional, post-MVP)                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                               ▲
                               │
            UptimeRobot (external) pings public Grafana URL
```

## 3. Components

### 3.1 Control Plane (single VM)

| Component | Purpose | Notes |
|---|---|---|
| Prometheus | Time-series DB, scrape orchestrator, rule evaluator | 15 s scrape, 15 d retention |
| Alertmanager | Alert routing, grouping, inhibition | Routes to Slack and remediation webhook |
| Grafana | Dashboarding | Anonymous role disabled; public viewer org for selected dashboards |
| remediation-webhook | Receives Alertmanager webhooks, executes runbooks | Python Flask, HMAC-verified, runbook whitelist |
| Caddy | Ingress + automatic TLS | Two-line config per virtual host |
| Loki + Promtail (optional) | Unified logs view | Added only if NFR1 comfortable |

All control-plane services run via `docker-compose` on a single VM.

The control-plane host is a new self-managed VPS with a minimum target of `4 GB RAM`.

### 3.2 Monitored Fleet (MVP target: ≥3 VMs)

| Component | Purpose |
|---|---|
| `node_exporter` | Standard system metrics (CPU, memory, disk, network) |
| Custom Python exporter (`prom_client`) | Application-level metrics, one per workload |

Per-host exporter responsibilities:

- **Collaborate host** — active rooms, websocket connections, events per second, room age distribution.
- **SwiftBatch host** — queue depth, worker count, DLQ size, processing-duration histogram.
- **Chaos host** — synthetic counters; primary purpose is being a stress target.

The current build can operate with the two existing workload hosts while the chaos host is pending. The MVP is not done until the chaos host is added and monitored. Adding or removing monitored hosts is an inventory/configuration operation: update `ansible/inventory/hosts.ini`, run Ansible, and Prometheus consumes the rendered file-based service discovery targets.

### 3.3 Out-of-band

| Service | Purpose |
|---|---|
| Slack incoming webhook | Alert delivery to the configured alert channel |
| GitHub Actions | CI for exporter + lint, deploy via `ansible-playbook` on merge to main |
| UptimeRobot (free tier) | External liveness check on public Grafana URL |
| DNS provider | Records for `grafana.<domain>`, `webhook.<domain>` |

## 4. Data Flow

### 4.1 Normal scrape cycle

1. Prometheus issues `GET /metrics` to each target every 15 s.
2. Targets respond with current values (pull model — no agent push).
3. Prometheus persists samples to local TSDB.
4. Grafana queries Prometheus on user dashboard view.

### 4.2 Alert lifecycle

1. Prometheus rule evaluator detects threshold breach for the configured `for:` duration.
2. Alert state transitions to `firing`; Prometheus pushes to Alertmanager.
3. Alertmanager applies routing tree:
   - all alerts → Slack
   - firing alerts in `auto_remediable` group → internal remediation webhook
4. Public remediation requests are HMAC-verified; Alertmanager reaches the internal remediation route over the Docker network with a bearer token.
5. Webhook looks up `alertname` in the runbook map; rejects unknown names with `400`.
6. Bash runbook executes (typically: SSH to target → action → capture diagnostic).
7. Webhook records and returns execution outcome for operator review.
8. Resolution: when the metric returns to healthy, Alertmanager sends a resolved notification to Slack. Resolved notifications do not execute remediation runbooks.

### 4.3 Drill (failure injection)

1. Operator runs `scripts/induce-cpu-spike.sh <host>`.
2. `stress-ng` runs on the chaos host; CPU metric crosses threshold.
3. Standard alert lifecycle (4.2) triggers.
4. Demo GIF captures the loop end-to-end.

## 5. Tech Decisions (with rationale)

| Decision | Choice | Rationale |
|---|---|---|
| Time-series DB | Prometheus | Industry standard; matches resume; pull model fits VM fleet |
| Metric exporter language | Python (`prom_client`) | Resume claim; readable; sufficient at this scale |
| Alert routing | Alertmanager | Native routing, grouping, inhibition, and generic webhook delivery |
| Auto-remediation | Custom Flask webhook + Bash | Transparent; whitelisted; trivial to read in interview |
| Ingress | Caddy | Auto-TLS in 2 lines; demonstrates breadth (Nginx is on Collaborate) |
| Configuration | Ansible | Industry standard; idempotent; SSH-only — no agent install |
| Container orchestrator | `docker-compose` (control plane) | k3s adds complexity without portfolio benefit; SwiftBatch already covers k8s |
| Hosting (control plane) | Self-managed VPS | Predictable low cost; simplest path for a dedicated 4 GB control plane |
| Hosting (chaos host) | AWS Lightsail | Small, cheap, and already available in the current account setup |
| Hosting (existing monitored hosts) | Reused existing Collaborate and SwiftBatch servers | Real workloads are more valuable than synthetic stand-ins |
| CI/CD | GitHub Actions | Free for public repos; widely understood |

Rejected alternatives are recorded in `docs/decisions/` when relevant.

## 6. Deployment Model

### 6.1 Bootstrap

```
ansible/  →  ansible-playbook -i inventory site.yml
              ├── installs node_exporter on fleet
              ├── installs custom Python exporter on fleet
              ├── deploys docker-compose stack on control plane
              └── installs Caddy with TLS config
```

### 6.2 Updates

- **Control-plane apps** — `docker-compose pull && up -d`, orchestrated by Ansible.
- **Exporter code** — GitHub Actions runs the playbook against fleet on merge to `main`.
- **Fleet membership** — adding/removing hosts is done by editing Ansible inventory and rerunning the playbook; the control-plane role renders Prometheus file-based service discovery target files.

The full system is reproducible from a bare cloud account in ≤30 minutes (NFR8).

## 7. Security Model

### 7.1 Network

- SSH: key-only, no password auth.
- Control plane reaches fleet over the public internet with SSH hardening, restricted firewall rules, and key-only access. Mixed-provider private networking is not assumed for MVP.
- Public surface is exactly two endpoints:
  - `grafana.<domain>` — HTTPS, viewer org for public dashboards, login required for non-public.
  - `webhook.<domain>/remediate` — HTTPS, HMAC signature required.
- Internal remediation endpoint `/remediate/internal` is reachable only inside the Docker network and is not proxied by Caddy.

### 7.2 Secrets

- Slack webhook URL, HMAC key, Grafana admin password, SSH private keys — all sourced from environment at runtime; never committed. Slack channel/workspace is changed by updating configuration and redeploying, not through an application settings UI.
- `ansible-vault` for any encrypted-at-rest values that must live in repo.
- GitHub Actions secrets for CI deploy credentials.

### 7.3 TLS

- Managed end-to-end by Caddy; auto-renewed.
- HSTS enabled on both public hosts.

### 7.4 Threat model

Documented separately in `docs/SECURITY.md` (post-MVP). Single-line summary: a hostile internet visitor cannot mutate state through any public surface.

## 8. Self-Observability

Guardian monitors itself:

- Prometheus self-scrape (`job: prometheus`).
- `Watchdog` alert fires continuously when Alertmanager is healthy. Absence of `Watchdog` for 5 min indicates Alertmanager itself is down.
- Meta-alert fires if any scrape target has been DOWN for >2 min.
- UptimeRobot pings public Grafana every 5 min and notifies the operator through Slack/email if it goes down.

## 9. Failure Modes

| Failure | Detection | Mitigation |
|---|---|---|
| Control-plane VM down | UptimeRobot ping fails | External notification; documented re-bootstrap takes ≤30 min |
| Slack webhook unreachable | Alertmanager logs | Alerts retried; second route is post-MVP |
| Runbook script fails | Webhook records non-zero exit | Operator investigates; alert remains firing until resolution |
| Prometheus disk fills | `node_exporter` disk alert (self-monitoring) | Retention reduced; TSDB pruned |
| Exporter exposes new metric | n/a | Backwards-compatible by Prometheus's data model |
| Free tier suspended | UptimeRobot ping fails | Recreate the chaos host on a fallback provider and reapply Ansible inventory/playbooks; documented in README |

## 10. Capacity Limits (by design)

| Dimension | Limit |
|---|---|
| Targets | ≤ 20 hosts (single Prometheus node) |
| Ingest | < 10 000 samples/sec |
| Retention | 15 days local; no long-term storage |
| Alert rules | ≤ 50 (manageable by one operator) |

Beyond these, the system is intentionally not designed to scale. Scaling would require Thanos / Cortex / federation and is explicitly out of scope (see PRD §5).

## 11. Out of Scope (Architectural)

Reaffirmed here because architecture is where these decisions get tested under pressure:

- no high availability — a single control-plane VM is acceptable for a portfolio demo
- no horizontal scaling of Prometheus
- no service mesh
- no multi-cluster federation
- no managed services beyond GitHub, Slack, UptimeRobot, the DNS provider, and the chosen IaaS

## 12. Repository Layout

```
guardian/
  docs/
    PRD.md
    ARCHITECTURE.md
    SLO.md
    MTTR.md
    POSTMORTEM_TEMPLATE.md
    decisions/
  ansible/
    inventory
    site.yml
    roles/
      common/
      node_exporter/
      python_exporter/
      control_plane/
  exporter/
    pyproject.toml
    guardian_exporter/
    tests/
  webhook/
    app.py
    runbooks/
    tests/
  prometheus/
    prometheus.yml
    rules/
  alertmanager/
    alertmanager.yml
  grafana/
    dashboards/
    provisioning/
  runbooks/
    high_cpu.md
    service_down.md
  scripts/
    induce-cpu-spike.sh
  .github/workflows/
    ci.yml
    deploy.yml
  docker-compose.yml
  Caddyfile
  README.md
```

This layout is the contract. Adding a new top-level directory requires a decision note in `docs/decisions/`.
