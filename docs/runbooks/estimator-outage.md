# Runbook: the estimator service is down or answering from the fallback

**Signal.**
- `dpe_fallbacks` rising in `/metrics`, or
- `source: "fallback"` / `"rule_of_thumb"` in responses, or
- readiness failing.

**What the hubs see.** The planner still gets answers: the last-known-good table, or the rule of thumb. Expect
more late deliveries if the fallback lasts into a peak.

1. **Is a model loaded?** Check `GET /health`.
   - `model: null` means the init container could not fetch `@champion`.
   - Check MLflow reachability and the workload identity's access to the storage account.
2. **Are pods crash-looping?** Run `kubectl -n estimators logs deploy/estimator-api`.
   - A bundle that fails to load means the last promotion is broken. Move the `champion` alias back to the
     previous version in MLflow and restart the deployment.
3. **Is it latency?** Check `dpe_latency_seconds_p95` and the HPA. Scale out if CPU is saturated.
4. **After recovery,** note the window. The day's coverage numbers are not comparable.
