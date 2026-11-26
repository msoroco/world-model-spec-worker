# C150116 current handoff — 2026-11-25

## 2026-11-25 independent audit closure checkpoint

`selected_audit.py` now reopens all seven selected diagnostic construction bundles, exact SHA-bound compatibility receipts, offline logs, recorded-only saved logs and three-state physical/lifecycle fixtures. It independently checks the selected 20 Hz, 45-second, four-camera profile and all four planned diagnostic comparisons, including fixed scene, regulation and clock fields. `selected-audit.json` SHA-256 `83c7f7703f624874edf82afa20488703567a4614ccff6f6173a0c4e8cea1882f` records seven selected integrity reports and four comparison checks, explicitly `original_source_verified=false` and `physical_acceptance=false`. `execution-manifest.json` binds this report, script and passing test log; current manifest SHA-256 is `33337f3c1d788d8b62ada450d99d59897e8e0e08f52ced4576a13bd4ec9c2c50`.

`delivery_audit.py comparisons` now takes an exact seven-case original-attempt index and independently audits each original attempt before comparing; caller-supplied report dictionaries are not accepted by its CLI. `comparison-audit-plan.json` SHA-256 `18a7b3b8ce3b24b01d60f14c7e7ae3dc0789256f64aeb121401ced2cfa637da4` names one source-bound command for each of the four planned comparisons. The original case command and comparison command both reject absent original attempts; the comparison negative log contains `original attempt missing` and is bound in the manifest. No positive original audit is claimed.

Focused suite `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C150116__NRS-484B-503__motor_vehicle_driver/tests -v` exited 0 with 27 tests; `cpu-selected-audit-tests.log` SHA-256 `c703f12dae012c104071fb09422ab92029885d71a245f3e6333f9247d72d3fc3`. It includes stale selected construction, compatibility and physical hashes; missing selected case/comparison; missing declared difference; and changed fixed comparison variable. Scoped `worker_check.py --assignment ... --complete` exited 0. Direct selected execution-manifest validator exits 1 exactly at `Expand sweeps with the main implementation before manifest generation` (`cpu-nov25-selected-validator.log`). Exact scoped strict gate exits 1 at `Preparation acceptance failed: partial/missing packages remain` (`cpu-nov25-scoped-strict.log`). These are current source-dependent gaps, and the result remains partial.

Direct pinned semantic-delivery validation passed, as did candidate and physical-preparation validation for all seven exact selected cases; `cpu-direct-stages.log` SHA-256 `8234558caeb7551dcb43ad1e13cd3b49e012ef28986ea87be0d917d1361aca69`. Final scoped static check passed after the manifest/result update. The assignment tree has 262 UTF-8 files, each under 2 MiB, with no trailing whitespace, blank EOF or conflict markers. The next source-dependent step is to seal the seven original attempts, expand the three sweeps from reviewed sources, run every positive original delivery/comparison command, and then rerun the exact strict assignment gate. No ready status or shared queue entry is authorized by these diagnostic receipts.

Status: **partial; source-gated selected diagnostic package**. Exact assignment `testing__C150116__NRS-484B-503__motor_vehicle_driver`; selected manifest SHA-256 `a2e54ce57898a1a4a24b743272ec019b2f9175d8469f95c529d0f71d304a7218`. No original Native attempt, legal disposition, physical success or accepted recording is claimed.

Seven exact selected cases and four controlled comparisons cover stop/stand/park without passenger activity, prompt loading/unloading, delayed loading, and parking outside effective hours. The law's exception is **expeditious passenger loading or unloading**; one and twelve seconds are engineering probes, never legal cutoffs. The outside-hours case controls activation and is not asserted to satisfy the effective-hours branch. The hours comparison permits a different sourced civil time/site hash but requires the road, zone, regulation authority, four-camera plan and blueprints to remain fixed. `delivery_audit.py` independently checks original source hashes, 900-frame history, saved finalizer bytes and all four decoded camera streams before comparing cases; its CLI rejects diagnostic attempts.

## Current CPU receipts

