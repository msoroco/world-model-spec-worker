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

## Source-bound audible emitter join, 2026-11-24

The earlier audio measurement detected a microphone waveform above an engineering threshold but could not associate that sound with the rider's commanded emitter. `sidewalk_overtake.py` now requires a SHA-bound `emitter-event-history.jsonl` source with an original emitter actor ID and frame/time row for every rider and pedestrian sample. Each microphone onset must follow an original emission event within the reviewed maximum propagation interval (at most 0.2 seconds). A loud unrelated sound and a changed emitter actor identity fail even when the event history is resealed. The output retains the original event times and still leaves human audibility, yielding and legal outcome unresolved.

The nine-test focused suite passes (`cpu-emitter-join-tests.log`, SHA-256 `66c64c34a3c7454016cc3193934b2f82377d1f65cedc0e294cf0e4171016f689`). Pinned preflight passes (`cpu-emitter-join-preflight.log`, SHA-256 `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`), scoped static passes (`cpu-emitter-join-static.log`, SHA-256 `4d5e3bc3eacdedd907e77fe720d4bfaa83e3f441e68424d92963e2b20020e66a`), and exact scoped strict exits 1 on truthful partial (`cpu-emitter-join-strict.log`, SHA-256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`). All command/log hashes are in `result.json`. There is no offline bundle yet, so offline and compatibility proofs remain CPU work.

Next CPU work is the source-gated exact runner/configuration for all six planned alternatives, actual four-camera and microphone acquisition, canonical semantic proposals/manifest, case-specific offline and compatibility proofs, and independent saved-delivery audits. A reviewed connected sidewalk remains necessary for eventual physical execution.
