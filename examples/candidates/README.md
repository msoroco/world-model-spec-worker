# One case, one primary, one risk-based fallback

This is a schema example, not a completed proof. Keep the existing case ID and primary manifest entry. Add these fields to that entry when original lane-transition evidence may fail:

```json
{
  "candidate_risk": {
    "status": "physical",
    "reason": "The requested lane transition may not complete before final observation"
  },
  "candidates": [{
    "id": "fallback1",
    "construction": "cases/base/fallback1/construction.json",
    "construction_sha256": "SHA256_OF_COMPLETE_FALLBACK_CONSTRUCTION",
    "trigger": {
      "source": "following_samples.jsonl",
      "metric": "destination_lane_reached",
      "failure_condition": "false at final observation"
    },
    "changed_knobs": ["steering_gain: 0.11 to 0.14"],
    "offline": {
      "command": "python3.11 runtime.py offline --manifest ... --case EXACT_ID --candidate fallback1 --output .runtime-work/...",
      "exit_code": 0,
      "construction_sha256": "SAME_SHA256_AS_ABOVE",
      "log": "receipts/fallback1-offline.log",
      "log_sha256": "SHA256_OF_LOG"
    },
    "compatibility": {
      "receipt": "receipts/fallback1-compatibility.json",
      "sha256": "SHA256_OF_RECEIPT",
      "log": "receipts/fallback1-analysis.log",
      "negative_log": "receipts/fallback1-negative.log"
    }
  }]
}
```

Run `runtime.py compatibility-recipe --candidate fallback1` with the same exact case, manifest, library and validator used by the primary. Copy its positive and negative logs and receipt into the named paths, then bind their hashes. The fallback construction keeps the primary law, cell, actor, case, required atoms, source packets, 20 Hz, duration, cameras and recording description. It may change only the declared engineering knob. If a linked comparison shares the controller, prepare the same fallback policy for its other cases. Do not choose a fallback based on legal outcome.

For a case with no concrete physical risk, use `"candidate_risk": {"status": "none", "reason": "specific CPU-supported reason"}` and `"candidates": []`. Do not invent fallbacks to fill a quota.

The local operator runs `runtime.py capture --candidate fallback1` only after the primary's original evidence satisfies the stated failure condition. The attempt stores `candidate-selection.json`; `process-saved` verifies its source hash and selected construction. Both capture attempts remain distinct research evidence until independent acceptance.
