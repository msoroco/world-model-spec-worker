# Bus school crossing zone: NRS 484B.363(2)

CPU package: eight selected constructions passed current-runtime offline, public positive and missing-source compatibility, recorded-only saved processing, physical/lifecycle diagnostics and independent delivery audits. Five controlled comparisons passed positive and missing-member negative audits. Original Native recording and independent source review remain pending.

## Statutory coverage

The full text fixes 25 mph in a designated school crossing zone while the limit applies. It separately excepts (a) no school session day, (b) the period from a half hour after school operation ends to a half hour before it next begins, (c) an operational beacon during class hours when its yellow lights are not flashing, and (d) a nonbeacon sign indicating the limit is inactive. The beacon definition requires a sign with at least two alternating yellow lights. Children present do not resolve an exception. Official designation and operation are original-source review facts.

## Exact selected cases

- `training__C255451__NRS-484B-363-2__bus_driver__selected_d08892c9__condition_a`
- `training__C255451__NRS-484B-363-2__bus_driver__selected_d08892c9__at_limit`
- `training__C255451__NRS-484B-363-2__bus_driver__selected_d08892c9__condition_b`
- `training__C255451__NRS-484B-363-2__bus_driver__selected_d08892c9__no_school_day`
- `training__C255451__NRS-484B-363-2__bus_driver__selected_d08892c9__half_hour_window`
- `training__C255451__NRS-484B-363-2__bus_driver__selected_d08892c9__beacon_not_flashing`
- `training__C255451__NRS-484B-363-2__bus_driver__selected_d08892c9__nonbeacon_sign_active`
- `training__C255451__NRS-484B-363-2__bus_driver__selected_d08892c9__nonbeacon_sign_inactive`

## Controlled comparisons

- `training__C255451__NRS-484B-363-2__bus_driver__selected_d08892c9__speed_boundary`: ["measured motor-bus speed below, at and above express 25 mph"]
- `training__C255451__NRS-484B-363-2__bus_driver__selected_d08892c9__no_school_day`: ["independently reviewed school-session day status"]
- `training__C255451__NRS-484B-363-2__bus_driver__selected_d08892c9__half_hour_window`: ["independently reviewed civil time relative to school operating hours"]
- `training__C255451__NRS-484B-363-2__bus_driver__selected_d08892c9__beacon_flash`: ["observed alternating yellow-light flash during pupils-in-class hours"]
- `training__C255451__NRS-484B-363-2__bus_driver__selected_d08892c9__nonbeacon_sign`: ["independently reviewed sign effective-hours indication without operational beacon"]

`case-plan.json` maps all seven frozen observation terms and every selected requirement to the cases. `proposals/semantic-index.json` binds canonical stages. Root `runner.py`, `config.json` and `construction.json` dispatch eight selected cases with 30 seconds at 20 Hz and synchronized overview, approach, reference corner and driver reference views. Exact selected constructions live under `native/selected/<condition>/construction.json`.

## CPU proof and replay

`execution-manifest.json` binds exact construction hashes, offline and public compatibility receipts, measurement contracts and diagnostic recipes, recorded-only saved-processing logs, three physical outcomes and lifecycle order, independent delivery positive/negative audits, and per-case fallback risk assessments. All software fixture evidence is synthetic; none proves actual motion, pixels or legal outcome.

Run from repository root with `.venv-cpu/bin/python`, `TMPDIR=$PWD/.runtime-work`, and `SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c255451-check`. Existing proof outputs are retained; choose new scratch names before replaying materialization or processing.

- `native/prove_selected_offline.py`: 8/8 current-runtime selected offline checks.
- `native/prove_selected_compat.py`: 8/8 public positive and missing-source negative compatibility checks.
- `native/prove_recorded_only.py`: 8/8 current-hash saved-only processing paths under `.runtime-work/c255451-recorded-v3-*`.
- `native/prove_physical.py`: each case has source-bound complete, incomplete and absent motion outcomes plus Native-exit/owner-release-before-processing lifecycle.
- `native/prove_delivery.py`: 8/8 independent 600-frame, three-participant, four-video audits and missing-original-source negatives.
- `native/prove_comparisons.py`: 5/5 fixed-source comparison audits and missing-member negatives.
- `tests/selected-bundle.log`: six selected runner template tests passed.
- `tests/root-package.log`: two root dispatch/camera plan tests passed.

## Original delivery review

Source-survey the officially designated school crossing zone, installed 25 mph sign, actor/asset geometry and approach visibility. Beacon cases require sign-mounted distinct yellow lamp actors and the alternating controller source; nonbeacon cases require separate sign schedule source. Confirm calendar and school hours, civil time, motor-bus class, actual speed, complete traversal, four-view pixel visibility and all 600 joined frames. The CPU fixtures and expected labels do not replace original sources. Local canonical acceptance and legal judgment remain separate.

The first GPU command is in `result.json` once the strict scoped gate passes. The lead integrates this exact package into the shared ordered queue. No CARLA or GPU run occurred here.

The exact scoped gate `.venv-cpu/bin/python -B worker_check.py --assignment training__C255451__NRS-484B-363-2__bus_driver --complete --require-delivery-ready` passed on the current runtime with `static_checks_passed: true`.
