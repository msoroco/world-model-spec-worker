# Handoff: heldout__C394300__LVMC-11-12-100-C__motor_vehicle_driver

The exact text has two clauses: use of the designated two-way left-turn lane is limited to preparing for or making a left turn, and a left turn where that lane is designated must begin from that lane. The eight source-hashed accepted summaries cover centre/outer lane, left/straight travel, and both east/west approaches. No new recording is proposed for this assignment.

## Source-backed equivalence

The centre-left/outer-left pairs in each direction compare the turn-origin clause. The centre-straight/centre-left pairs compare the shared-lane-use clause. Outer-straight cases are applicability negatives. All pairs share the C394300 cell and recorded designated-lane context. Historical labels are scenario expectations, not an independent legal decision.

## Limits and resume

The source inventory exports metadata, not original video or trace bytes. The published records identify synthetic lane designation and intent as authored premises, and do not test continuous behavior between 20 Hz samples. Local operator should independently inspect canonical originals before claiming physical or legal acceptance; retain the accepted historical recordings. No new CPU construction, candidate, diagnostic, or GPU queue item is needed for this existing-evidence disposition.

Run `.venv-cpu/bin/python worker_check.py --assignment heldout__C394300__LVMC-11-12-100-C__motor_vehicle_driver --complete --require-delivery-ready` after the lead writes the batch-level branch matrix, review and queue.

## 2026-11-19 existing-evidence readiness

The eight accepted recording IDs in the frozen evidence inventory each have a source-hashed review fact in `case-plan.json`; every accepted recording is reviewed, with no remaining evidence gap and no new case or comparison. The frozen `branch_coverage.validate_evidence(..., no_capture=True)` passes. The source review covers designated-lane turn origin and restricted centre-lane use in both east and west directions. It preserves the limits of authored designation and intent, original media unavailable to this CPU worker, and 20 Hz sampling. It makes no new physical or legal acceptance claim.

`result.json` now declares `ready` / `existing_evidence`, so this package requests no new capture or GPU queue item. A source-backed `existing_evidence` row with all eight accepted IDs was added to `work/_shared/branch-coverage.json`. The real scoped command `.venv-cpu/bin/python worker_check.py --assignment heldout__C394300__LVMC-11-12-100-C__motor_vehicle_driver --complete --require-delivery-ready` exits 0. Pinned `.venv-cpu/bin/python runtime.py preflight` exits 0 with `cpu_preflight_passed: true` and `simulation_started: false`. The batch still has other partial packages; no aggregate readiness is claimed. No frozen input, runtime, batch or Git operation was performed.

The aggregate rerun `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` exited 1 at frozen `preparation.py:276`: `Preparation acceptance failed: partial/missing packages remain`. This does not revoke the C394300 scoped strict pass; five other assigned packages remain partial.
