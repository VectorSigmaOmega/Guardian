# MTTR methodology and record

## Method

1. Trigger representative failure (`scripts/induce-cpu-spike.sh`).
2. Record timestamps:
   - failure injected
   - alert firing
   - remediation start
   - remediation completion
   - alert resolved
3. Compare manual baseline run to automated remediation run.

## Baseline vs automated

| Scenario | Detection (s) | Recovery (s) | Notes |
|---|---:|---:|---|
| Manual baseline | TBD | TBD | Fill after first drill |
| Automated runbook | TBD | TBD | Fill after first drill |

