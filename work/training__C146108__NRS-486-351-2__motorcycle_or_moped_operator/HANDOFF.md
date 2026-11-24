# NRS 486.351(2) at C146108

The frozen `one_way_multilane` / `overtake` / `other_vehicle` cell and `motorcycle_or_moped_operator` actor are retained. The frozen witness requests a same-lane pass. There are no accepted original recordings in the assignment snapshot; no reuse or physical acceptance is claimed.

## Current CPU construction

`controlled_2` is a selected motorcycle same-lane pass draft in `draft-same-lane-manifest.json`. `native/geometry.py` authors a 300 m one-way two-lane OpenDRIVE road with two 6 m through lanes. `native/runner.py` places the motorcycle and another motor vehicle in the same lane, requests a behind-to-ahead pass using distinct target velocities, records all 600 original Native frames at 20 Hz, writes full actor body corners and four synchronized FFV1 camera streams, and restores the exclusive world. Blueprint availability, actual trajectory, body clearance, pixels and lane readback require the local Native run. The camera videos in the CPU measurement diagnostic are labelled synthetic placeholders and establish no pixel proof.

The source-bound `native/measure_pass.py` checks complete frame/time/camera joins, both full bodies within one lane for all 600 frames, and ordered behind, overlap, clear-ahead events. It reports the minimum lateral body gap during overlap and retains source hashes. It rejects a missing pose source. It makes no legal verdict. The measurement maps the frozen observation terms in `case-plan.json` without treating all planning terms as Core IDs.

Pinned offline command: `.venv-cpu/bin/python runtime.py offline --manifest work/training__C146108__NRS-486-351-2__motorcycle_or_moped_operator/draft-same-lane-manifest.json --case training__C146108__NRS-486-351-2__motorcycle_or_moped_operator__controlled_2 --output .runtime-work/c146108-moto/offline-04 --python "$PWD/.venv-cpu/bin/python"`. It passed; `cpu-offline-proof.log` SHA256 `1bf3001eb5e06bbcf8ab554fd80eae5072fed56d88dba46e6d02fd6f329251b4`. The construction SHA256 is `4161ad5bd730501da6e1de22fbaca0cf2e50c6fdde3a06ebe33abdbcfde811ba`.

Source-bound diagnostic command: `.venv-cpu/bin/python work/training__C146108__NRS-486-351-2__motorcycle_or_moped_operator/prove-measurement.py`. It passed positive 600-frame, negative missing-source and wrong-lane tests; `measurement-proof.log` SHA256 `4aca86dc050ad82b8c42d07ace0970460ff70f3a599dda9caf0f17c935cc0ee2`.

## Remaining CPU work

Build the controlled following counterpart, the distinct abreast and passing alternatives, moped/trimobile statutory alternatives as appropriate, and review consent and subsection 3 against authoritative text. Complete exact selected case manifests, risk-based fallback constructions, source-bound compatibility and saved-only processing, semantic proposals and independent delivery/comparison audits. Run each exact scoped strict ready gate only after these proofs pass. Native physical motion, actual camera pixels and canonical acceptance remain unobserved and are not claimed.
