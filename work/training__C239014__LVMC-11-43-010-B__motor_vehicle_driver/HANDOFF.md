# C239014 roundabout entry handoff

Status: **ready for first GPU delivery**, based on CPU preparation and the exact assignment-scoped strict gate. No Native capture or legal/physical acceptance is claimed.

## Selected scope

LVMC 11.43.010(B) requires the entering driver to yield to vehicles already within the roundabout and wait for a traffic gap. The frozen reviewed witness selects two exact conditions that vary only the requested ego entry-release time (17.0 s and 12.5 s). All ten frozen observation terms have source-joined channels. Original roundabout boundary, actual circulating occupancy, traffic response, sufficient-gap judgment and visible source pixels remain delivery review items.

The six-metre conflict neighborhood, 0.2 m/s stop proxy, and frame timing are engineering diagnostics. They are not legal thresholds. The six accepted full-train recording IDs in the frozen inventory are membership rows, with no source-hashed equivalence reuse.

## CPU proof

The authored OpenDRIVE ring and approach, three-actor Native controller, PipelineCapture path, four FFV1 cameras, source-sealed capture lifecycle, and saved-only finalizer are in `native/`. Both primary and risk-based steering fallback candidates pass pinned offline checks and positive/missing-map public compatibility. Recorded-only saved processing passes for both primary source-shaped fixtures. Independent delivery and controlled-comparison diagnostic audits pass, and source-tamper negatives reject. The seven-stage semantic chain validates; its judgment sweep remains explicitly incomplete pending original physical and legal review. Synthetic fixtures are identified as such throughout.

Execution manifest SHA-256: `08fda4047d06c8e1315392fb88d1ab421e76cd073534fcc92cf0b89b26a4403e`. Semantic index SHA-256: `6d4edf3b1af0387a9349b0127e87097ebd10064c3963c5c7a4b7647b9e254c09`.

| Condition | Primary construction | Fallback construction | Primary compatibility | Fallback compatibility |
| --- | --- | --- | --- | --- |
| condition_a | `081a742735085ebfe85aafb0e5c50c17aa4e4ccb5bbf821882dcc99e3f302a38` | `6148a6ae1d02b51037bc65e539b5867fdf82a72c7bafc11adbefca4ed0676f49` | `232d393b562e1622e3d64053062ce89e1185453be336656c45fd13d689db0715` | `267834d0086259dde9df45df456a6b09857e466ed05e885ea58f4bdc99d99b26` |
| condition_b | `1297636772ffbda5df9fde5e5e8d5097125c2f81c2846406a7b46a3aca30a2b1` | `1d1754087689090dd321795098c2e942f98e677ef2b0a7ed422346249a2f723a` | `c09f31d7e88a464b5fd2786df0f9357be221b78a337a637310f91358e79894d7` | `6d067fecfb9c7e64bfa5d5c3b95c8da5a731a973554b8891e0d0709b42859ded` |

## Delivery

Run the canonical exact job with the owner-held CARLA endpoint, then inspect the sealed original source, four decoded camera streams, physical completion, participant histories, entry chronology and legal applicability. The independent original-mode audit requires `original-physical-review.json` and rejects missing or stale original source hashes.

First job command:

```sh
PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python -m worker_exchange execute-delivery --repo . --batch full-train-delivery --db $DB --assignment training__C239014__LVMC-11-43-010-B__motor_vehicle_driver --case training__C239014__LVMC-11-43-010-B__motor_vehicle_driver__selected_a60a4f45__condition_a --run $RUN --job $JOB_ID --python $CARLA_PYTHON --host $CARLA_HOST --port $CARLA_PORT
```

The exact scoped gate passed:

```sh
.venv-cpu/bin/python worker_check.py --assignment training__C239014__LVMC-11-43-010-B__motor_vehicle_driver --complete --require-delivery-ready
```

The selected manifest binds exact offline logs, primary and fallback public receipts, saved processing summaries, three synthetic physical outcomes, a six-event owner lifecycle, and positive/negative independent delivery audit logs. `case-plan.json` binds the positive/negative comparison audit. All generated videos and attempt trees remain under `.runtime-work`.
