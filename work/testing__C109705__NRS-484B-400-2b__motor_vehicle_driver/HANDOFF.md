# C109705 CPU handoff — NRS 484B.400(2)(b)

Status: **partial**. Both intersecting highways must be two-directional. After left-turn entry, the complete body must leave the intersection to the right of the **destination** centerline. This differs from 400(2)(a), which governs approach position. No numeric legal lateral cutoff is supplied.

`case-plan.json.evidence_review` assesses all four frozen accepted metadata sources. Each identifies the fixed law/cell/actor, 900 frames and a passing decoder. Raw traces, video and delivery audits are not exported, so accepted labels and the shared manifest cannot prove destination exit position or comparison isolation. No original is replayed or claimed reusable. Four conditional source-verified cases address unresolved gaps.

`native_road_selection.py` inventories opposite-signed Native driving lanes on both roads. `departure_measurements.py` joins original telemetry and frame maps, requires observed entry before a complete-body exit on the outgoing road, and measures destination right-half containment and centerline clearance. Three CPU tests pass, including near/far, wrong side, wrong road, stale frame and missing exit/lane rejection. These are implementation tests, not a physical or legal verdict.

Next CPU work: review original accepted raw sources when available for exact equivalence; retain unknowns until verified. Source a two-directional junction and marked/imaginary destination references; implement exact left-turn runner, four raw cameras, original-frame capture, saved finalizer, three distinct physical-risk fallbacks per selected case, semantic proposals and independent delivery/comparison audits. Run exact offline, compatibility and saved-processing proofs and assignment strict gate. All construction and proofs are worker-owned CPU work.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C109705__NRS-484B-400-2b__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C109705__NRS-484B-400-2b__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

No frozen input, runtime or batch file was edited; no Git command was run. Pinned CPU preflight passes. Assignment and full-gate outputs are retained in `assignment-check.log` and `strict-gate.log`.

Checkpoint: assignment-scoped static check passed. Complete strict gate next reports missing result `testing__C125714__NRS-484B-250-1__motor_vehicle_driver`; this is unfinished worker preparation, not an external dependency.

## Destination source review checkpoint

`site_review.py` now binds the Native junction, both opposite-direction road lane inventories, the marked or imaginary destination centerline, the destination right-half polygon and junction geometry to five distinct byte-hashed source documents. It rejects a changed centerline source and a destination road without opposite-direction Native driving lanes. The fourth CPU test exercises both centerline kinds and those negative branches. The fixture documents are synthetic; no reviewed real centerline or junction document has been supplied or claimed.

Next prepare an actual source packet for a Native junction, route and controller for the four selected near/far marked/imaginary exits, four-camera capture and saved processing, physical-risk fallbacks, canonical proposals and independent audits. Current result remains partial because these are unfinished worker-owned CPU requirements; actual Native exit and source pixel visibility remain later physical checks.

## Paired turn route construction checkpoint

`departure_route.py` now plans near and farther left-turn waypoint paths from one source-reviewed Native junction packet. It requires selected approach and outgoing lane IDs in the opposite-direction Native inventories; an outside approach point, passage through the sourced junction, an outside destination exit, a left-turn heading change, and an exit body envelope wholly on the destination right half without centerline contact. The farther case must have more measurable centerline clearance than the near case. This is a route construction API for either marked or imaginary centerline source type.

`turn_control.py` applies bounded steering and speed control to the planned waypoint list and brakes at its endpoint. The fifth CPU test runs both near/far paths through source review, geometry rejection branches and controller progress. All five tests pass (`cpu-tests.log`). The synthetic map and source documents in this test do not show that a real Native junction matches the packet, that CARLA dynamics complete the left turn, or that original cameras show the destination centerline.

This route checkpoint preceded the integrated capture construction below. Status stays partial.

## First exact near-centerline construction checkpoint

`runner.py` now connects the source-reviewed two-road route and bounded controller to a CARLA-lazy 45-second, 20 Hz capture. It verifies the selected Native approach lane, spawns the ego and four original RGB cameras, joins each sensor image to the Native snapshot frame, writes lossless FFV1 streams, original `turn_history.jsonl`, `video_frames.jsonl` and sourced `road_context.json`, and restores the world after capture. `camera_setup.py` and `camera_encoder.py` implement four-camera lifecycle and lossless encoding. The actual Native capture path has not been run.

