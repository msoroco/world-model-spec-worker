# Full statutory branch preparation

The deliverable is a complete finite plan and executable comparisons for all 22 laws, not one capability case per law. Read inputs/coverage/branch-sources.json: every topic must appear in a branch. The topic inventory is a source checklist, not an exhaustive semantic decomposition: independently read the full law and definitions, split alternatives and exceptions, and add every branch needed. Do not turn engineering measurements into legal thresholds.

Write work/_shared/branch-coverage.json:

```json
{
  "format": "worker-full-branch-coverage-v1",
  "batch_id": "demo-test-full-branches-v7",
  "additional_bindings": [],
  "laws": {
    "LAW_ID": {
      "branches": [{
        "branch_id": "LAW_ID-approach-position",
        "topic_ids": ["text-0", "text-1"],
        "status": "runnable",
        "assignment_id": "testing__CELL__LAW_ID__motor_vehicle_driver",
        "case_ids": ["ASSIGNMENT__near_centerline", "ASSIGNMENT__farther_from_centerline"],
        "comparison_ids": ["approach_lateral_position"]
      }]
    }
  }
}
```

Use actual IDs and topic keys. Every runnable branch needs two or more exact cases and a controlled comparison. Reuse a reference within multiple comparisons explicitly; do not create redundant recordings. For 400-2a, hold connected two-directional geometry, left turn and downstream policy fixed while varying measured approach body position. For 400-2b, vary measured departure body position with the approach fixed. Do not invent a lawful lateral cutoff. For 257-1, enumerate stop/yield, each stopping-reference hierarchy branch, occupied/approaching traffic, across-or-within history, and governing-control exceptions. Keep incompatible controls in separate catalog cells only when necessary.

Default to the original law/cell assignment for all compatible branches. New scene variants are not new cells. If a fixed layout, maneuver, control or actor cannot support a branch, inspect inputs/coverage/candidate-cells.json. Prefer an existing compatible testing cell, or an unused candidate if a new allocation is necessary. Reject cells allocated to full-train or held-out. Write an additional_bindings row with assignment_id, original_assignment_id, original_cell_incompatibility and binding_reason. Add work/<new-assignment-id>/assignment.json with exact catalog cell identity, role testing, the same law, branch, summary and source_observation_terms. All usual executable package checks apply to it. Do not modify frozen inputs or batch.json.

Each assignment's case-plan.json must contain every exact case and nonempty comparisons. Every comparison has comparison_id, case_ids, fixed_conditions and deliberate_differences. Cover every case in the shared branch matrix. Every requirement disposition in a ready v7 package must have status selected_required and include case_ids to identify the cases to which it applies; retain its global disposition_index in each relevant measurement contract. Every nonbaseline case has its own inline construction, exact offline proof, positive/negative compatibility recipe and manifest entry. Root runner.py/config.json/construction.json may be the first case; additional exact bundles belong under cases/. Root config.supported_case_ids lists all cases. Keep a common camera/duration contract within linked comparisons.

Update 004 adds risk-based alternatives inside each existing manifest case. Add `candidate_risk` with `status: none|physical` and a concrete `reason`. For `none`, use an empty `candidates` list. For `physical`, provide one or two `fallback1`/`fallback2` entries containing a complete construction path/hash, a trigger with `source`, `metric`, and `failure_condition`, a list of `changed_knobs`, an exact offline receipt, and a positive/negative compatibility receipt with its analysis and negative log hashes. Keep config law/cell/actor/case, required atoms, source packets, 20 Hz, duration, cameras and recording description equal to the primary. A fallback may tune spawn or controller engineering without changing the comparison variable. If it changes a shared controller policy, make the same candidate available to every linked case. The primary remains the default. `runtime.py capture --candidate fallback1` writes a candidate-selection receipt; saved processing verifies it. Select candidates by the stated physical trigger, never by desired legal outcome. The lead's independent branch review must include `candidate_review_method` and `unreviewed_candidates: []`.

Every manifest entry needs post_capture with recorded_only: true, command, feedback_command, test_log, test_log_sha256 and test_exit_code: 0. Bind a fixture test that actually executes the saved-only processing path. Reuse runtime.py process-saved --manifest PATH --case ID --attempt PATH --output PATH --library PATH --validator PATH. It never runs CARLA. It validates saved acquisition, runs the finalizer, converter, renderer and decoding, and writes feedback.json on failure. Supply case-specific additional physical/pixel audits and comparison audits, with CPU tests. Do not claim canonical or legal acceptance from this software proof. Return the exact ordered GPU queue and postprocessing commands for all cases.

A genuine unsupported branch uses status capability_blocked with blocker_receipt and blocker_sha256. The JSON receipt must contain tested_limitation and commands/log hashes. A missing cell binding, missing implementation, or lack of a GPU is not a capability blocker. The strict ready gate fails while any capability blocker remains.

After all four partition owners finish, a separate review pass reads the original law texts and definitions independently, checks omitted alternatives and exceptions, cell reuse, measurement rules and comparison isolation. Write work/_shared/branch-review.json with coverage_sha256, review_method and missing_branches: [] only if none are missing. The gate checks structure and source joins; this semantic review is mandatory.

Report planned recording counts, explicit reuses, complete/pending branches and exact failures. Keep branch planned, Native executed, video/Core accepted and comparison complete distinct. Push the configured return branch. The local operator will validate and apply any scope extension, import/freeze the code, then run the exact GPU queue.

Exact statutory text controls over summaries. Reject any summary that turns an engineering epsilon, duration, time-to-conflict or numeric spacing into an unsupported legal definition. Keep measurements and legal judgments separate.
