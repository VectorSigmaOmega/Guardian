# Service down runbook

## Trigger
`TargetDown` alert fired for a monitored instance.

## Response
1. Check host reachability (`ping`/`ssh`) and service status.
2. Restart failed process if restart policy did not recover it.
3. Review recent logs for root cause indicators.

## Recovery criteria
1. `up` metric returns to `1`.
2. Alert transitions to resolved in Alertmanager and Slack.
3. Follow-up action is documented in the postmortem template.
