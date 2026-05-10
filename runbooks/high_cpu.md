# High CPU runbook

## Trigger
`HighCPU` alert fired from Prometheus.

## Manual checks
1. Verify sustained CPU pressure from Grafana and node exporter metrics.
2. Identify top CPU-consuming processes on the affected host.
3. Validate whether the host is serving production traffic before remediation.

## Automated action path
`HighCPU` currently alerts only. The temporary drill demo can re-enable webhook runbook `stop-cpu-stress.sh` while a drill host is attached.

## Post-action
1. Confirm CPU returns to baseline.
2. Ensure the resolved notification appears in Slack.
3. Record drill details in `docs/MTTR.md` if this was part of a demo drill.
