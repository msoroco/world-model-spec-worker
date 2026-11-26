# C42387 handoff

Assignment: `training__C42387__NRS-484B-413-2__motor_vehicle_driver`. Exact pinned input SHA-256: `e5094e09edb8c17b05d10041b84d55435a00bf8d11e1d571261b1ea5ca200478`.

Status: `ready` for CPU delivery preparation. Original Native capture, physical maneuver, pixel review, and canonical demo-train/full-train acceptance have not been claimed.

## Exact selected construction

- Three fixed business-district right-turn cases request continuous right signaling at 35 m, 30.48 m (the source 100-foot boundary), and 20 m. The comparison measures observed lamp-on path distance from saved Native source, independently of the request.
- OpenDRIVE contains a connected 200 m approach and turn, an opposing lane with a separately spawned vehicle, and 100 m of authored business-use frontage in the 200 m approach. The frozen witness requires at least 300 feet of qualifying frontage within a 600-foot highway interval; original classification remains for Native and legal review.
- Primary and lookahead fallback constructions passed exact offline checks for each case. Fallback is selected on original route error, not on a desired legal result.
- Four 20 Hz cameras and 600 frame source joins are specified for each case. Native capture remains unexecuted.

## CPU proof evidence

- Six selected public compatibility checks passed with positive source-shaped fixtures and missing-source negatives.
- All nine physical checker outcomes passed: complete motion, incomplete motion, and missing evidence for each case. These are synthetic mechanics tests.
- Three recorded-only saved processing positives passed; removing `control_context.json` produced missing-source feedback without Native replay for each.
- The independent delivery audit passed positive synthetic mechanics and rejected an out-of-bounds pixel review for each case.
- The three-way comparison source-hash audit passed with fixed conditions and separately measured distances; removing a comparison source was rejected.
- The branch audit checked the frozen 100-foot business witness and exact same-law 300-foot and left-turn delegated case IDs. Other course changes remain a separately selected source branch, not a claim of this fixed cell.
- Root and Native unit suites passed.
- Exact scoped gate passed: `.venv-cpu/bin/python worker_check.py --assignment training__C42387__NRS-484B-413-2__motor_vehicle_driver --complete --require-delivery-ready`.

## Stable hashes

- `case-plan.json`: `e8b74652f9594d0726452cc0573eea177ca5980a6c4c64a2ffa15197e7fb3cd8`
- `execution-manifest.json`: `36d6f3f71e69b69c1e7bcd420ed1e86dcaf28d89bf5e18db71ab71671f5af5f8`
- `proposals/semantic-index.json`: `07fae222591c5ce6f786e028d227ccf8b01d8615392f936240b2364ff5544ab2`
- `proposals/cases.json`: `092a0e1f2821f5d3fca98a7b8d22b4fd06d8b65661a7f9ef7ea1872d0a6f6004`
- `native/branch-scope-positive.json`: `220042fb60e454a35618d58ab9a4359556ddf82663b09cbaad22e03f8d9e9e1f`
- `native/comparison-three-positive.json`: `7369adc5b0619b1a12f9f66f8a3d3730c0c8444ff30a3f1fc2ce21d0a9166a55`
- `native/comparison-three-negative.log`: `0f9937b95ca9760398f0ea32fd734705a08dd10f62359d6f92e477bdc20911b0`
- `native/strict-check.log`: `b5cb64da4087b91eadbe30a56449d21a54cce1dc8d9aa09c441b7047db5308f2`
- `result.json`: `ddbee9fa0b432b9bfc0e3a6c5e2dd10818dc6be31f253a532c707f68a80ce757`

## Original execution still required

- Acquire an original Native recording; confirm the actual business frontage, highway context, other vehicle relationship, ego body route, and continuous right lamp pixels.
- Run the source-bound saved process and independent delivery/comparison audits on original recordings, then seek local acceptance into both target sets.
