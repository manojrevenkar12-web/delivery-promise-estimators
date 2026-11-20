# Runbook: the weekly challenger was not promoted

**Signal.** `promoted: false` in the training job's `gate.json`, and the `champion` alias did not move.

1. **Read the pinball losses** in the run. A small regression (2–5%) on a single quiet week is common. Leave the
   champion and wait for next week.
2. **If the challenger loses badly,** check the training rows (`rows_*` metrics). Missing days in the lake make a
   thin training set.
3. **If the champion is getting old** (more than three weeks without a promotion), look at drift and coverage
   before forcing anything. A forced promotion bypasses the only check between training and the planner.
