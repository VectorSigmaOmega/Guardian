# Guardian — Agent Brief

This document is the working agreement for building Guardian. `docs/PRD.md` and `docs/ARCHITECTURE.md` remain the primary source of truth. This brief makes the build executable by freezing implementation assumptions that were previously implicit.

## 1. Project Goal

Build `Guardian` as a live, reviewer-readable systems project that demonstrates:

- fleet configuration management with Ansible
- production-style monitoring with Prometheus, Alertmanager, and Grafana
- incident automation through alert-triggered remediation

The goal is not to build a general-purpose monitoring product. Do not add features just because they are interesting.

## 2. Hard Constraints

- Prioritise `DevOps/SRE systems signal` over product breadth.
- Prioritise `boring, defensible implementation` over architectural novelty.
- Deployment target: `one 4 GB self-managed control-plane VPS + three monitored Linux hosts`.
- Public demo target: `public Grafana over HTTPS`, plus a recorded drill showing alert to remediation to recovery.
- Do not introduce scope creep unless the current plan has a concrete technical flaw.
- If the plan must change, make the smallest change that unblocks delivery and record why in `docs/decisions/`.

## 3. Project Positioning

`Guardian` should look like `a disciplined DevOps/SRE systems project with real operational thinking`, not `a half-productized startup dashboard or an overbuilt observability lab`.

One-paragraph story:

> Guardian is a small but real monitoring and auto-remediation platform for a mixed Linux fleet. It configures hosts with Ansible, scrapes system and application metrics with Prometheus, alerts through Alertmanager to Slack, and auto-remediates one whitelisted failure class through a signed webhook and runbook. The project is built to be understandable in a short review and defensible in a technical interview.

Showcased capabilities:

- operational observability and alerting
- repeatable fleet configuration and deployment
- safe, auditable remediation automation

## 4. Scope

### In Scope

- a single control-plane VM running Prometheus, Alertmanager, Grafana, remediation webhook, and Caddy via `docker-compose`
- monitoring at least three Linux hosts with `node_exporter` plus a custom Python exporter
- at least one end-to-end drill: metric breach -> alert notification -> webhook -> runbook -> recovery
- public read-only Grafana over HTTPS
- CI covering lint, exporter tests, and Ansible lint
- SLO, MTTR documentation, one runbook, and one postmortem template

### Explicitly Out of Scope

- a custom Guardian web console or Next.js app
- Loki and Promtail for MVP
- managed Kubernetes
- multi-region, HA, federation, or scale-out observability
- accounts, billing, or product auth systems

If a tempting feature does not appear In Scope, treat it as Out of Scope.

## 5. Demo Policy

- Auth: `no public signup`; public Grafana viewer only for selected dashboards; admin access stays private
- Rate limits: `webhook endpoint limited and HMAC-signed`; public surface kept to Grafana and remediation webhook only
- Data retention: `Prometheus local retention around 15 days`; no long-term storage in MVP
- Safety controls: `runbook whitelist`, bounded input validation on webhook payloads, SSH key-only access, minimal exposed ports

The public review experience, in order:

1. open the README and understand the system in under 10 minutes
2. open the live Grafana URL and see real host and application metrics
3. view the demo GIF showing the alert and remediation loop

Keep the demo simple and low-friction. No sign-up.

## 6. Architecture

Detail lives in `docs/ARCHITECTURE.md`. This brief freezes only:

- Architectural pattern: `single control-plane VM monitoring a small mixed-host fleet`
- Primary language(s): `Python for exporter and webhook, YAML for config and infrastructure`
- Orchestrator / runtime: `docker-compose on the control-plane host`
- Data store(s): `Prometheus TSDB`; no separate relational database in MVP

Implementation assumptions now frozen:

- Control plane spec: `4 GB RAM minimum`
- Control plane host: `new self-managed VPS`
- Chaos host: `AWS Lightsail small instance`
- Existing monitored hosts: `Collaborate host` and `SwiftBatch host` are real pre-existing workloads
- Networking assumption: `mixed-provider public internet with SSH hardening and firewalling`, not a shared private VPC across all hosts

Any deviation from these requires a decision note in `docs/decisions/`.

## 7. Software Engineering Practices

