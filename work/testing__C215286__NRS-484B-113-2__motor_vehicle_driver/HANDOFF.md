# C215286 NRS 484B.113(2) crosswalk delivery handoff

Status: delivery prepared on the current pinned CPU runtime. The exact assignment strict gate passed on 2026-11-24. Native CARLA capture, physical acceptance, camera pixel review, and legal judgment remain for local GPU delivery.

## Scope and selected cases

The assigned branch is backing on or over a crosswalk at C215286 by the motor vehicle driver. `case-plan.json` selects three exact cases: `reverse_clear` (disjoint), `reverse_tangent` (contact), and `reverse_overlap` (positive-area overlap). It requires `reverse_contact_vs_clear` and `reverse_overlap_vs_clear` saved-source comparisons. These are engineering geometry probes. The law's contact boundary has no source-backed numeric cutoff; the canonical semantic proposal records the numeric judgment sweep as incomplete, while preserving all three selected physical probes and unresolved legal judgment.

The one frozen accepted marked-crosswalk recording remains unchanged. Its exported metadata reports acceptance and 700 frames, but the original trace and video were not supplied. The existing-evidence review cites its frozen metadata and retains that limitation; it does not infer body-crosswalk relation or comparison isolation from acceptance metadata.

## Source-grounded Native package

`execution-manifest.json` binds three selected primary constructions and one source-triggered fallback per case. The package requires an original C215286 marked-crosswalk site packet with map hash, map marking polygon/source, district and driver attribution, vehicle blueprint, spawn and reverse route. `runner.py` captures 900 original 20 Hz vehicle-body and crosswalk frames, four synchronized original cameras, frame mapping, source hashes, Native restoration/closure evidence, and selected measurement. The analyzer derives physical disjoint/contact/overlap from the original frame source and returns no legal verdict. The fallback changes only reverse throttle and engineering stop radius, with source-defined trigger conditions.

The selected measurement contract binds original source files and a missing-source rejection. `compare_saved.py` verifies two distinct saved attempts, their original map/marking/vehicle/driver/district identity, timestamps and observed geometry distinction. `delivery_audit.py` reopens original source, trace and four FFV1 videos, validates all timestamp joins and decoded pixels, and rejects missing original frame source. The positive CPU audits are explicitly synthetic diagnostic fixtures; their pixels and geometry are not physical CARLA acceptance evidence.

## CPU proofs and exact delivery

All six primary/fallback offline and compatibility proofs passed on the current pinned runtime, including Native validator, Lean Core decoder, four camera renders/decodes, selected measurements and negative source tests. Saved-only processing passed for each exact case with preserved acquisition sources and a fresh derived version. Both comparison audits passed. The focused suite passed 26 tests. Physical preparation fixtures exercised complete, incomplete and missing-evidence branches, plus Native seal, exit and owner-release ordering. Each case's `delivery_acceptance` receipt binds a positive independent audit and a negative missing-source audit for demo-test and full-test targets. These proofs prepare the package for GPU delivery; they do not claim physical or legal acceptance.

The first exact GPU command is in `result.json` as `first_gpu_delivery_command`. It needs `CARLA_PYTHON`, `CARLA_HOST`, `CARLA_PORT`, `JOB_ID`, `DB`, and `RUN` supplied by the local owner. Run one exact selected case at a time, preserve the original site packet and pixels, review fallback triggers from original measurements, then use recorded-only processing and the two independent comparison audits. The local lead adds the three exact case commands and two comparison commands to the shared queue.

Verification: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python worker_check.py --assignment testing__C215286__NRS-484B-113-2__motor_vehicle_driver --complete --require-delivery-ready` exited 0 and reported `static_checks_passed: true`.
