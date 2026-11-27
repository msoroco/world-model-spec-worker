# Current handoff, 2026-11-27 rider-class comparisons

The current result is `ready` / `delivery_prepared`; the exact scoped strict gate passed after the rider-class additions. The six selected cases and their original capture contracts are unchanged. The law names bicycle, electric bicycle, and electric scooter separately; the electric bicycle and scooter cases are now paired with the bicycle before-signal/yield reference. The two new comparisons isolate `rider_kind` while requiring the same reviewed connected sidewalk map and route, 900-frame capture, original pre-pass signal, and original brake response. `delivery_audit.py` rejects changed fixed context, unsealed or mismatched measurements, changed signal timing, and changed response. The focused suite has 27 passing tests in `cpu-matrix-rider-kind-tests.log`; the exact scoped strict result is in `cpu-matrix-rider-kind-strict.log`. The local queue addition is `queue-comparison-proposal.json` with two comparison rows and command catalog entries, adding no case jobs. Original physical/human review remains in `remaining_gpu_checks`; no legal or physical conclusion is claimed.

The older notes below record earlier partial checkpoints and do not override the current `result.json` or exact strict gate.

## 2026-11-25 sparse source-gated judgment sampling

Assignment status is recorded in `result.json`; release requires the exact scoped strict gate to exit 0. The canonical judgment sweep specs retain `status: incomplete` because original physical and independent human review has not occurred. `sweeps_expanded: true` records that the canonical expansion pass ran; because the two judgment specs are incomplete, it created no judgment-sweep cases. The six selected cases are ordinary controlled cases.

The engineering sample is explicitly sparse, with six exact point-to-case mappings in `case-plan.json` and `proposals/cases.json`. A bicycle pre-pass signal/brake case is the shared reference. Two bicycle cases vary emitter timing to late and silent while retaining brake response; one bicycle case varies response to advance while retaining the pre-pass signal. Electric bicycle and electric scooter each receive the pre-pass/brake capability point. No Cartesian product of rider kind, timing and response is claimed. This covers the law's three covered rider alternatives and isolates the two requested behavioral contrasts without inventing legal ranges. The three comparisons remain the fixed before/late, before/silent and brake/advance pairs.

`qualitative_sweep_audit.py` binds each exact sparse point to its selected production construction SHA, source-sealed independent original delivery receipt, connected sidewalk map, full original rider/pedestrian/emitter/microphone source inventory, 900-frame passing bracket, original review intervals and independent yielding or human-audibility observation. It rejects missing or changed sources, misbound points, missing capability and intervals, and legal verdicts. Synthetic original-shaped fixtures test only the software protocol. `audit_original_cli.py` and `compare_original.py` expose local post-capture audits. `queue-proposal.json` lists six exact jobs, fallbacks and three comparison audits.

The focused suite passes 24 tests; scoped static passes. Direct current execution, semantic (seven stages), six delivery and compatibility validators passed in `cpu-qualitative-sweep-direct-v25.log`. Original connected sidewalk/site review, emitter and microphone capability, real 900-frame Native capture, independent physical/human review and legal interpretation remain local production requirements.

## Current handoff, 2026-11-25 production source-gated package

Status: **partial**. Selected production manifest SHA-256: `b8015fd07b0dfca0e8ca5db4ba5746331ca9a0bd9dd49b0f813dd9a024887e7d`. The package has seven semantic cases (one baseline and six exact targets), six primary constructions, six upstream-route fallback constructions, and three fixed comparisons. The two qualitative judgment sweeps retain `status: incomplete` and explicit original-source review needs. Synthetic diagnostics are labeled as such; no physical or legal acceptance is claimed.

- `runner.py` dispatches the exact selected case through a reviewed original sidewalk packet, live route and actor readback, physical audible emitter and pedestrian microphone. It records 900 ordered frames at 20 Hz with four cameras and the microphone. The fallback moves the actual rider route start one meter upstream and rechecks the connected sidewalk. Missing, changed, or diagnostic source packets fail closed.
- All 12 exact primary/fallback offline proofs passed. All 12 source-hashed compatibility runs passed selected measurement, missing-source rejection, Native validation, Core decoder, four-camera rendering, and final decode. Six recorded-only saved replays passed 900-frame joins and source preservation; none claims physical or legal acceptance. Receipts are under `proofs/production-*` and `proofs/saved-production-*`.
- Six three-state synthetic motion and ordered lifecycle receipts passed. Six independent original-delivery audit probes passed positive mock-only wiring and absent-original rejection. Four comparison-audit tests passed. The focused suite passed 18 tests (`cpu-nov25-production-tests.log`). Direct execution-manifest, semantic, delivery, and receipt validators passed (`cpu-nov25-production-validators.log`). Scoped complete static passed (`cpu-nov25-production-static.log`).
- Exact scoped strict exits 1 at `Preparation acceptance failed: partial/missing packages remain` because `result.json` is truthfully partial (`cpu-nov25-production-strict.log`). It did not fail a CPU construction, offline, compatibility, saved, semantic, or delivery validator. No assignment-local GPU queue proposal is published while strict is failing.

Original source needed for readiness: a reviewed **connected physical sidewalk** for C142510, exact rider/pedestrian blueprint and audible emitter/microphone capability, original source-manifest/site packet with geometry and hashes, 900-frame 20 Hz rider and pedestrian histories, original emitter-event history, pedestrian microphone PCM16 WAV, and four original 900-frame camera videos. The cell's `nonmotorized_trail` label does not establish the physical connected sidewalk. Original motion and audio plus independent judgment ranges are needed to finish the yielding and audible-signal sweeps; human audibility and right-of-way yielding remain unresolved. The production runner and analyzer reject absent or synthetic original sources.

The exact command is `.venv-cpu/bin/python worker_check.py --assignment testing__C142510__LVMC-11-40-180-C__cycle_or_scooter_operator --complete --require-delivery-ready`. Keep status partial until reviewed original source and judgment work permits this gate to pass.

## Historical notes

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
