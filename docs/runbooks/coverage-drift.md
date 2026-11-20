# Runbook: drift alarm (actuals above the served percentile too often)

**Signal.** Two consecutive days with stop or travel coverage more than 10 points under the served percentile.

**What happens automatically.** The service retrains daily for five days, and each challenger must pass the gate.

1. **Which estimate drifted?** Compare stop coverage and travel coverage.
   - Travel only, concentrated in some zones: usually road works, a closure or an event. Check the zone pairs.
   - Stops only: a new building type, a change in the driver app's stop logging, or a new hub layout.
2. **Is it the data, not the world?** Check log volumes per day. A half-empty log day looks like drift.
3. **If daily retrains keep failing the gate,** look at the gate detail in MLflow (`gate.json`).
   - The champion may genuinely still be better.
   - Or the validation day is unrepresentative (a holiday).
4. **Tell the hubs** if a known change, such as road works, will last. Operations may want to widen promises in
   those zones.
