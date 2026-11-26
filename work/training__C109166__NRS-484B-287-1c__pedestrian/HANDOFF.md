# C109166 NRS 484B.287(1)(c) delivery handoff — 2026-11-25

Status: **ready for exact GPU delivery preparation**. The assignment-scoped strict CPU gate passed on the final selected cases and candidate proof bindings. No original CARLA capture, physical or legal acceptance is claimed. Historical checkpoints follow below; their partial status predates this selected package.

- Selected cases: `__marked_crosswalk` and `__unmarked_midblock`, each 600 frames at 20 Hz for 30 seconds, with primary and `fallback1` camera-height candidate.
- Current Native runner: `native/crossing/original_capture.py`, materialized in each exact construction as `runner.py`. It requires a separately sourced and independently reviewed two-junction map/control survey, captures pedestrian footprint, both operating official controls, four synchronized cameras and full source hashes, then records world restoration.
- All four selected exact offline checks and all four public compatibility checks passed. The public proofs include selected measurement analysis, four source videos, Lean decoder, full render/decode and a missing-control-source negative. They are synthetic diagnostics, not original capture evidence.
- Both primary `process-saved` runs passed recorded-only processing with original acquisition preserved. Independent source/video delivery positives passed for both cases; each rejected a removed `controls-original.jsonl`. `comparison-proof.json` checked all 600 source frames and isolated the 20 m crossing-location difference while holding survey, exception source, control states, timing and camera plan fixed.
- NRS 484B.290 is explicitly bound as selected requirement `text-1` to both cases in `case-plan.json`. Its exact operative text and person-specific applicability are absent from frozen inputs. The source-only measurement outputs `undetermined`, and the production delivery audit requires independent source review before acceptance. No legal verdict is asserted.
- Physical CPU receipts cover completed, incomplete and missing-evidence outcomes plus capture-finished → encoders-closed → restoration-verified → Native-exit → owner-released → saved-processing ordering. Actual Native physical completion remains for GPU delivery.
- Exact check: the owner and lead independently ran `.venv-cpu/bin/python -B worker_check.py --assignment training__C109166__NRS-484B-287-1c__pedestrian --complete --require-delivery-ready` on 2026-11-26; both exited 0 with `static_checks_passed: true`. The earlier cloned camera/duration-plan failure does not recur in this current workspace.
- Selected manifest SHA-256: `a801db54cd7c0372adc65c8f8d812aaefafea1d547b66989f41cf399bba13a77`. Comparison receipt SHA-256: `1dc7b5d4ae33f75f326212a3eaa271795d1d589d58a7bb2734f35fb91c440368`.

## Historical checkpoints

# C109166 pedestrian crossing checkpoint

Status: partial. No selected delivery case, Native observation, physical acceptance, or legal verdict is claimed.

## Source and comparison

The current frozen NRS 484B.287(1)(c) text applies to crossing between adjacent intersections with official traffic-control devices in operation, except as provided in NRS 484B.290, and permits a marked crosswalk. The frozen cell is intersection / enter_road / traffic_control_device, actor pedestrian. The witness is pending review; the full-train membership has zero rows. The recovered summary is not statutory authority.

The two `case-plan.json` definitions request marked-crosswalk and unmarked-midblock crossings. `native/crossing/request.py` binds to current assignment SHA-256 `2254705a424b298452a063dfb5d4f1f6d67754ab8b055d5cac789935e7252d07` and plan SHA-256 `6f0e6cb201c525afd05d718702178be731e185b6360a403aaa218b60b6b37c0c`. It builds two unselected 600-frame, 20-Hz, 30-second pedestrian requests. Their x=0 and x=100 intersections, x=40 marked crossing, x=60 unmarked crossing, and roadway boundary y=-4 are authored diagnostic markers, not measured Native map facts. Each requested crossing reaches y=-4 at frame 259 (13 seconds). All Native, official-device, marking and verdict fields remain false or null.

## Current CPU evidence

- `native/crossing/manifest.json`: SHA-256 `988567de56a016c27413da6302aa659bfbc7b809a1be045f0c85eb798071deed`.
- `native/crossing/request-proof.json`: SHA-256 `8003aceeb9c6c30ae87c914eb7e0359b071e1f0608050d22664f6ed33fb43818`. `prove.py` passed 2 exact positives and rejected 8 law, track, status and duration tamper cases.
- `native/crossing/comparison-audit.json`: SHA-256 `60fa15099acb9c2b2abf067e70abec5e0b65f6edb88375b2eb7f10e2bc8a9231`. `audit.py` compared all 600 frames; only requested x and crossing category differ.
- `native/crossing/draft-execution-manifest.json`: SHA-256 `8942feaeae3e41bc72a984d35f868dd6941571033f605462abbc51ea4df50775`.
- `native/crossing/pinned-runtime-proof.json`: SHA-256 `bfd3d4eb1540c946607a07f99ea16dcc8a300689fb5969034a1e0db2d5ee4141`. Both current `runtime.py offline` runs exited 0 with one exact test each and no simulation; hashed logs are under `.runtime-work/c109166-*-2/offline.log`.

