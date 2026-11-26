# C230211 protected pavement handoff

Status: partial. The exact scoped strict delivery gate has not passed.

Seven selected cases and six comparisons cover barrier across, barrier around, bypass, warning person, warning sign, highway closed sign, and the active same-pavement employee exception. The frozen inventory has no accepted Native recordings. Actual pavement condition, warning effect, employee activity, vehicle motion, and four-view pixels require original GPU capture and independent review.

## Construction

`runner.py` accepts only an exact reviewed site with source-hashed map, jurisdiction, driver, vehicle, pavement, warning geometry and placement time, route, employment, and work activity. It checks the exact case and 900-frame four-camera profile before lazy CARLA import. `pavement_native.py` owns and restores actors and world settings. `pavement_capture.py` preserves the materialized attempt, captures 900 consecutive original frames and four FFV1 streams, and writes a source receipt. After successful restoration, the runner seals Native provenance and calls `analysis.py` to write a source-bound result. The finalizer detects crossing or bypass from original positions and leaves legal judgment unresolved.

Seven primary and seven slower physical fallback constructions were rebuilt after fixing the Native attempt and result lifecycle. Their current hashes are in `execution-manifest.selected-draft.json`; each fallback changes only the controller speed scale. No selected or fallback is considered ready from a synthetic diagnostic alone.

## CPU progress

The current pinned CPU preflight passed. Four focused tests passed. All seven fallback offline checks passed. The first 900-frame primary compatibility attempt passed positive conversion, Lean decoding, four-view processing, and negative missing-source rejection. That attempt predates the final Native lifecycle source change and is diagnostic history only. Current-hash primary and fallback compatibility runs are in progress under `.runtime-work/c230211-nov26/`. Six independent comparison definitions passed synthetic positive and negative protocol checks; `comparison-proposal.json` records no Native acceptance.

The diagnostic generator retains 900 joined capture, trace, frame-index, packet, and graph records, with each returned generator under 2 MiB. Its provenance is explicitly synthetic. Physical outcome, capture lifecycle, saved-only processing, and independent delivery proofs remain to finish for every case before marking `result.json` ready and running the exact scoped strict gate.
