# C230259 / NRS 484B.297(2) pedestrian handoff

Status: ready for original Native delivery preparation. The assignment-scoped strict CPU gate passed on 2026-11-26. This status asserts a portable, source-bound execution package and CPU proofs. It does not assert an observed CARLA run, accepted recording, or legal verdict.

## Exact pair and source scope

The selected cases are `training__C230259__NRS-484B-297-2__pedestrian__selected_81846e7f__condition_a` and `training__C230259__NRS-484B-297-2__pedestrian__selected_81846e7f__condition_b`. They hold the reviewed highway boundary, no-sidewalk context, subsection 6 obstruction context, participant route, westbound pedestrian heading, 30-second 20 Hz window, and four synchronized cameras fixed. Only the pedestrian side changes: traffic-left in A and traffic-right in B. These labels are geometric diagnostics, not legal conclusions. The original Native map packet must substantiate highway authority and all spatial context at execution.

The Walker adapter in `walker_capture_adapter.py` routes the real pedestrian actor through the pinned PipelineCapture and SGG source path, while representing vehicle-only control and light fields as not applicable. `native/prove_walker_adapter.py` exercises this interface with a CPU mock. The source path has not run against a CARLA server on this host.

## Selected constructions and candidates

Primary A construction SHA-256: `c74521bfc280c987246ec37564433d62508da97c26d9ff9547bf7de3ad1cb8bc`. Primary B construction SHA-256: `9f91502ea2918d3d3c72ce0912fbe4e0c9e98687f1b58a58f2df655274ba18dd`. Fallback1 A construction SHA-256: `5b07ace0944e2759f82ad2d96ad9bdf0ab6c1efda5aac5c49656487ecbdd5316`. Fallback1 B construction SHA-256: `f90daa8c2e4874965094360a45a63cd2712c47a35d705855b1e8ca0f282ccb0b`. The sole fallback trigger is an original Walker spawn collision or measured vertical clearance below 0.05 m; it changes the Walker spawn height adjustment from 0 to 0.15 m. Candidate selection stays tied to each exact case and original measurement. It does not alter the comparison variable.

`execution-manifest.json` binds the current runtime, all four exact constructions, offline checks, public compatibility receipts, missing-road-source negatives, physical preparation, recorded-only saved processing, and independent delivery acceptance. `proposals/semantic-index.json` binds all five current-runtime semantic stages, including recording descriptions equal to selected constructions. Both three-requirement measurement contracts passed.

## CPU proofs

- All four A/B primary/fallback1 candidates passed `runtime.py offline` and public `runtime.py compatibility` on the pinned runtime. Compatibility decoded all four source cameras and rejected missing road source. These are diagnostic software fixtures, not original observations.
- Physical preparation under `physical-proof/condition_a/` and `physical-proof/condition_b/` exercises complete, incomplete, and missing-evidence source-shaped paths. The authored 0.4 m/s movement and 6 m progress threshold produce `met`, `not_met`, and `unverified` respectively; lifecycle ordering is checked. Original motion remains unobserved.
- All four candidates passed recorded-only `runtime.py process-saved` on copied diagnostic attempts. The original diagnostic inputs were unchanged, and final four-view videos decoded.
- `delivery_audit.py` independently checks 600 frame joins, both actor IDs, source context, side and heading continuity, vehicle progress, and per-frame video pixels. A/B diagnostic positives passed; original-source negatives rejected the same synthetic data. Original Native acceptance still requires an independent source and pixel review and measured maneuver completion.
- `native/validate_stage_contracts.py`, the three `tests/test_offline.py` unit tests, current preflight, scoped `--complete`, and the exact scoped `--complete --require-delivery-ready` gate passed. Static execution-manifest, semantic, handoff, and package compatibility validators passed before the strict gate. CPU logs bound by `result.json` are under `native/cpu-*.log`.

The passing gate command was `SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c230259-297-2-output TMPDIR=$PWD/.runtime-work/c230259-297-2-tmp .venv-cpu/bin/python -B worker_check.py --assignment training__C230259__NRS-484B-297-2__pedestrian --complete --require-delivery-ready`.

## Delivery handoff

Use `result.json` `first_gpu_delivery_command` for the first exact job and `execution-manifest.json` for the A/B candidate commands. At the delivery host, review the source map and route packet, observe the original Walker spawn and camera placement, select fallback1 only on its measured trigger, execute original Native capture, process only the saved recording, and run independent delivery acceptance on all four camera sources. Report observed failures without replacing source evidence with diagnostics.
