# training__C394566__LVMC-11-48-060__motor_vehicle_driver

Status: **partial**. Current-runtime offline constructions and saved-finalizer source proofs pass; exact compatibility and strict readiness remain.

## Exact law and coverage

LVMC 11.48.060 bars use of a non-truck street as a through route from one truck route to another unless pickup, delivery or essential use is required enroute. The frozen C394566 motor-vehicle actor is surveyed as a truck. Full-train has no accepted recordings for this requirement. The two selected exact cases share road topology, truck class, camera policy, 30 seconds at 20 Hz and route geometry: `probe_01` has no reviewed enroute purpose; `probe_02` has an independently reviewed service premise and pickup, delivery or essential purpose plus a 100-frame service stop on the intervening road. Stop duration is an engineering observation, not a legal threshold or proof of purpose.

## Executable Native construction

The two selected cases and their faster-cruise `fallback1` candidates have inline bundles under `native/`. `native/selected-offline-manifest.json` binds each exact case and construction. Four-view source camera names now match the current runtime profile (`overview`, `approach`, `reference_corner`, `driver_reference`). The primary and fallback for each case pass `runtime.py offline`; unittest discovery ran 2 tests for `probe_01` and 3 for `probe_02` per candidate. The fallback trigger is failure of original source trace to reach the exit truck route within 600 frames, and its knobs are only speed target and throttle cap. These checks never start CARLA.

- `probe_01` `primary`: `selected-primary-construction.json` SHA-256 `598244756ae06b4addb5d2fe2118dce4cd0bedb804477e14766f3eda8f672f92`; `selected-primary-offline.log` SHA-256 `18b93cd3bd407fb07add22b3d4acac11ea486b1883d3d54f3131a3d22b4e275d`; exit 0.
- `probe_01` `fallback1`: `selected-primary-fallback1-construction.json` SHA-256 `b2326cf5f0ecf5e5c0453a786fa01b62973f0fa625aff51aff39c448c9f6e1eb`; `selected-primary-fallback1-offline.log` SHA-256 `18b93cd3bd407fb07add22b3d4acac11ea486b1883d3d54f3131a3d22b4e275d`; exit 0.
- `probe_02` `primary`: `selected-purpose-construction.json` SHA-256 `606f73c1ec656b347550a79862291c840ee8dc1bc6e22d0c61ad86c48cb68011`; `selected-purpose-offline.log` SHA-256 `62f2be104a6f3925639a4d920053414d3950e6a2ad2a983af2a5be020b73ea24`; exit 0.
- `probe_02` `fallback1`: `selected-purpose-fallback1-construction.json` SHA-256 `b3ccbf77cee75bd0f29a69ab474228f424c4695a5f8db995f6d8e1b273f19992`; `selected-purpose-fallback1-offline.log` SHA-256 `62f2be104a6f3925639a4d920053414d3950e6a2ad2a983af2a5be020b73ea24`; exit 0.

## Independent source checks

`native/measure_through_route.py` joins 600 original Native route rows, frame map and four decoded camera sources; requires independently reviewed truck-route designations, truck blueprint/class, connectivity, purpose and premises source. It rejects missing source/identity/hash and measures a complete three-road passage. `native/measure_purpose_route.py` also requires an original 100-frame service stop on the intervening street and reviewed non-none purpose. Neither script issues a legal verdict.

`native/prove_through_route.py` passes four route/purpose variants and rejects source, frame, actor, geometry, designation and purpose mutations. `native/comparison_audit.py` rereads both original source directories and checks shared route/designation/truck context, complete passages, spatial route/length tolerance, exact case identity and reviewed purpose difference. `native/prove_comparison.py` passes synthetic comparison and five negatives (wrong purpose, changed route source, changed truck class, incomplete and interrupted stop).

- Source proof log: `native/through-route-proof.log`, SHA-256 `059a50a0947dca56c0c8c80e90da414344881b1a3e7693d2837fa533640ae1e8`.
- Comparison proof log: `native/comparison-proof.log`, SHA-256 `57a0cea36d511b0805df0188855d69b21b1cab6ffd7719e0b40d21e34416aad4`.

## Remaining CPU work

