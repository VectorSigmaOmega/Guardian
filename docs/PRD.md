# Guardian — Product Requirements Document

## 1. Overview

Guardian is an automated infrastructure monitoring platform that observes a small fleet of Linux hosts, alerts on anomalies, and auto-remediates a defined set of failure classes via webhook-triggered runbooks.

This is a focused engineering demonstration, not a product. Its purpose is to demonstrate DevOps and SRE competence through a concise repository review and live system. It will not be commercialised, will not acquire users, and will not be extended into a general-purpose monitoring solution.

## 2. Primary Goal

Produce a single GitHub repository plus a public live demo that conveys:

- production-style observability (Prometheus, Alertmanager, Grafana)
- configuration management at fleet scale (Ansible)
- incident automation (alert → webhook → runbook → recovery)
- operational maturity signals (SLOs, runbooks, postmortem template)

Secondary goal: signal backend competence for non-DevOps roles via the custom Python exporter and the optional remediation webhook service.

## 3. Personas

The repository is read by two audiences. Both must succeed.

| Persona | Time spent | Needs |
|---|---|---|
| Engineering manager / quick reviewer | 60–600 s | README clarity, architecture diagram, live link, demo GIF, healthy folder structure |
| Senior engineer / interviewer | 10–30 min | Code quality, defensible decisions, evidence of tradeoff awareness |

## 4. Goals (Measurable)

| ID | Goal |
|---|---|
| G1 | Public Grafana dashboard URL reachable ≥99% of the calendar month. |
| G2 | At least one custom Python exporter exposes ≥3 application-level metrics that are not duplicates of `node_exporter`. |
| G3 | At least one alert path completes the loop: metric → Slack alert → webhook → bash runbook → recovery. |
| G4 | MTTR for the demonstrated failure class is documented with a measured baseline-vs-automated comparison and methodology. |
| G5 | Repository contains populated `ansible/`, `.github/workflows/`, and operational configuration directories with non-trivial content. |
| G6 | README, architecture diagram, and demo GIF together let a non-expert reviewer understand the system in under 10 minutes. |

## 5. Non-Goals

The following are explicitly out of scope and will not be added regardless of how interesting they appear during the build:

- multi-tenant monitoring
- a custom rule engine (Prometheus rules are sufficient)
- a proprietary alert UI (Grafana + Alertmanager UI suffice)
- machine-learning anomaly detection
- log aggregation beyond an optional minimal Loki/Promtail addition
- managed Kubernetes
- multi-region deployment
- mobile applications
- billing, subscriptions, or accounts
- arbitrary user-authored runbook DSL (bash + a whitelist is sufficient)
- dashboard-driven host management or Slack settings (configuration is changed through Ansible inventory, environment variables, and redeploy)

## 6. Functional Requirements

### FR1 — Monitored Fleet
The MVP shall monitor at least three hosts:
- one host running a real workload (the deployed Collaborate whiteboard service)
- one host running a representative workload (Photon demo or stub)
- one dedicated drill host that can be stressed on demand for drills

The current live build runs `guardian-host`, `photon-host`, and `drill-host`. Hosts are managed through Ansible inventory and Prometheus file-based service discovery so hosts can be added or removed after deployment without code changes.

### FR2 — Metrics Collection
Each monitored host shall expose:
- `node_exporter` system metrics
- a custom Python exporter exposing application-level metrics

The control plane shall scrape both via Prometheus.

### FR3 — Alerting
The system shall:
- evaluate alert rules in Prometheus
- route alerts via Alertmanager
- deliver alerts to a configurable Slack channel with diagnostic context

### FR4 — Auto-Remediation
The system shall:
- accept Alertmanager webhook callbacks at a remediation service
- execute a whitelisted bash runbook keyed by `alertname`
- record execution outcome for operator review

### FR5 — Public Dashboard
The system shall expose a read-only public Grafana view of fleet health over HTTPS.

### FR6 — Drill Capability
The system shall provide a documented mechanism (script or endpoint) to inject a representative failure for demo purposes.

