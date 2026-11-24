# C230211 protected pavement checkpoint

Status: partial. Exact scoped strict gate exits 1 because this result remains partial.

## Constructed CPU scope

`pavement_protection.py` source-gates jurisdiction, driver/vehicle, newly laid/repaired pavement, protection geometry and timing, route, and same-pavement active employee work. It constructs actual barrier or warning person/sign and vehicle route with actor cleanup. Its 900-frame original finalizer detects physical crossing versus bypass from source-linked positions; legal effect stays unresolved.

Seven exact cases and six controlled comparisons in `case-plan.json` cover across/around barrier, bypass, warning person/sign, closed-highway sign and active employee exception. Frozen evidence inventory has no accepted recording. The cell selects a motor vehicle driver; horse riding is a law alternative outside that actor scope.

## CPU proof receipts

- `case-plan.json` SHA256 `bde329130c1591a7dd9bad9eed9a7bc88da8b35e60a2a0e8670fce7089049d34`
- `pavement_protection.py` SHA256 `8af918ec8597f9ab55d585c1fa88bb7fb5b93565ac66f0d1f3851b19361c840c`
- `tests/test_pavement_protection.py` SHA256 `c65bbf10301234c6863b8fb2d2b462d23802edd6753b9b2349094774c9ae6354`
- `cpu-tests.log` SHA256 `c41663a5c53eaa21e04f52adfd4ce5eca720c48ab11f707e2f88372b12ee8e41`
- `cpu-preflight.log` SHA256 `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`
- `cpu-static-check.log` SHA256 `2ded6905989fdd32fa4c3a9ed477bfd6b13f5f6095724655ae7f8925297b5c01`
- `cpu-strict-check.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`

Focused unittest exit 0 (3 tests); pinned `runtime.py preflight` exit 0; scoped static `worker_check.py --assignment testing__C230211__LVMC-11-22-100__motor_vehicle_driver` exit 0; same exact scoped strict with `--complete --require-delivery-ready` exit 1 on truthful partial. `result.json.tests` includes only passing commands with package-relative logs and SHA256.

## Remaining CPU work

Create canonical selected-case runtime bundles, source-bound positive/negative compatibility, saved-only processing, semantic proposals, and independent delivery/comparison audits. Establish physical placement timing in original captured data. Then rerun scoped strict. Actual CARLA motion and camera coverage remain physical review after CPU readiness.
