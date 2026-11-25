# training__C230222__LVMC-11-30-050__pedestrian

Status: ready, delivery_prepared. On 2026-11-24 the exact scoped strict gate passed:

```text
.venv-cpu/bin/python worker_check.py --assignment training__C230222__LVMC-11-30-050__pedestrian --complete --require-delivery-ready
static_checks_passed: true
```

The selected exact cases are:

- `training__C230222__LVMC-11-30-050__pedestrian__selected_c0238853__condition_a`: requested right-angle route.
- `training__C230222__LVMC-11-30-050__pedestrian__selected_c0238853__condition_b`: requested longer diagonal route.

The frozen rule allows a route at right angles to the curb or the shortest route to the opposite curb, with a crosswalk exception. The two cases share the law, authored road and curb context, pedestrian controller, 30-second/600-frame window, and synchronized four-camera profile. The route heading and path are the deliberate comparison difference. No legal verdict is embedded in the capture or measurement code.

`execution-manifest.json` binds a current-runtime primary and spawn-clearance fallback for each case, selected Native construction, proof receipts, semantic stages, physical risk review, and original-rejecting delivery acceptance. Four selected `runtime.py compatibility` proofs passed Native validation, Lean conversion, render/decode, source-bound route and outside-crosswalk measurements, and missing-source rejection. Four `runtime.py process-saved` receipts passed recorded-only replay. The original source hashes are preserved in the diagnostic receipts. Runtime source manifest SHA-256: `5e2dd81ac49dd2d9814a10b71ee30cf85323868a8369116020b06a69cbfcc5e3`.

`delivery_audit.py` passed both full-size synthetic diagnostic positives and rejected both when original Native source was required. `delivery-proofs/` contains the diagnostic and rejection logs. `native/prove_route_meter.py`, `prove_comparison.py`, `prove_finalizer.py`, `prove_full_finalizer.py`, and `prove_physical.py` passed their source-join, changed-condition, missing-source and physical-risk CPU checks. The root `tests/test_offline.py` passed four tests; `root-tests.log` is bound in `result.json`. The semantic and execution manifest validators and both delivery handoff validators passed before the scoped gate.

The package is prepared for the first GPU job shown in `result.json`. The original CARLA capture, source-pixel/map review, final physical acceptance, and legal interpretation remain to be performed on the resulting evidence; synthetic CPU diagnostics make no claim that those outcomes occurred. No accepted membership row was reused.

Scratch diagnostics and temporary media remain under `.runtime-work/c230222-lvmc-route/`. The committed package is self-contained under this assignment's work directory. Previous draft checkpoints were superseded by the selected v5 proofs bound in `selected-proofs/`.