### FR7 — Self-Monitoring
The system shall monitor itself: a `Watchdog` heartbeat alert, a meta-alert for any DOWN target lasting >2 min, and an external uptime check on the public Grafana URL.

## 7. Non-Functional Requirements

| ID | Requirement | Target |
|---|---|---|
| NFR1 | Control-plane availability | ≥99% monthly |
| NFR2 | Monthly hosting cost | ≤ USD 20 |
| NFR3 | First contentful render of public Grafana | ≤ 3 s on residential broadband |
| NFR4 | Mean time to detect a host-down condition | ≤ 120 s |
| NFR5 | Mean time to recovery for the auto-remediated class | ≤ 180 s |
| NFR6 | Public surface area | only Grafana viewer + remediation webhook (HMAC-signed) |
| NFR7 | Secrets storage | no secrets in repo; provided via environment or `ansible-vault` |
| NFR8 | Reproducibility | system rebuildable from a bare cloud account in ≤ 30 minutes |

## 8. Out of Scope (Hard No)

The following will not be implemented, even as stretch goals:

- arbitrary user-defined alert rules through the dashboard
- non-Linux monitoring targets
- Windows agents
- payment or billing
- per-host RBAC beyond Grafana viewer/admin
- a custom orchestrator beyond `docker-compose` on the control plane

## 9. Success Criteria

The project is considered successful if a reviewer clicking the repository link can, within 10 minutes:

1. understand what the system does from the README
2. reach the live Grafana dashboard
3. find a demo GIF showing the alert → remediation loop
4. observe `ansible/`, `.github/workflows/`, monitoring config, and runbooks with non-trivial content
5. open one runbook and one alert rule and find them legible

## 10. Definition of Done (MVP)

MVP is complete when **all** of the following are true:

- three monitored hosts are configured and monitored according to the documented architecture
- `node_exporter` and the custom Python exporter are installed via Ansible on the fleet
- Prometheus scrapes all targets; UP for ≥24 h continuous
- ≥3 alert rules are defined; ≥1 fires on demand and resolves on recovery
- Slack receives the alert with diagnostic context
- auto-remediation runs at least one whitelisted runbook end-to-end
- public Grafana URL is reachable with TLS
- README contains: overview, architecture diagram, live URL, demo GIF, run instructions
- one runbook (`runbooks/`), one SLO statement (`docs/SLO.md`), one postmortem template (`docs/POSTMORTEM_TEMPLATE.md`) exist
- GitHub Actions or an equivalent automated CI path runs lint, exporter unit tests, and `ansible-lint`
- MTTR comparison (manual baseline vs automated) is documented with methodology in `docs/MTTR.md`

If any of the above is missing, the MVP is not done — no exceptions.

## 11. Open Questions

| # | Question | Default until decided |
|---|---|---|
| OQ1 | Hosting: Oracle Cloud free tier vs Lightsail vs Hetzner | Resolved: control plane on a self-managed VPS, with workload hosts plus a dedicated drill host in the monitored fleet |
| OQ2 | Is the Guardian Console (Next.js) in scope? | No — post-MVP only, after DoD met |
| OQ3 | Add Loki + Promtail for unified logs? | Yes if NFR1 is comfortably met; otherwise post-MVP |

Open questions are resolved by editing this PRD and recording the decision in `docs/decisions/`. `OQ1` is no longer open and remains here only as a recorded resolved decision.

## 12. Out-of-Scope Backlog (deliberately deferred)

Items the author finds tempting but has chosen not to build during MVP. They live here so they cannot be smuggled in mid-build:

- Guardian Console (Next.js portal with GitHub OAuth and RBAC)
- dashboard settings for adding/removing hosts or changing Slack connections
- email + PagerDuty alert routes
- multi-environment (staging vs prod) Prometheus federation
- on-call rotation tooling
- custom Grafana plugin

If any of these is built, it must be after the MVP DoD is met **and** must not regress any DoD item.
