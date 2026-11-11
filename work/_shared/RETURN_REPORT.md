# Held-out CPU return checkpoint — 2026-11-11

Batch: 51 assignments; 6 ready, 45 partial, 0 blocked. Strict delivery gate has not passed. No physical or legal acceptance is claimed.

## Environment and gates

- Pinned `.venv-cpu` preflight: rerun and passed with numpy 1.26.4, ffmpeg/ffprobe and Lean/Lake 4.28.0 available (`preflight.log`, SHA256 `e607085136fde64b5d223161149ee690740b924253c7fd8e91245a898fccba80`).
- Repository unit tests: rerun, 6 passed (`repository-tests.log`, SHA256 `9408fccf6c69b927bcc68bdeec11205fe15e99cebba50e25cc7695cb0216cc66`).
- Latest batch checkpoint gate: passed (`batch-check.log`) after the owners repaired disallowed proof names, compacted diagnostics and cleaned generated runtime scratch.
- Latest batch strict gate: rerun after the environment update and C111273 code changes; exit 1, `Preparation acceptance failed: partial/missing packages remain` (`batch-strict-gate.log`, SHA256 `89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292`). This is the current definitive result with six ready and 45 partial assignments.

## Partition 01 work

- C109514 / NRS-484B-710: ready with 13 exact cases and scoped strict gate passing; see its `HANDOFF.md` and `strict-gate.log`.
- C110161 / NRS-484B-207-1: source-bound overtaking measurement, connected same-direction two-lane route, measured-clearance return controller, original Native body/road-tangent recorder, four-camera runner and saved-only canonical finalizer pass eleven CPU tests and the first exact offline construction check; full compatibility, remaining cases and audits remain, partial.
- C111294 / NRS-484B-250-3: ending-road topology and entry-order measurement/audit; partial.
- C111603 / NRS-484B-413-1: indicator/audio measurement and branch plan; partial.
- C125714 / NRS-484B-200-1: baseline Native construction probe, four synchronized cameras, original footprint acquisition, saved-only joins; exact offline and 17 local CPU tests pass. Eight case deliveries and seven comparisons remain CPU work; partial.
- C136539 / NRS-484B-600-1b: first Native person-exposure construction probe, original actor capture, four cameras and saved-only analyzer pass exact offline and 12 local CPU tests; six person/property case intents and four comparisons; partial.
- C178038 / NRS-484D-215-2: original Native body/high-low beam readbacks feed source-bound 299/300/301 ft following measurement and saved-only canonical result shape. The first connected two-vehicle, four-camera Native construction probe passes exact offline and 11 CPU tests; full compatibility, other cases/fallbacks, proposals and audits remain, partial.

## Other partition owners

- Partition 02: C147331 has six exact cases and 18 fallbacks, all passing offline, positive/missing-source compatibility, saved processing, source audits, synthetic physical/lifecycle and positive/stale-source delivery fixtures. Twenty-one CPU tests and three comparison audits pass. Its scoped strict gate fails solely because status remains truthfully partial: passing-lawful facts and the separate unallocated C5191 turn branch require further review. C178759 now has original-frame continuous-driver conduct-distance and two-episode measurement with below/at/above one-mile tests; scoped partial gate passes, while Native construction/finalizer and exact proofs remain.
- Partition 03: C136014 is ready: nine exact cases, 36 primary/fallback bundles, source-bound semantic chain, offline/compatibility/saved processing and physical protocol/delivery audits pass. Its scoped strict gate exits 0. C10365 has an officer direction Native runner, connected alley/sidewalk placement, four post-indication branches, retained direction/motion sources, four cameras, first exact construction and saved-only finalizer; ten CPU tests and scoped partial gate pass, while exact bundle proofs and audits remain.
- Partition 04: C136529 is ready with six exact cases, 24 primary/fallback constructions, offline/compatibility/saved processing, six delivery audits, six physical-preparation receipts, five comparison audits and three fixed source-measured speed grids. Its scoped strict gate exits 0. C111273 now has source-linked Native traffic-light/lane selection for both approaches, a crossing actor, four-camera synchronized capture, post-tick Yellow/Off readback/restoration, a saved-only source-joined finalizer and a three-comparison fixed-condition audit. Eighteen CPU tests and its scoped checkpoint gate pass. The scoped strict gate exits 1 because exact bundles, fallback and compatibility proofs, semantic proposals and delivery audits remain; its status remains partial. See `work/heldout__C111273__NRS-484B-310-2__motor_vehicle_driver/HANDOFF.md` for hashes and commands.

## Exact continuation

Complete every partial package’s exact construction, fallbacks where risk warrants, case-specific positive/negative compatibility, saved-only processing, semantic proposals and independent delivery/comparison audits. Rerun each scoped strict gate before setting ready. Then build and review shared branch coverage, GPU queue and integration proofs, rerun `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready`, and update this report with its exit code. The missing CPU implementation is unfinished work, not an external dependency.
