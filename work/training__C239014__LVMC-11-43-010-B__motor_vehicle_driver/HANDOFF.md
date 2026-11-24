# training__C239014__LVMC-11-43-010-B__motor_vehicle_driver

Status: partial CPU construction checkpoint. Neither exact case is promoted to selected delivery; original Native, physical and legal outcomes are unclaimed.

The exact law requires a roundabout entering driver to yield to vehicles already inside and wait for a traffic gap. The frozen cell is a roundabout entry with another vehicle. `case-plan.json` preserves the two planned comparison IDs. Six historical accepted rows are membership-only; no source-hashed equivalence receipt exists and no original is proposed for replay.

## Current exact construction and tests

`native/gap_request.py` generates two 600-frame, 20 Hz, 30-second authored entry requests for the exact planned case IDs. The waited condition releases the ego at 17.0 s; the early-entry condition releases it at 12.5 s. Circulating actors cross the modeled entry conflict neighborhood at about 12 s and 24 s in both conditions. The diagnostic checks source identity, 600 frame/time joins, both circulating actor rows, ego continuity, wait/entry order, and the previous and following conflict brackets. It rejects missing actor sources, a missing frame and a forged `original_native` label. Its six-metre neighborhood is an engineering proxy, never a statutory gap threshold.

`native/build_draft.py` authors `condition_a-construction.json` and `condition_b-construction.json` with exact IDs, 30-second capture and four named source-camera contracts. The pinned `runtime.py offline` command passed for each. These remain unselected inline drafts because they do not yet include Native capture, source-bound compatibility or process-saved finalization.

`native/measurement-contract.json` maps all ten summary observation terms to the original actor, map, frame and camera sources to retain. It is a draft measurement plan, not a completed saved finalizer.

Proof and hashes:

- `native/gap_request.py`: `ac7577eee77331f148c5cf7d8e3bb50bd8863d85b6171f401234f8f18c81de0f`
- `native/gap-diagnostic-proof.json`: `1b799c911bffe955def1b1986f22a23da46f0dfb253b57e9ce53f1984e6f3bb8`
- `native/measurement-contract.json`: `42f9104a444a39f36074bea82b9dde20211572da481699b149cd29e567f54be7`
- `native/condition_a-construction.json`: `727f61a1a1bd29ee56c2240f9169abe00027df3eb32856c11a58753c541e1639`; passing `native/condition-a-offline.log`: `1964d08abef53a00d5139c86b1302367e404a83a989853237bd873f53f210663`
- `native/condition_b-construction.json`: `f5f23270ecd8c0f589810db306e002b23e594c48f8e9ef0274ff5c277fd06c5d`; passing `native/condition-b-offline.log`: `41fdf2b4067b1937379bd317753540a41db54505a5cc6d81d6ac619498f32ee3`

The generated request rows and negative fixtures are under ignored `.runtime-work/c239014-gap/`. The two offline bundles are under `.runtime-work/c239014-gap-offline-a/` and `-b/`.

Passed commands:

```text
.venv-cpu/bin/python runtime.py preflight
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C239014__LVMC-11-43-010-B__motor_vehicle_driver/native/gap_request.py prove --output .runtime-work/c239014-gap
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline --manifest work/training__C239014__LVMC-11-43-010-B__motor_vehicle_driver/native/draft-manifest.json --case training__C239014__LVMC-11-43-010-B__motor_vehicle_driver__selected_a60a4f45__condition_a --output .runtime-work/c239014-gap-offline-a
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline --manifest work/training__C239014__LVMC-11-43-010-B__motor_vehicle_driver/native/draft-manifest.json --case training__C239014__LVMC-11-43-010-B__motor_vehicle_driver__selected_a60a4f45__condition_b --output .runtime-work/c239014-gap-offline-b
.venv-cpu/bin/python worker_check.py --assignment training__C239014__LVMC-11-43-010-B__motor_vehicle_driver --complete
```

## Next CPU work

Implement connected Native roundabout geometry and actual ego/circulating actor controllers for both exact cases, retaining all four synchronized source cameras. Bind original actor/map/frame readback and sealed capture to a saved finalizer. Add current source-bound positive/negative `runtime.py compatibility` receipts and actual `process-saved` fixtures for the two exact cases. Build and test candidate fallbacks for concrete physical risks, independent delivery and comparison audits, canonical semantic proposals, and execution-manifest bindings. Run the assignment-scoped strict gate before any ready status. These are worker-owned CPU gaps.

Later physical review must confirm realized ring topology, yield behavior, cameras and observed gap. Neither diagnostic condition assigns a legal outcome.
