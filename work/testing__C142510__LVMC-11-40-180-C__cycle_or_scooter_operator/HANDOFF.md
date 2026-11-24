# C142510 connected-sidewalk pedestrian overtaking

Status: partial. Six exact targets and three controlled comparisons are planned; no real attempt is claimed ready. The cell is labeled `nonmotorized_trail`, so a reviewed physical connected sidewalk is required before any target is admissible.

## CPU package

- `native_overtake.py` checks live OpenDRIVE hash, source citations, covered rider kind, same-sidewalk route readback, real rider/pedestrian spawns, audible emitter and pedestrian microphone readback, and rollback on construction failure.
- `sidewalk_overtake.py` seals original map, site, rider/pedestrian body histories and microphone WAV. It joins original actor/frame/time rows, verifies 20 Hz history and full body sidewalk containment, measures actual passing and brake history, decodes PCM16 waveform and compares measured onset with pass timing. It leaves right-of-way yielding and human/legal audibility unresolved.
- Eight synthetic original-shaped tests pass, including source tampering, non-sidewalk, actor/frame mismatch, unrealized pass, silent/late signal, rider response, wrong rider kind and missing microphone. Synthetic fixtures prove the audit protocol only.

## Next CPU work

1. Source-review the actual C142510 map and connected sidewalk geometry, rider/pedestrian blueprint and usable audible emitter/microphone mechanisms.
2. Build canonical exact runner, configuration, construction manifest and semantic case proposals for all six targets; preserve the law's bicycle, electric-bicycle and electric-scooter alternatives.
3. Add four-camera capture, per-case offline and compatibility proofs, saved-delivery finalizers, comparison and independent delivery audits. Attach original source manifests and evidence to each real case.
4. Run the assignment-scoped strict gate and mark ready only if it passes. CARLA physical motion and pixels require later actual execution.

## Checks

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C142510__LVMC-11-40-180-C__cycle_or_scooter_operator/tests -v` passes eight tests. `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python worker_check.py --assignment testing__C142510__LVMC-11-40-180-C__cycle_or_scooter_operator --complete` passes. The strict scoped gate is expected to fail on truthful partial status; see `strict-check.log`. Test log hashes are in `result.json`.
