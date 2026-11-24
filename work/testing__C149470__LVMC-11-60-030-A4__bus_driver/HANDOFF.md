# C149470 bus curb checkpoint

Status: partial. Exact scoped strict gate exits 1 because this result remains partial.

## Constructed CPU scope

`bus_curb.py` source-gates a public-street non-tour bus and qualifying bus stop, stand, passenger zone, origin or destination location. It constructs a bus entry/halt, actual passenger/baggage activity and separately routed traffic. Its 900-frame original finalizer measures right-front-wheel point-to-curb distance, source uncertainty, bus-to-curb angle and other traffic speed during stopped loading. It does not substitute vehicle-body extent for front-wheel location.

Seven exact cases and five comparisons in `case-plan.json` include 0.4472/0.4572/0.4672-meter targets around the statutory 18-inch (0.4572 m) boundary. Approximately parallel and unduly impede remain unresolved judgments, not numeric cutoffs. Frozen evidence inventory has no accepted recording.

## CPU proof receipts

- `case-plan.json` SHA256 `6eebfbac117091fd6ee6c8075d794592e035d8591e0c208285592ecaa73b40a0`
- `bus_curb.py` SHA256 `4aacb3a0baa693dc90feb2a302fb4fe56574461f2b8681f9c49592f53b6146a8`
- `tests/test_bus_curb.py` SHA256 `2b0f391c33b4a9b01dd7d2865789aa26d6c9b36c45691589c520c571a0ab5941`
- `cpu-tests.log` SHA256 `814aaf46759d835c2927636255bdcffd5920e073e88e47ac92b1522c29be2ce2`
- `cpu-preflight.log` SHA256 `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`
- `cpu-static-check.log` SHA256 `7c9ebe5f7f854d49deef519d8657dbdab3def38f76e82160225ae323a4b86edc`
- `cpu-strict-check.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`

Focused unittest exit 0 (3 tests); pinned `runtime.py preflight` exit 0; scoped static `worker_check.py --assignment testing__C149470__LVMC-11-60-030-A4__bus_driver` exit 0; exact scoped strict with `--complete --require-delivery-ready` exit 1 on truthful partial. `result.json.tests` includes only successful commands with package-relative logs and SHA256.

## Remaining CPU work

Create canonical selected-case bundles and source-bound positive/negative compatibility, saved processing, semantic proposals and independent delivery/comparison audits. Ensure precise original right-front-wheel pose uncertainty supports the 1-cm boundary probes. Then rerun scoped strict. Actual CARLA wheel geometry, loading and traffic/camera visibility remain physical review after CPU readiness.