Commands: `.venv-cpu/bin/python runtime.py preflight`; `.venv-cpu/bin/python native/crossing/request.py`; `.venv-cpu/bin/python native/crossing/prove.py`; `.venv-cpu/bin/python native/crossing/audit.py`; `.venv-cpu/bin/python native/crossing/build_runtime_offline.py`; `.venv-cpu/bin/python runtime.py offline --manifest native/crossing/draft-execution-manifest.json --case CASE_ID --output .runtime-work/c109166-LOCATION-2` (paths relative to this assignment for native scripts, repository root for runtime).

## Required continuation

Review NRS 484B.290's exception and map source observation terms to measured channels. Build executable CARLA geometry with two verified adjacent intersections, official traffic-control device identity and operating-state readback at roadway entry, physical marked crossing, pedestrian controller and footprint crossing, four synchronized cameras, measured frame identities and world restore. Build the source-only saved finalizer, primary and risk-justified fallback candidates, exact positive/negative compatibility and process-saved/render/decode proofs, semantic proposals and independent delivery/comparison audits. A requested coordinate cannot prove physical map adjacency, control operation, marking or legal compliance. Keep partial until the assignment-scoped strict gate passes.

Final scoped checks: `.venv-cpu/bin/python worker_check.py --assignment training__C109166__NRS-484B-287-1c__pedestrian --complete` exited 0. The same command with `--require-delivery-ready` exited 1 on the expected partial-package acceptance condition. All returned files are below 2 MiB; whitespace and conflict-marker scan passed.

## Source-only saved crossing continuation (2026-11-23)

`native/crossing/saved.py` now checks two diagnostic saved attempts against exact 600-frame/20-Hz maps, pedestrian footprint samples, both official-device operating samples, adjacent-intersection topology, source file hashes and all four 600-frame decoded camera streams. The two requested crossing locations share source frame identities, device state, map context and decoded camera pixels; only pedestrian footprint x and crossing category differ. The marked request reaches the authored x=40 marking and the unmarked request crosses at x=60, with the same roadway entry frame 259. These are **synthetic Native-shaped sources**, not physical map/device/pedestrian observations or a legal verdict.

`prove_saved.py` passed both positives, retained source bytes, and rejected five material mutations: an unbound pedestrian source hash, changed frame identity, a device disabled at entry, an intermediate intersection, and a missing fourth camera. Independent `audit_saved.py` passed the controlled source/pixel comparison. Current pinned `runtime.py offline` also passed the two unchanged exact request drafts. Receipt `native/crossing/current-cpu-checkpoint.json` SHA-256 `531e0ba1cafec02f3e0884927668af3743b85f361c779e007734ed20698ef6f5` binds saved proof SHA-256 `bffbe4a485e3f0d41809a61718b05ab5f4ea0df3875b3c00b92450e89c013b9c`, independent audit SHA-256 `f0532ab0a841908f3492c3a8468cccddce095c1b215b2c727b2608eef19cb0e9`, and both offline logs.

Next CPU work remains executable Native geometry, pedestrian controller, real source-camera capture and restore, source-derived adapter inputs, current `process-saved` and positive/negative compatibility on an exact selected primary, risk fallbacks, semantic proposals, and independent acceptance/comparison audits. NRS 484B.290 exception and original Native verification remain unresolved; status stays partial.

## Authored crossing scene and controller CPU checkpoint (2026-11-23)

`native/crossing/scene.py` adds an authored OpenDRIVE two-junction road, two requested official traffic-control devices, a marked crosswalk at x=40 m, and a pedestrian motion controller. The marked and unmarked requests share road, devices, marking, controller, 30-second/600-frame policy and four named cameras; only requested pedestrian x changes from 40 m to 60 m. `native/crossing/prove_scene.py` passes two positive request checks and six negatives for case identity, blueprint, camera loss, false Native verification, missing pose and missing observed device state. Proof SHA-256 `22d6300a9b8137510b9b63dea7112dbbc05b217cba786e5da0eef7966361ac38`. This is authored geometry/control software only: the XML junction/device geometry has not been parsed or observed in CARLA and is not a qualifying original source. Existing source-hashed request bundles and case plan are unchanged.

Next: complete CARLA map/junction parse and physical control-device readback, record walker footprint and four original camera streams, then run current saved-only and compatibility on selected cases with risk fallbacks and independent delivery audit. NRS 484B.290 exception still requires disposition. Keep partial until scoped strict gate passes.
