# C147311 one-way direction checkpoint

Status: partial. Exact scoped strict gate exits 1 because this result remains partial.

## Constructed CPU scope

`one_way_direction.py` source-gates a public dedicated, multilane one-way highway, authorized governing sign, qualifying driver/vehicle and lane-specific route. It constructs the physical sign and vehicle route and measures actual original velocity projected on the designated road vector over 900 joined frames; heading alone is not used.

Four exact cases and four comparisons in `case-plan.json` cover both same-direction lanes and designated versus opposed travel. The two frozen accepted lane-one metadata entries remain preserved with source review pending. Their original traces/video are absent; metadata and authored review settings do not prove actual direction or comparison isolation. No duplicate lane-one recording is proposed by this checkpoint.

## CPU proof receipts

- `case-plan.json` SHA256 `cfcedcf51d837c1d52217457d672c7b4a88ef5a96b95fb329f0548e27511e789`
- `one_way_direction.py` SHA256 `34d98c4f0fe2469761d5a6008e0a500d59a653e1bf6d9f2e64c152fa8d508c81`
- `tests/test_one_way_direction.py` SHA256 `ca56cade772ab58b2f3ce2ce036c4845a6e80f48b386ec2d9ae8546175f849a2`
- `cpu-tests.log` SHA256 `a05f822b4c1a575e0d81442778896e23bedea51119efbae0ba2ff1e1b8c478cc`
- `cpu-preflight.log` SHA256 `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`
- `cpu-static-check.log` SHA256 `44477c53eaa70167331894dacb9d2162ec93757b9c05d35170548a95bffe475a`
- `cpu-strict-check.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`

Focused unittest exit 0 (3 tests); pinned `runtime.py preflight` exit 0; scoped static `worker_check.py --assignment testing__C147311__NRS-484B-220-1__motor_vehicle_driver` exit 0; exact scoped strict with `--complete --require-delivery-ready` exit 1 on truthful partial. `result.json.tests` includes only successful commands with package-relative logs and SHA256.

## Remaining CPU work

Create canonical selected-case bundles and source-bound positive/negative compatibility, saved processing, semantic proposals and independent delivery/comparison audits. Review existing accepted original sources before selecting any repeat lane-one recording. Then rerun scoped strict. Actual CARLA sign governance and travel visibility remain physical review after CPU readiness.

## 2026-11-24 position and velocity consistency checkpoint

The saved 900-frame direction measurement now requires an original ego position source on each row, validates SHA-shaped source references, and checks adjacent original positions against velocity and elapsed time. A reversed velocity with unchanged positions, tampered positions, missing position source and malformed context digest are rejected. This is a CPU acquisition/measurement contract; no physical capture is claimed.

### Receipts

- `cpu-position-tests.log` exit 0, SHA256 `5ee9dd033dcc430dea8fa347ccbf0858850e9c3f326e41952ae6c7d4a97fda01`
- `cpu-position-preflight.log` exit 0, SHA256 `8f5031299024e59b7a9fd340dc4980120ae90736e7309c8b104ae9b7b2a18ad0`
- `cpu-position-static.log` exit 0, SHA256 `44477c53eaa70167331894dacb9d2162ec93757b9c05d35170548a95bffe475a`
- `cpu-position-strict.log` exit 1, SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`

- `one_way_direction.py` SHA256 `09ffd3c50b3effcc9bf842527c6cb33346a5f0fcaa6fda9907513b14d518ca5f`
- `tests/test_one_way_direction.py` SHA256 `41bc5c603da8d8d233e406fb3a5882b52f9dc3941755df166991c9d022e99266`

Five focused tests, pinned preflight and scoped complete static check pass. Exact scoped strict exits 1 because status remains partial. Next CPU work: canonical selected-case bundles and independent comparison/delivery audits for all four exact cases.
