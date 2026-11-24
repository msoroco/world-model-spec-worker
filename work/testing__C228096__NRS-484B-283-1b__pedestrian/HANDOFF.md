# C228096 curb entry checkpoint

Status: partial. Exact scoped strict gate exits 1 because this result remains partial.

## Constructed CPU scope

`curb_entry.py` source-gates pedestrian identity, curb/safety boundary, qualifying vehicle and driver control, road and distinct vehicle-path geometry. It constructs timed pedestrian and vehicle routes and measures synchronized original pedestrian/vehicle positions over 900 frames. The finalizer distinguishes roadway entry from entry into the vehicle path and records proximity and speeds without inventing a suddenness or impossibility threshold.

Five exact cases and four comparisons in `case-plan.json` probe walk/run, close/far vehicle positioning, road-only entry and remaining at the curb. The introductory statutory exceptions are retained as unresolved context. Frozen evidence inventory has no accepted recording.

## CPU proof receipts

- `case-plan.json` SHA256 `dc1b5df4454c535637dde0f5e14142901372d9e85a6afaddc54806c32da4fb7c`
- `curb_entry.py` SHA256 `5d3e8c534179d46e0e6407b8e1d0d1d36afd3778ed4e1d3f599436dc324b20e4`
- `tests/test_curb_entry.py` SHA256 `81d67defcfeea4527d060976da7b2445c4c5f69696f7588b879739b179ce7943`
- `cpu-tests.log` SHA256 `6f573220022a4c482d9648c78d7621e00e74242b4f5a9ae1f6d5cfaddd48ef7f`
- `cpu-preflight.log` SHA256 `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`
- `cpu-static-check.log` SHA256 `ff41d541ce02466f778dc2bfbbc829d90e30799405cc544c54e94f374c1a9062`
- `cpu-strict-check.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`

Focused unittest exit 0 (3 tests); pinned `runtime.py preflight` exit 0; scoped static `worker_check.py --assignment testing__C228096__NRS-484B-283-1b__pedestrian` exit 0; exact scoped strict with `--complete --require-delivery-ready` exit 1 on truthful partial. `result.json.tests` includes only successful commands with package-relative logs and SHA256.

## Remaining CPU work

Create canonical selected-case bundles and source-bound positive/negative compatibility, saved processing, semantic proposals and independent delivery/comparison audits. Add sourced driver response/braking and any operative introductory exception facts. Then rerun scoped strict. Actual CARLA synchronization and camera coverage remain physical review after CPU readiness.