`construction.json` is the exact primary for `source_verified_near_centerline`; `draft-execution-manifest.json` binds its SHA-256 and the exact offline receipt. `site_packet.json` and five separate hashed documents are **synthetic CPU fixtures**, not a reviewed real Native site or legal road designation. The materialized `tests/test_exact.py` verifies that the exact packet passes source review, the planned exit has positive centerline clearance, the controller advances, and the wrong centerline kind is rejected. `runtime_cli offline` passed at `.runtime-work/c109705-near-offline-v1`; `exact-offline.log` is the copied log. No simulator was started. The standalone five-test suite and assignment-scoped `worker_check.py --complete` also pass with the current result.

The manifest is intentionally named `draft-execution-manifest.json`: it covers one of four selected cases and contains no fallback. Full strict readiness still requires a reviewed real junction and destination references, the three remaining selected exact constructions, distinct physical-risk fallbacks, saved finalizer and recorded-only process proof, positive/negative compatibility, semantic proposals, independent delivery/comparison audits, and later Native camera and body-exit review. No physical or legal completion is claimed.

## 2026-11-19 four-case exact offline checkpoint

All four planned source-verified departure alternatives now have distinct exact construction files: marked near (`construction.json`, SHA256 `289e3d8b254531cbe80f104bf9cf0fce9da1cf04e6cc78450deccdb03c1b13f2`), marked farther (`cases/source_verified_farther_from_centerline/construction.json`, SHA256 `9123b68f937d19249d55b4f1d41220dfad6a604bfdba214bd83497b009841a23`), imaginary near (`cases/source_verified_imaginary_near_centerline/construction.json`, SHA256 `a98fc2e5f97b88804c1b1a339318afd39b06d6bb5d188e1ef750b171c02cb7a7`), and imaginary farther (`cases/source_verified_imaginary_farther_from_centerline/construction.json`, SHA256 `8b8e02bb407b62682faaaa497683a2eb47cd33cf577068ea1d7d5d1c2c610d9d`). The imaginary cases carry a distinct synthetic imaginary-centerline source document and hash. The materialized exact tests check their expected kind, final route position, clearance, controller progress, and rejection of the wrong kind.

Each exact construction passes the pinned `worker_exchange.runtime_cli offline` command in `exact-offline-batch-proof.json` (SHA256 `5afd86ec433ddc58ecb03c128f0db641cd07ff7feeb6a4f750a5ca8c43461eac`). The bundle retains each command, current construction hash, JSON stdout, stdout hash, materialized offline log and log hash. All four exits are 0 and explicitly report `offline_passed: true`, `simulation_started: false`, one materialized test `OK`. The draft manifest binds all four current construction hashes and the bundle. The former single-case log is archived under ignored `.runtime-work/archived-unselected-empty-analysis/c109705-historical-exact-offline.log`; its bytes and hash are retained in the bundle.

`runtime.py preflight` passes with pinned Python, FFmpeg and Lean. The scoped `worker_check.py --assignment testing__C109705__NRS-484B-400-2b__motor_vehicle_driver --complete` and the affected C158190 scoped check both pass. The return is exactly 8,600 files. To meet that cap while preserving a draft's empty analysis evidence, three zero-byte C158190 sign-minus fallback analysis placeholders were archived to ignored `.runtime-work/archived-unselected-empty-analysis/`; their unselected `sign-angle-compatibility-manifest.json` references now point to three existing zero-byte fallback analysis placeholders with the same SHA256. This does not constitute positive compatibility proof.

Status remains **partial**. CPU work still needed: reviewed real Native junction and destination reference source packet; risk-based alternative constructions and exact proofs; executable saved-only finalizer and positive/negative compatibility for every exact construction and fallback; canonical semantic proposals, physical/delivery contracts, independent source and comparison audits, and strict ready-mode validation. The current four-case offline proofs use synthetic fixtures only; no CARLA motion, original pixels, legal finding or physical acceptance is claimed.

Full strict gate rerun on this checkpoint: `PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=.runtime-work/matplotlib .venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` exited 1 at frozen `runtime/scenario_pipeline/worker_exchange/preparation.py:97` with `ValueError: Unapproved output: runtime/runs/scenario_pipeline/state/cache/maps/34a021702707f02cd9a576bcf509ac3be929f0c110bc3a9ab50d5e8646ead71b.lock`. That zero-byte lock existed before this run and is outside approved return paths. The user forbids editing `runtime/`, so it remains present; the checker stops before the batch readiness decision. This is an exact strict-gate condition, while the package's fallback/compatibility/saved/audit requirements remain unfinished worker-owned CPU work. Do not mark ready.
