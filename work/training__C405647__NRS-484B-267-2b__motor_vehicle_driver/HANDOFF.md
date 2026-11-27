# NRS 484B.267(2)(b) at C405647

Status: CPU delivery prepared under the current pinned runtime. Five exact cases are planned; no original recording was executed or accepted. The scoped strict gate passed with `.venv-cpu/bin/python worker_check.py --assignment training__C405647__NRS-484B-267-2b__motor_vehicle_driver --complete --require-delivery-ready`. Use `PYTHONDONTWRITEBYTECODE=1` for Python commands and keep all temporary output under `.runtime-work/`.

## Exact scope and coverage

The frozen actor is `motor_vehicle_driver`; the cell is road/travel/emergency_vehicle. The full source in `inputs/training__C405647__NRS-484B-267-2b__motor_vehicle_driver/assignment.json` requires an approaching driver, a moving or visibly preparing authorized emergency or regulatory agency vehicle, qualifying flashing lights, and the law enforcement direction exception. “Proceed with caution” has no statutory speed, gap, braking or time-to-conflict cutoff. The original witness in `witnesses.json` selects the already moving branch and specifically rejects adding a separate duty throughout passing. The five cases and four controlled comparisons in `case-plan.json` cover the compatible alternatives:

| Exact case suffix | Branch or contrast | Paired comparison |
| --- | --- | --- |
| `probe_01` | Moving authorized emergency vehicle; slower, wider approach | Reference for all four comparisons |
| `probe_02` | Faster, closer approach with the same qualifying vehicle | `caution_response` |
| `probe_03` | Moving official regulatory agency vehicle | `qualifying_role` |
| `probe_04` | Stationary vehicle with a visibly preparing driver hand signal | `moving_or_preparing` |
| `probe_05` | Distinct law enforcement officer direction | `officer_direction` |

There is no accepted recording in the supplied membership or evidence inventory, so no reuse is claimed. `statutory-source-audit.json` records the independent exact text review. The assigned law has no numeric legal boundary; the requested speed and margin values are engineering probes only.

## Construction and source processing

`runner.py` uses `road_geometry.py` to generate a two-directional OpenDRIVE road, spawns the subject and qualifying vehicle in separate readback-checked Native lanes, controls the requested trajectories, and writes `road.xodr` with 600 original Native samples and four synchronized 20 Hz camera streams. `hand_signal_pose.py` supplies the requested source-driver or officer gesture; original pixels and role identity still require review. `source_review.py` rejects missing or unbound authorization, equipment qualification, lamps, lanes, weather, traffic, hand signal and officer sources. `saved_measure.py` joins 600 original frames; `finalize.py` writes source-backed diagnostic channels and Native results while leaving legal compliance unassessed. `delivery_audit.py` and `comparison_audit.py` independently reject synthetic delivery or broken fixed conditions. Actual Native outcomes and source reviews remain local GPU and human checks.

`execution-manifest.json` binds each `cases/probe_0N/construction.json`, `measurement-contract.json`, `fixture-recipe.json`, and `proposals/semantic-index.json`. Every selected disposition has exact case IDs and source-backed measurement outputs. Each case assessed candidate risk as none; a fallback cannot establish missing legal authorization, original pixel visibility, or a qualitative legal judgment, and the controlled primary has no demonstrated recoverable motion failure. No untested fallback is returned.

## CPU proofs and resume

`proofs/01-...` through `proofs/05-...` contain current-runtime offline logs, positive and missing-source negative compatibility receipts, three physical completion fixtures, ordered ownership lifecycle tests, saved-only processing logs, and independent delivery audit rejection logs. `proofs/comparison-proofs.json` binds four positive fixed-condition and swapped-case negative audits. The fixture videos are generated diagnostics, never original evidence. The full proof commands are recorded in `execution-manifest.json` and `proofs/01-physical-proof.json` through `proofs/05-physical-proof.json`.

The independent validation commands were:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py verify --runtime runtime
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py preflight
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/training__C405647__NRS-484B-267-2b__motor_vehicle_driver/tests -p 'test*.py'
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python worker_check.py --assignment training__C405647__NRS-484B-267-2b__motor_vehicle_driver --complete --require-delivery-ready
```

Local dispatch must prepare and execute each exact case under the canonical job, review original authorization, flashing-light equipment and pixels, visible preparation or officer direction where requested, then run recorded-only processing, source and comparison audits, and exact full-train acceptance. The first canonical GPU command is in `result.json`; the lead integrates all five cases and four comparisons into the shared queue. Unknown CARLA motion, actor visibility, original qualification, qualitative caution and canonical acceptance remain unconfirmed.
