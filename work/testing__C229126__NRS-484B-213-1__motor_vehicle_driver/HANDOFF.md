# NRS 484B.213(1), C229126 CPU preparation

Status: partial. The scoped strict gate remains unpassed. No accepted recordings are present in the frozen evidence inventory, and no physical CARLA success is claimed.

The exact statutory text in `inputs/testing__C229126__NRS-484B-213-1__motor_vehicle_driver/assignment.json` controls. The cell is road / overtake_left / other_vehicle for a motor vehicle driver. The witness is conditional because the cell does not itself establish a two-lane two-directional public highway. A reviewed map and original Native sources must establish that geometry, vehicle/driver identity, centerline and both permitted directions.

## Exact case plan

`case-plan.json` has seven exact cases: `clear_free_complete`, `occluded_left`, `oncoming_distant`, `oncoming_close`, `opposite_response`, `overtaken_response`, and `incomplete_pass`, each prefixed by this assignment ID. Five comparisons vary one declared feature: visibility, oncoming distance, opposite vehicle response, overtaken vehicle response, or passing completion. The occluded case calls for a physical opaque roadside blocker, not a Boolean flag. The plan retains the absence of accepted recordings as one source-cited gap. There are zero frozen judgment ranges for this exact law and actor.

No statutory numeric distance, ray cutoff, response magnitude, or passing time is invented. The terms “clearly visible,” “sufficient distance,” and “interfering with the safe operation” remain unresolved judgments. Ray clear distances, body spacing, speeds, movement history and responses are descriptive evidence to retain for later review.

## Implemented and tested

`pass_measure.py` consumes an original-frame Native projection with source hashes and rejects missing frame continuity, actor direction, map qualification and ray evidence. It measures body-side entry, body-clearance return after passing, oncoming station gaps, ray brackets and actor response histories while preserving unresolved judgments. The module is a draft measurement component; no live Native projection or full finalizer is yet bound to it. `comparison_audit.py` checks case order, fixed-condition equality, declared measured difference and missing review flags in saved report inputs. It is a draft protocol: the final auditor must verify those flags and measurements against original saved sources rather than trusting report fields.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C229126__NRS-484B-213-1__motor_vehicle_driver/tests -v` passed nine tests; `cpu-tests.log` is hashed in `result.json`. The pinned `runtime.py verify --runtime runtime` and `runtime.py preflight` logs are retained; preflight reports CPU readiness and no simulation start.

The initial scoped strict command `.venv-cpu/bin/python worker_check.py --assignment testing__C229126__NRS-484B-213-1__motor_vehicle_driver --complete --require-delivery-ready` failed with `Preparation acceptance failed: partial/missing packages remain`, because the result is correctly partial. This is unfinished CPU work, not an external dependency.

## Next CPU actions

1. Bind a reviewed CARLA two-way road source and construct actual ego, overtaken, and oncoming actors, plus an opaque blocker for `occluded_left`. Implement controllers and runtime capture at the common four-camera profile, 20 Hz and declared duration, with source-qualified map, rays, participant histories and frame map.
2. Build seven exact construction/configuration bundles, measurement contracts and case-specific finalizers using sealed original Native sources. Test the controller and geometry with CPU fakes, including both road directions and blocker creation.
3. Author canonical semantic stage proposals and the exact execution manifest, justified physical-risk candidates, saved-only processing commands and source-bound positive/negative compatibility receipts for each selected case and candidate.
4. Implement and CPU-test independent delivery audits that reject missing original evidence, and comparison audits that check fixed conditions as well as the named differences. Add the exact GPU queue proposal for lead integration.
5. Review the original law and definitions again, run focused tests, and repeat the scoped strict gate until it exits zero. Only then mark `result.json` ready.

Actual CARLA motion, visual coverage, physical occlusion and canonical acceptance remain later local checks after CPU preparation.