Build the full current-runtime execution manifest, source-hashed fixture recipes, exact measurement contracts and Core finalizers for both cases and fallbacks. Run positive/negative `runtime.py compatibility` and recorded-only `runtime.py process-saved` receipts. Author the six semantic stage proposals and independent delivery acceptance audit; bind the comparison audit to the exact saved receipts. Add root canonical runner/config/construction/camera plan and then run `.venv-cpu/bin/python worker_check.py --assignment training__C394566__LVMC-11-48-060__motor_vehicle_driver --complete --require-delivery-ready`. Result remains partial until that command succeeds.

## Local physical review

The operator must survey a real connected two-truck-route journey over an intervening non-truck street, verify a truck blueprint and service premise, then independently inspect original route IDs, actor, purpose sources, camera pixels and physical completion. No CARLA run, original recording, canonical acceptance or legal verdict is claimed.

## Current-runtime diagnostic update (2026-11-24)

Both exact measurement contracts are `measurement-contract-probe_01.json` and `measurement-contract-probe_02.json`. Both source-hashed synthetic recipes are `fixture-recipe-probe_01.json` and `fixture-recipe-probe_02.json`; generated fixtures are kept under `.runtime-work/`. The four Native bundles now contain `finalize.py`, source-join analyzers and complete recording descriptions. `native/finalizer-proof.log` shows both 600-frame saved finalizers pass their case-specific measurement and reject missing `route_context.json`. The current-runtime decoder was built under `.runtime-work/c394566-decoder/`. First full `runtime.py compatibility` reached Core conversion and exposed missing synthetic graph frame and observed-evidence packet, both corrected. The next converter probe exposed missing synthetic `world`; the fixture builder now retains it. Re-run exact compatibility for both cases and fallbacks, then saved processing, physical fixtures, semantic stages and delivery audit. No CARLA or legal outcome is claimed.
## Current-runtime compatibility checkpoint

All four selected case/candidate pairs passed `.venv-cpu/bin/python runtime.py compatibility` using the current source-manifest runtime and source-hashed exact recipes. The four receipts and positive/negative logs are retained under `compat-p01-pr/`, `compat-p01-fb/`, `compat-p02-pr/`, and `compat-p02-fb/` and bound in `execution-manifest.json`. Each receipt states diagnostic software compatibility only; original physical route, pixels and purpose remain unverified. Saved-only processing, physical outcome fixtures, semantic proposals, delivery acceptance and the strict assignment gate remain CPU work. Status remains partial.

## Saved-only and physical CPU checkpoint

`runtime.py process-saved` passed for exact `probe_01` and `probe_02` primary diagnostic attempts: 600 original frame joins, selected analysis, converter, final video checks and unchanged original sources. Receipts are `saved-p01-processing.json` and `saved-p02-processing.json`. `native/prove_physical.py` passed complete three-road route, incomplete route and missing-route-source fixture outcomes for each case and a capture/owner lifecycle order check; all are synthetic and bound in `execution-manifest.json` under `physical/`. Candidate fallback validators passed locally. Semantic proposals, independent delivery acceptance, comparison binding and strict assignment gate remain.

## Canonical proposals and delivery audit

The six semantic stage files are under `proposals/` and `semantic-validation.log` confirms source-hashed stage validation for two exact cases. The qualitative enroute essential-use judgment is retained with an incomplete numeric sweep specification because the law supplies no numeric meaning and the frozen delivery comparison uses independently reviewed purpose context; this is an unresolved judgment, not a legal outcome. The root `runner.py`, `config.json`, `construction.json` and `case-plan.json.camera_plan` now cover the two exact cases; `root-runner-check.log` shows offline check without CARLA import. `audit-selected-delivery.py` passes positive and missing Native-route-source negative tests for each case against synthetic source and saved receipts, and both delivery acceptance specifications validate. An independent comparison initially rejected the service-stop diagnostic because it had 10 m less route progress; the diagnostic builder was corrected to preserve spatial route length while retaining the 100-frame stop. Probe_02 compatibility and saved-only proofs are being regenerated against the corrected source.

## Physical progress correction

A source-bound comparison had passed after restoring the service-stop path length, but the runtime `physical_checks.maneuver` still reported `not_met` because both diagnostics traveled only about 60 m against its 75 m engineering progress floor. `native/build_diagnostic.py` now generates approximately 84 m of route travel with speed samples consistent with sampled position, retaining all three road IDs and the original 100-frame service stop. The independent comparison audit passes this corrected pair. All four exact compatibility and both saved-only receipts must be regenerated against these new source hashes before readiness. The physical threshold is an engineering diagnostic, not statutory meaning.