- Twelve-factor configuration: environment variables for deploy-specific settings; no secrets in repo.
- One module per concern; no god-files.
- Errors are surfaced and logged at boundaries, not swallowed.
- Comments explain why, not what.
- No dead code, placeholder TODOs, or fake integrations.
- Public behavior stays stable once documented.

## 8. Tests

- Unit tests for exporter parsing/collection logic and remediation webhook logic.
- At least one integration path proving the primary alert/remediation flow.
- Tests run in CI on every push.
- Tests must not depend on the public internet or mutable external state.

## 9. CI/CD

- `ci.yml` and `deploy.yml` remain separate.
- On every push or PR: lint, test, Ansible lint.
- On merge to `main`: deploy via Ansible if deploy automation is in scope for the current phase.
- Deploy credentials live only in CI secret storage.

## 10. Documentation

- `README.md` must include: project summary, architecture diagram, live Grafana URL, demo GIF, local run path, deploy path.
- `docs/PRD.md` and `docs/ARCHITECTURE.md` must stay accurate.
- Meaningful plan changes go into `docs/decisions/`.
- Docs update in the same change as behavior changes.

## 11. Security

- No secrets in git.
- Public endpoints are HTTPS-only.
- Webhook is HMAC-signed and accepts only known alert/runbook mappings.
- SSH is key-only; default deny firewall.
- Expose only the ports required by documented architecture.

## 12. Operations

- Structured logs where practical.
- `/metrics` on exporter and webhook services where feasible.
- Health checks for long-running services.
- Graceful restart/shutdown behavior for service processes.
- Config changes should not require code changes.

## 13. Delivery Order

Build in this order:

1. Guardian repo skeleton and README scaffold
2. local `docker-compose` control-plane stack
3. custom exporter happy path on one host
4. Prometheus scrape and Grafana dashboard happy path
5. alert rules and Slack delivery
6. remediation webhook and one whitelisted runbook
7. Ansible for control-plane and fleet configuration
8. CI/CD
9. documentation polish, architecture diagram, and demo GIF

Do not build optional features before the end-to-end alert/remediation loop works.

## 14. Definition of Done for MVP

MVP is done when all of the following are true:

- a public Grafana dashboard is reachable over HTTPS
- at least three Linux hosts are monitored with both `node_exporter` and the custom Python exporter
- at least one alert path completes Slack notification plus auto-remediation plus recovery
- the control-plane stack runs locally with one command
- the deployed environment matches the documented architecture
- CI validates Ansible, exporter tests, and linting
- README explains local run, deployment, and demo flow
- `docs/PRD.md` and `docs/ARCHITECTURE.md` are accurate
- no dead code, no commented-out branches, no undocumented drift from the source-of-truth docs

If the alert/remediation loop or public Grafana is missing, MVP is not done.

## 15. Instructions for the Next Agent

1. Treat this brief plus `docs/PRD.md` and `docs/ARCHITECTURE.md` as the active contract.
2. Do not widen scope beyond the current project goals.
3. Prefer small, defensible implementation choices.
4. Keep the deployment story provider-simple and Ansible-driven.
5. Keep Loki out of MVP unless the source-of-truth docs are explicitly changed.
6. Do not invent a custom UI or console for Guardian during MVP.
7. Preserve the mixed-host reality: pre-existing workload hosts are monitored as real systems rather than rebuilt for infrastructure purity.
8. If a plan/design detail is vague enough to change implementation meaningfully, stop and force clarification before coding.
9. Optimise for a comprehensible end-to-end demo over extra features.

## 16. Anti-Scope-Creep Rule

If a proposed addition does not materially improve one of these:

- Ansible and operational automation signal
- observability and alerting credibility
- remediation/demo clarity
- deployment reproducibility

then do not build it.

## 17. Failure Mode Watchlist

| Anti-pattern | Correction |
|---|---|
| Adding infrastructure tools that do not fit the chosen providers | Prefer a smaller, honest Ansible-driven deployment story |
| Building Grafana polish before metrics and alerts work | Ship scrape and alert path first |
| Adding Loki because it "looks more complete" | Skip for MVP unless the core flow is already stable |
| Putting control plane on an underpowered host | Keep the 4 GB minimum |
| Co-locating chaos with a real workload host | Keep chaos isolated unless the docs are intentionally changed |
| Treating a monitoring project like a product app | Optimize for operational credibility, not product breadth |