- `build_diagnostic_bundles.py` authored seven exact synthetic-only constructions; pinned `runtime.py offline` passed 7/7. `build_runtime_compatibility.py` added source-specific 900-frame zone/event recipes and seven measurement contracts. Pinned `runtime.py compatibility` passed positive selected measurement, missing `zone-rows.json` negative, Native schema, current Core decoder and four-camera render/decode for all seven primary cases. Receipts are under `proofs/selected-*` and selected offline logs are `cpu-nov25-selected-offline-*.log`.
- `build_semantic_draft.py` produced relevance, exact-quote template/exception, three judgment observable proposals, binding and seven cases. Direct `worker_exchange.semantic_delivery.validate` passed 8 stages and 7 selected cases; `proposals/semantic-index.json` SHA-256 `6e30a8163dd2bc3be0f47b202118feee9ba8ca50ecfa87532000e170a46ac222`.
- Seven selected-hash synthetic `runtime.py process-saved` replays passed recorded-only with no physical/legal acceptance; `post_capture` proof logs are `cpu-nov25-saved-*.log`. `prove_physical_diagnostic.py` generated three-state motion and ordered lifecycle proof for every case; direct pinned `physical_preparation.validate` passed 7/7.
- One uniform `fallback1` moves the synthetic passenger anchor 0.5 m toward the curb only if original four-view frames fail to show marked zone, stopped ego and passenger interaction together. The source-gated fallback is available across all linked cases. Pinned fallback offline and positive/negative compatibility passed 7/7; receipts under `proofs/fallback1-*`. Direct `candidate_constructions.validate` passed 7/7. Isolation test verifies every other bundled file and scene fact is fixed.
- Focused suite: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C150116__NRS-484B-503__motor_vehicle_driver/tests -v`, exit 0, 19 tests; `cpu-tests.log` is bound in `result.json`. `original_runner.py` rejects diagnostic site provenance before adapter actions; `finalize_saved.py` and `saved_audit.py` remain source-bound to closed 900-frame original history.

## Exact remaining gate and source acquisition

Direct pinned `execution_manifest.validate` currently fails `Expand sweeps with the main implementation before manifest generation`. Three qualitative sweeps remain incomplete in `proposals/cases.json`: expeditious passenger loading/unloading, actual marked passenger curb designation/pose, and applicable regulation effective hours. `inputs/<assignment>/evidence.json` lists zero accepted original recordings and the supplied judgment range inventory has zero entries. Do not turn the synthetic `zone-rows.json`, borrowed Native graph/video fixture, requested passenger action or engineering delay into a reviewed original or a legal standard.

To resume, acquire a reviewed original C150116 one-way road/map readback and approach route; source-hashed marked passenger curb polygon, curb adjacency, parking pose and passenger anchor; vehicle/passenger blueprints; jurisdiction-specific applicable regulation and effective-hours source; synchronized civil clock/timezone; original actor/control/event source packets; and 900 contiguous original frames from four synchronized 20 Hz cameras. A reviewed original site manifest is required by `original_runner.py`; a closed original Native source manifest, saved history/seal/result and four camera bytes are required by `delivery_audit.py`. Expand qualitative sweeps only from documented physical feasibility and reviewed range/landmark sources, then replace diagnostic-only selected analyzer/runner with source-bound original capture/finalization, run production positive/negative delivery audits, rebind receipts and run the exact scoped strict command. Actual CARLA motion/visibility and canonical acceptance remain later local checks.

Exact scoped `.venv-cpu/bin/python worker_check.py --assignment testing__C150116__NRS-484B-503__motor_vehicle_driver --complete` exited 0; exact scoped `--complete --require-delivery-ready` exited 1 at `Preparation acceptance failed: partial/missing packages remain`, consistent with the truthful partial result. Direct selected validator supplies the deeper source gate above.

`result.json` remains partial. No queue row is authorized. Scratch, temporary videos and decoder outputs reside only under `.runtime-work/c150116/`.

## Prior checkpoints

# testing__C150116__NRS-484B-503__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.503 — A person shall not stop, stand or park a vehicle for any purpose or period of time except for the expeditious loading or unloading of passengers in any place marked as a passenger curb loading zone during hours when the regulations applicable to such passenger curb loading zone are effective.
Assigned branch(es): Parking in an effective passenger curb loading zone.
Cell: C150116 (one_way_road, park, loading_zone_marking); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C150116__NRS-484B-503__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 worker construction checkpoint

The frozen evidence inventory has zero recordings. `case-plan.json` now specifies seven exact cases: `stop_no_passenger`, `stand_no_passenger`, `park_no_passenger`, `load_prompt`, `unload_prompt`, `load_delayed`, and `park_outside_hours`, each prefixed by the exact assignment ID. Four controlled comparisons cover conduct, passenger activity, release timing and effective hours. The outside-hours case is a condition control, not asserted to satisfy the effective-hours branch. No numeric legal duration cutoff is inferred from the word expeditious.

`passenger_zone.py` validates one-way map readback, source-hashed marked passenger curb polygon and curb adjacency, vehicle/passenger blueprints, applicable regulation, jurisdiction, civil time and timezone before spawning. It commands an ego route and passenger action and cleans up owned actors on failure. `measure_history` requires 900 original contiguous frames and checks actor/source continuity, measured in-zone halt frames and source-backed boarding/alighting events. `saved_audit.py` independently checks the sealed original-history digest, frame join, zone/regulation source and event provenance. `audit_pair` rejects changed fixed sources and missing deliberate differences. These measurements are evidence for later review; they neither decide legal compliance nor prove physical visibility.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C150116__NRS-484B-503__motor_vehicle_driver/tests -v` passed 9 tests; log `cpu-tests.log` SHA-256 `a984a9b3ccc0579ced474267af4e24629dab6101d1d83184222168b76bb6b592`. Negative tests reject wrong zone designation, missing boundary source, wrong effective-hours readback, actor changes, missing event source, frame tampering, stale digest and changed comparison site.

Next CPU work: bind an actual source-backed C150116 Native site and applicable civil-time regulation; implement the exact runner, capture/finalizer, semantic proposals and every manifest/candidate and compatibility/post-capture receipt; complete independent four-camera and comparison acceptance audits. Run exact assignment strict gate after those proofs. Actual zone marking, motion and visibility remain later physical checks. Status remains partial.

### Saved-only finalization extension

`finalize_saved.py --history PATH --site PATH --seal PATH --output PATH` now joins a hash-sealed closed original history to a source-hashed site and case ID, invokes the independent history auditor and 900-frame measurement, then writes an atomic JSON measurement. It rejects stale site/history bytes before output. The fixture test exercises the finalizer and both stale-byte negatives; it is not an actual Native capture. The complete focused suite passes 11 tests, retained in `cpu-tests.log` SHA-256 `8b8ebe417b3049463e3e63fe0e8969746c1aada1f67abc92712823e2298aa57c`. The earlier 9-test hash in this report is an intermediate checkpoint; `result.json` names the current suite.
