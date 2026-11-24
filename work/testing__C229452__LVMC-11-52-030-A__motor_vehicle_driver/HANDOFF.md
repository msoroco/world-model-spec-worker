# C229452 red curb checkpoint

Status: partial. Exact scoped strict gate exits 1 because this result remains partial.

## Constructed CPU scope

`red_curb.py` constructs a source-gated red curb, matching sign and vehicle subtype, parking route and actual halt activity. A long original event trace measures 1799/1800/1801-second signed tour-bus probes and separately covers shuttle, limo, RTC bus, armored/emergency business, ordinary stop/park and adjacent U.S. mail deposit. Attendance, engine operation, conflict and authority directions are retained without treating them as automatic exceptions. No accepted recording exists in the frozen evidence inventory.

The eleven exact cases and eight controlled comparisons are in `case-plan.json`. Legal applicability and expeditiousness/necessity remain unresolved. A 900-frame 45-second video cannot prove a 30-minute boundary; a linked long event trace is required.

## CPU proof receipts

- `case-plan.json` SHA256 `235c39bed13263f42f7c5127ae48c054d93307ecabae294e8e5c99cb773c7811`
- `red_curb.py` SHA256 `caa2ee481be43fc447871e36a3e8929b44613394995d2d5d7005c98b430a34ee`
- `tests/test_red_curb.py` SHA256 `5690e2f6d10b3970793996fdabb80050b58252b22864decdea9cadba5db22fbf`
- `cpu-tests.log` SHA256 `6e6b97d7b27420efb09529fd68dc6e5af37befcf6c813e2dd19db42cc6c19bb2`
- `cpu-preflight.log` SHA256 `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`
- `cpu-static-check.log` SHA256 `e6c4b636ea169282984d9a421a87b9cfc75ced7f2b59036f16021bd821a5c80b`
- `cpu-strict-check.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`

Focused unittest: exit 0 (4 tests). Pinned `runtime.py preflight`: exit 0. Scoped static `worker_check.py --assignment testing__C229452__LVMC-11-52-030-A__motor_vehicle_driver`: exit 0. Exact scoped strict with `--complete --require-delivery-ready`: exit 1 on truthful partial. `result.json.tests` includes only passing commands with package-relative logs and SHA256.

## Remaining CPU work

Create canonical selected-case execution bundles and source-bound positive/negative compatibility proofs for each case; add saved-only processing, semantic proposals, independent delivery/comparison audits. Add remaining statutory alternatives such as standing and RTC bus below/above boundary where selected. Then rerun exact scoped strict. CARLA physical motion and camera verification follow CPU readiness.
