# LVMC-11-52-030-B at C150173

## 2026-11-26 taxi selected CPU continuation

Four exact 30-second, 20 Hz, four-camera taxi cases now exist: passenger waiting at 10:00 and 18:00, passenger loading at 10:00, and passenger unloading at 10:00. Each has a same-case stop-position fallback with the purpose, clock, cameras and road held fixed. `native/audit_draft_comparisons.py` independently verified all three controlled comparisons and all four fallbacks. Five unit tests passed, including a real 600-frame FFV1 full-decode/profile check. Pinned `runtime.py offline` passed for all eight final-byte v9 constructions with `--check` executing; the earlier runner had no CLI dispatch and was fixed. `native-selected-cpu.json` binds the four delivery-intent cases, their source-based measurement contracts and retained offline logs (all four contracts pass the runtime measurement-contract validator); its delivery_ready field remains false.

`native/finalize_original.py` joins 600 original taxi body, civil-time, trace and four-camera frame rows; `native/seal_review.py` now requires a Native capture seal and source-based reviews before hashing the source set. Four exact source-shaped CPU fixture recipes now materialize under `.runtime-work` and pass the saved-source join: probe_a 600 posted-active frames, probe_b 0, probe_c 600, probe_d 600, all synthetic and without original-evidence claims. `native/audit_original.py` independently checks a sealed original attempt, exact four-camera time joins and complete FFV1 decodes; it has no original positive yet. Synthetic structural tests reject changed footage, missing purpose review and a synthetic source kind in the original path. These tests do not establish an authoritative sign, taxicab identity, passenger exchange, legal permission or physical completion. The 18:00 case measures posted-hour activity only; ordinary parking rules are unresolved. The commercial freight alternative needs a separate source-authorized compatible actor binding and remains pending.

Remaining CPU work: build a contract-compliant selected execution manifest with canonical semantic proposals, selected finalizer result, positive/negative public compatibility, saved-only processing, physical and independent delivery/comparison audits. The selected source reviews must resolve the actual posted sign, passenger purpose and outside-hours rules; no fabricated legal finding is allowed. Scoped `worker_check.py --assignment training__C150173__LVMC-11-52-030-B__taxi_driver --complete` passes for this partial checkpoint. The strict `--require-delivery-ready` gate fails because the package remains partial.

## Current CPU construction checkpoint

`native/measure_yellow_zone.py` now reads hashed yellow-curb geometry, authored sign hours and 600 contiguous 20 Hz taxi rows with civil time. `prove-yellow-zone.py` retains two 30-second synthetic diagnostics with the same taxicab, stop, curb, and sign; only clock hour differs. Both show 600 standing-in-yellow-zone frames. The 10:00 trace has 600 sign-active standing frames; the 18:00 trace has zero. Two positives and six negatives (changed source bytes, missing taxicab identity, civil-time gap for each trace) pass. Proof SHA-256 `3f7f9722b4edd82751a978fc85182d941f08785d16d68994c1c2abd0bc9aabd6`.

`audit-yellow-zone.py` independently checks frozen statutory text, retained source hashes, raw taxi rows, civil-time joins, and posted-hour counts. It passed; audit SHA-256 `b59794c7bfc581b58f0499786a6c8d2197b454c9771a20b98843a6f9159ddd31`. These are synthetic CPU diagnostics, not a verified authoritative sign, observed passenger-waiting purpose, Native parking, selected delivery, accepted evidence, or legal verdict. Outside posted hours, the ordinary parking rules remain unresolved; the zero active-hour count is not itself a prohibition finding.

Verification commands: `.venv-cpu/bin/python work/training__C150173__LVMC-11-52-030-B__taxi_driver/prove-yellow-zone.py` and `.venv-cpu/bin/python work/training__C150173__LVMC-11-52-030-B__taxi_driver/audit-yellow-zone.py` exit 0. Pinned `.venv-cpu/bin/python runtime.py preflight` exits 0; `current-preflight.log` SHA-256 `88e35c2dc843cd5657b918dda888d0e329875479f96f80a1eedae7d9e25f6e4c`. `.venv-cpu/bin/python worker_check.py --assignment training__C150173__LVMC-11-52-030-B__taxi_driver --complete` exits 0; `current-scoped-complete.log` SHA-256 `5e90eb3af3624963e9f13d77facfd2202380c2646ab2a3d23c6cfcf2fcfba306`. This validates a partial checkpoint only.

Remaining worker-owned CPU work: construct exact Native taxi parking and yellow curb/sign geometry, source the sign's authority and posted conditions, observe passenger waiting/loading/unloading or commercial freight purpose as applicable, resolve outside-hours ordinary rules, build four distinct 30-second constructions per selected case with four cameras, run saved-source processing and Core/Lean/final decode positives/negatives, and complete independent delivery/comparison audits. Keep partial until scoped strict readiness passes.

Actor: `taxi_driver`. Frozen cell: `one_way_road` / `park` / `yellow_curb`.

Witness branch: taxicab passenger waiting.

Comparison variable: `taxi_yellow_zone_use`. Proposed physical probes: wait for passengers under posted conditions; use zone contrary to posted conditions. These are proposed controller and scene targets, not observed behavior or legal verdicts.

Source: `inputs/training__C150173__LVMC-11-52-030-B__taxi_driver/assignment.json`, SHA-256 `977f5ca417c21b2a894ca88be6bc9f14f807d9b090a3f7d4c78075f3bb258098`. Summary status: `recovered_requires_source_review`; exact law text and witness take precedence.

Accepted membership IDs: none. No source-hashed equivalence receipt or accepted recording contents are available locally, so no reuse is claimed.

Incomplete CPU work: Delivery package incomplete: two controlled branches are planning definitions only; no four distinct CARLA constructions, offline and compatibility proofs, saved measurement fixtures, or independent audit. Physical realization and legal outcome remain unverified.

Resume by resolving every statutory branch and exception against the law text; construct physical Native routes and controllers in the frozen cell; define measured channels and four distinct plans per selected case; run offline, compatibility, saved-only, comparison and independent audit proofs; set ready only after those proofs pass.

Update 016 status correction: missing case construction, candidate proofs and audits are actionable CPU work under START_HERE.md. This package is partial, with the frozen scope and listed resume actions preserved.
