# Guardian SLOs

## Service-level objectives

- **Control-plane availability:** >= 99% monthly uptime for public Grafana endpoint.
- **Detection latency:** host-down conditions detected in <= 120 seconds.
- **Auto-remediation MTTR target:** <= 180 seconds for whitelisted failure class.

## Measurement

- Uptime measured by external probe (UptimeRobot) against public Grafana URL.
- Detection and recovery timings measured from alert timestamps and remediation completion logs.

