# training__C245490__NRS-484B-413-2__motor_vehicle_driver

Status: partial. No selected delivery case, accepted recording or legal verdict is claimed.

## Source and scope

NRS 484B.413(2): A signal of intention to turn right or left, or otherwise turn a vehicle from a direct course, shall be given continuously during not less than the last 100 feet traveled in a business or residential district and not less than the last 300 feet traveled in any other area prior to changing the course of a vehicle. This rule shall be observed, regardless of the weather.

Cell: same_direction_multilane / change_lane / lane_marking; actor: motor_vehicle_driver. Frozen witness count: 1. Membership rows: {'full-train': 6}. Membership alone does not prove coverage or reuse. Exact source and topic hashes are in `case-plan.json`.

## Exact boundary comparisons

The 90/100/110-foot cases form one requested business/residential boundary comparison; 290/300/310 feet form a separate requested other-area boundary comparison. Geometry, same-direction lane change, cameras, requested clear weather and 20 Hz remain fixed within each triple. Requested area class is not an original legal classification. Original area evidence remains a requirement before any legal conclusion. The saved measurement integrates observed pose steps over the last uninterrupted observed signal interval before the lane-history-derived crossing. Requested settings are not measured results.

## Blockers and resumption

Twelve draft exact inline constructions are present: the two distance triples plus 100- and 300-foot interruption, rain and rightward lane-change contrasts. These variants are separate same-cell comparisons against the respective at-distance case. The cases are not selected, and no Native recording or public compatibility acceptance is claimed. Next CPU work: exact manifest and semantic proposals, exact offline and public positive/missing-source-negative compatibility proof per case, recorded-only pipeline, source-bound lifecycle and independent delivery/comparison audits, then scoped strict. Actual area classification, visible signal pixels and legal judgment remain pending original source review. Set `ready` / `delivery_prepared` only after exact scoped strict passes.

## Current CPU construction checkpoint

`measure_signal.py` now implements a saved-sample measurement of continuous signal distance before one observed course-change event. It rejects missing or reordered frames, 20 Hz time gaps, missing poses or indicator states, left-censored onset, and absent course-change events. An off or opposite-direction indicator resets continuity. `signal-measurement-contract.json` states the original-source requirements, 100/300-foot area branches, 30-second capture requirement, and independent area/course-change checks. These are source-shaped measurement software, not original Native evidence.

`prove_signal_measure.py` exited 0. `signal-measurement-cpu.log` SHA-256 is `6a02e3beacce5f206f44def15c0a38767d841208b0d82d4182d63fda98ef6342`; it records six synthetic distance probes, two interruption probes, eight clear/rain left/right invariance probes, and six negative-source checks. `signal_scene.py` has a 300 m two-lane OpenDRIVE request and 600-frame controller plan. `native_capture.py` retains original post-tick signal, pose, lane identity, full-body vertices, Core trace/evidence, four FFV1 camera streams and a frame map; `finalize.py` joins those saved sources and rejects disagreement between signal course-change flags and lane history. `build_selected.py` materialized twelve draft bundles; `runner.py --check --bundle DIR` exited 0 on each. Four `test_signal_scene.py` tests passed. All twelve source-hashed synthetic recipes ran through the current runtime fixture and the saved-only finalizer under `.runtime-work/`. Measured diagnostic distances were 90/100/110 and 290/300/310 feet, 85.8/285.4 feet for the interrupted variants, and unchanged at-distance results in rain/right variants. All twelve diagnostic physical checks reported lane transition met with `synthetic_fixture` provenance; this does not establish real motion. Removing `signal-source.jsonl` from a copy of the fixture caused finalization to fail with `Missing original source: signal-source.jsonl`. `.venv-cpu/bin/python -B worker_check.py --assignment training__C245490__NRS-484B-413-2__motor_vehicle_driver --complete` exited 0 for the partial package. Native capture remains unexecuted and public compatibility and strict selected proofs remain pending. Do not promote from this checkpoint.
