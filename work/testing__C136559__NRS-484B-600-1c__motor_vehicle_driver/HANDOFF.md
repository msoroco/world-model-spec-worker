# C136559 CPU handoff — NRS 484B.600(1)(c)

Status: **partial**. The selected obligation requires vehicle speed greater than the rate posted by a public authority for the particular highway portion being traversed. Frozen evidence has zero accepted recordings.

## Exact primary diagnostic checkpoint

The `posted_below` primary construction now contains a four-camera Native runner, 20 Hz velocity/frame/road-coordinate capture, physical Native sign selection by type/value/trigger, source-context capture, bounded controller, saved finalizer and pinned diagnostic OpenDRIVE geometry. The runner aborts on missing/ambiguous sign, lost road coordinate, frame mismatch or incomplete extraction and restores the prior world. Its authored 25 mph signal and 2.7 m lanes are diagnostic. They do not prove a public-authority posting or statutory highway status.

- `construction.json` SHA-256 `4b44295b117236890388325f31a445f7cc1589956f7a1d2865c4bacab0c56583`; `runtime.py offline` passed, no simulation started (`primary-offline.log`).
- `runtime.py compatibility` passed all 11 checks, including source-negative removal, actual analysis, four-camera decode and selected measurement (`primary-compatibility.json`, SHA-256 `6144646ac40af8c405fd97fa87547c7bb7a44ead418ebcf74891b8548d4d9776`). Static `check_receipts` returned true.
- `runtime.py process-saved` passed, preserving originals and recording `physical_acceptance_claimed=false` (`primary-saved-processing.json`, SHA-256 `67e068c6f6d40934e95fb66830af921e0d15ae78a136ad305228792e5dddf137`). The frozen proof manifest is `execution-manifest-processing.json`.
- Eight local CPU tests passed (`cpu-tests.log`), and assignment-scoped `worker_check.py --complete` passed (`assignment-check.log`).

The diagnostic fixture adapts nine original-shaped CARLA frames from the frozen runtime example. It adds an explicitly authored sign-context record and original-frame road-coordinate joins for software verification. Its measured in-zone sampled peak is **0.1236901875 mph**, well below the authored 25 mph value and the requested 24.9 mph. The source graph's road width differs from the authored construction scene. This fixture supports only software compatibility and saved-source mechanics; it does not establish physical target attainment, a visible sign, a legal posting or map consistency.

## Equality-requested primary diagnostic checkpoint

The `posted_at` case has a distinct case-bound construction and fixture recipe. It requests **25.0 mph** against the authored diagnostic 25 mph sign; its reused nine-frame source history measures **0.1236901875 mph** inside the diagnostic interval. This is **not** observed equality. Exact offline construction, all 11 compatibility checks including removed-sign-context rejection, and recorded-only saved processing passed. `cases/at/construction.json`, `cases/at/compatibility.json`, `cases/at/negative-analysis.log`, `cases/at/saved-processing.json` and `execution-manifest-at-processing.json` pin the proof. `check_receipts` returned true for both primary cases. The fixture does not establish public authority, sign visibility, highway governance or physical target attainment.

## Above-posted requested primary diagnostic checkpoint

The `posted_above` case now has a separate case-bound construction and fixture recipe requesting **25.1 mph**. Exact offline construction, all 11 diagnostic compatibility checks with removed-sign-context rejection, and recorded-only saved processing passed. `cases/above/construction.json`, `cases/above/compatibility.json`, `cases/above/negative-analysis.log`, `cases/above/saved-processing.json` and `execution-manifest-above-processing.json` pin the proof. Static `check_receipts` returned true across all three primary cases. Its source history still measures **0.1236901875 mph** in-zone, so it is **not** an observed above-posted case. Public authority, sign visibility, highway governance, scene/source-map consistency and physical target attainment remain unresolved.

## Remaining work

Build the exact outside-zone construction and three distinct physical-risk fallback candidates per selected case, with offline, positive/negative compatibility and saved-processing proofs. Supply source-backed public-authority posting, sign face and value/unit, governed road portion and direction, narrow-road geometry, actual Native sign actor/landmark and original velocity/road-s history. Then independently audit camera visibility, fixed-condition comparisons and delivery. Keep `result.json` partial until strict delivery readiness passes. No frozen input, runtime or batch file was edited.
