# NRS 484B.493 at C135709: CPU checkpoint

Actor: `motor_vehicle_driver`; frozen `narrow_road` / `park` / `parking_restriction_device` cell. The frozen law prohibits standing or parking on the left-hand side of a one-way street when official traffic-control devices are erected giving notice. The witness permits converting this narrow road to a one-way street but supplies no accepted recording. Official notice, one-way legal designation, city/public street context and standing/parking purpose still require sources. The exact law and frozen witness hashes remain in `case-plan.json` and the saved diagnostic proof.

## Constructed and checked

- `native/geometry.py` authors a 120 m one-way street draft with one permitted-direction driving lane, both curb shoulders and a left-side NO STANDING OR PARKING signal. OpenDRIVE alone does not establish official authority, legal one-way designation or visible sign pixels.
- `native/runner.py` contains a side-parameterized motor-vehicle parking controller, surveyed lane/sign readback, four synchronized 1280×720 FFV1 camera streams, 600 frames at 20 Hz, original `FrameMap`, measured actor transform/velocity/rotated footprint, and world restore/actor cleanup. Native execution has not occurred.
- `build_draft.py` binds separate right-side `controlled_1` and left-side `controlled_2` primary constructions in `draft-one-way-manifest.json`. Their construction SHA-256 values are `26586f0f60ea2a1222f0b7baa1624e47abe48cc4d0bcf044e5e0ee74df0e7a0f` and `7ec4f174b5c1d3a1c712837fe60ad4ff8eed269bc4f6a9bbc7d38d8bb5fa5890`. Both passed pinned `runtime.py offline` using `.venv-cpu/bin/python`; logs `controlled-1-offline.log` and `controlled-2-offline.log` each hash to `821e113393c861bdea172700dc56365e7b368ef92ecbd2473488fd0871530853`.
- `one_way_saved_measure.py` measures a saved vehicle footprint against the permitted-direction centerline and governed extent. It requires source hashes for the map, legal one-way designation, street boundary, official authority, notice content and erection. It joins original vehicle poses, `FrameMap` and OpenDRIVE bytes. `prove_one_way_saved_measure.py` passes four 600-frame synthetic positives (left, right, centerline-straddling, outside extent) and ten missing/changed-source negatives in regular and optimized Python. Both proof logs hash to `70613c7128249ea3cb3cb23419fb59b5c64a82ff19fbafea18383db5bce4dd7d`. The 0.1 m/s stationary flag is a measurement tolerance, never a legal definition of standing or parking.
- `.venv-cpu/bin/python worker_check.py --assignment training__C135709__NRS-484B-493__motor_vehicle_driver --complete` exits 0 for this partial checkpoint.

## Exact remaining CPU work

1. Add source-backed standing-purpose alternatives and controlled absent-notice/two-way cases without changing the frozen cell or inventing legal cutoffs. Review whether the parked pair should remain selected after branch decomposition.
2. Complete Native saved finalization from original traces and separately reviewed authority/designation sources. The draft Native `road-context.json` intentionally leaves official authority and one-way legal designation null; the reducer rejects them until proven. Test actual saved-only processing, four video decodes and source-damaged negatives.
3. Add risk-triggered fallback constructions, exact compatibility receipts, Core and semantic proposals, independent delivery and comparison audits, and finalizer-bound manifest entries. Run the assignment strict ready gate only after these CPU proofs pass.

Physical motion, sign pixels, authority, legal conclusion and accepted set membership are not claimed. Status remains `partial`.
