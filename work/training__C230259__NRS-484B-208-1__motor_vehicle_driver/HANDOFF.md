# C230259 / NRS 484B.208(1)-(2) / motor vehicle driver

Status: ready for first Native delivery. The exact assignment-scoped CPU gate passed on 2026-11-25. No original CARLA run, accepted recording, physical completion, or legal verdict is claimed.

## Selected witness and source limits

The selected reference and contrast use the same authored two marked, same-direction lanes, subject and faster rear motor vehicle, 20 Hz / 600-frame duration, weather, cameras, and road context. Only `slow_extreme_left_lane_continuation` differs: reference continues in the extreme left lane after the rear crossing; contrast exits before the crossing. The independent diagnostic audit measured 400 post-crossing left-lane frames of difference. This is a source-bound synthetic contrast, not proof that a real controlled-access highway, posted limit, driver knowledge, or subsection 2 necessity exists.

The source law is NRS 484B.208(1) with subsection (2). The reviewed exceptions are subject overtaking another vehicle, preparing a left turn, HOV designation and eligibility, construction/maintenance/repair or snow removal, traffic/weather/obstruction/hazard necessity, official control device or officer direction, authorized emergency duty, and a location within a city or town. The semantic template and recorded context retain these as review questions. Source-grounded facility classification, original posted-speed authority and driver notice, city boundary, HOV authorization, emergency duty, and each qualitative necessity exception remain unresolved. The accepted-evidence inventory had no recording for this exact assignment, and no equivalence or law finding is inferred from the synthetic fixtures.

## Current-runtime CPU package

`execution-manifest.json` (SHA-256 `84fdcb14377c319365bd65ec9bf9d9f62d274ba414ff2bb3b340de16fdf66f94`) selects two exact cases with primary and fallback candidates each. All four exact offline logs, public compatibility positives with missing-source negatives, and recorded-only `process-saved` receipts are bound under `proofs/{reference,contrast}/{primary,fallback1}/`. The saved receipts report `passed`, `recorded_only`, and `originals_preserved`, with `missing_evidence=false`; their remaining items explicitly include original pixels/physical completion and legal judgments. `proposals/semantic-index.json` (SHA-256 `fdd552d85f87cda0135cd4fc218066386b624c99bde7fcdb9aba872252cd5566`) binds canonical relevance, template, three judgment observables, cell bindings and cases.

The executable Native construction is `runner.py`, `capture.py`, `finalize.py`, `geometry.py`, `road.xodr`, `config.json`, and `construction.json`; CPU tests passed in `top-level-tests.log`. Native capture is designed to record 600 original actor/map/trace rows and four synchronized videos, restore world settings, close encoders, and seal acquisition only after successful completion. It has not yet run against CARLA. Six engineering physical triad fixtures passed, with two receipts `physical-reference-preparation.json` and `physical-contrast-preparation.json`; these fixtures do not assert physical completion.

Independent delivery audits passed on both synthetic primary attempts and rejected both as physical deliveries without `capture-seal.json`. The independent `comparison-main-audit.json` (SHA-256 `e081d49084090a8c0055f40ac2a098bf3d33a99ebe3d27934ef1a2bb174c1d2c`) checks fixed conditions and original source hashes. The exact `.venv-cpu/bin/python worker_check.py --assignment training__C230259__NRS-484B-208-1__motor_vehicle_driver --complete --require-delivery-ready` passed; `strict-assignment.log` has SHA-256 `b6999347890d54be3d835929d6a9cc89cd8a7d0257d525a728f71af708675b52`.

## First delivery and review

Use the exact `first_gpu_delivery_command` in `result.json`. After Native capture, inspect its acquisition seal, all four original camera views, actor/map/time joins, physical maneuver evidence, driver notice and posting, and subsection 2 context. Keep the legal outcome unresolved until that independent source review is complete. The saved processing path uses the selected manifest and recorded source bytes only.
