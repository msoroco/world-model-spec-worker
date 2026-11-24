# C405647 / NRS 484B.267(1)(b) handoff

Status: `ready` / `delivery_prepared` on the active runtime. Exact scoped strict assignment check passed on 2026-11-24. This is CPU preparation for two selected cases, not an accepted original Native recording or a legal verdict.

## Reproduce the gate

From repository root, set `SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c405647-1b-runtime-import`, `TMPDIR=$PWD/.runtime-work`, and `PYTHONDONTWRITEBYTECODE=1`, then run:

```sh
.venv-cpu/bin/python worker_check.py --assignment training__C405647__NRS-484B-267-1b__motor_vehicle_driver --complete --require-delivery-ready
```

Exit code was 0 with `static_checks_passed: true`. `result.json` SHA-256: `ac4e63c1fa01f8ca7033a4aed7c1539699a05eb8bfbaa2d6626bb8fb86810c5f`; `case-plan.json`: `d9d799fe5ef39d879f871d4abdc6f53114720b4c28fd615641ee66a80cb29048`; `execution-manifest.json`: `3959847f66c4a64804284fe7786a383dc2ed0e8550c44fc8467ba1eaf36e614c`. Frozen assignment SHA-256: `0ee3f348d7db64723f6be4dab6257853965bc6626f68567df96d31ee3b5d01cd`; active runtime SHA-256: `5e2dd81ac49dd2d9814a10b71ee30cf85323868a8369116020b06a69cbfcc5e3`.

## Selected preparation

`execution-manifest.json` selects `__reference` and `__contrast`, each with a primary and two distinct fallback constructions. All six selected candidates pass current-runtime public positive compatibility, missing-source negative, pinned offline preflight, and recorded-only saved processing. Receipts and logs are in `current-public/`; source-hashed construction bundles are in `current-bundles/`. The current manifest has six selected candidate rows; older `draft-*` and `full-package-*` material describe unselected or retired proofs.

The 600-frame, 20 Hz synthetic fixture has four synchronized camera streams. `current-public/comparison-audit.json` SHA-256 `f529ecbc09a3471d2689030d31ca6f91e56e6b4e46f62de7e13a6fb718a0e71a` verifies the fixed case context and intended lateral-position difference. `statutory-branch-review.json` SHA-256 `ce1f4252278af953df1a0d2bbcc9d6fa6dcb26784a48ac319861dc42696c26b2` binds all 11 supplied statutory topics to selected diagnostic measurements and identifies original qualification gaps. The canonical semantic proposals pass all eight active stages. Root CPU tests pass, log `current-public/root-tests.log` SHA-256 `79897d011a1aaa76145e639592b1207fa563cb1187e00ac85c3ee31c86a0b15f`. Delivery audit positive diagnostic rehearsal passes, and normal acceptance rejects missing original Native source.

## Next physical and legal checks

The first original GPU job command is in `result.json`. On an exclusive idle CARLA server, execute the reference case and then the contrast case with their recorded source files; use fallback constructions only after their declared original-source trigger is measured. Verify actual motion and right-edge geometry, emergency vehicle authority and qualifying lamp pixels, shoulder signage and exceptions, synchronized four-view visibility and 30-second duration. Independently review the resulting original Native evidence and statutory qualifications before any physical acceptance or legal conclusion. The synthetic fixture and CPU receipts are diagnostic only; `carla_executed` is false and `recordings_accepted` is zero.
