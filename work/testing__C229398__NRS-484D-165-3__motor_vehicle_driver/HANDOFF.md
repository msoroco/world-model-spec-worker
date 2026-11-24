# testing__C229398__NRS-484D-165-3__motor_vehicle_driver

Status: ready for CPU delivery preparation. The exact scoped strict gate passes. Native capture, original-pixel review, physical completion and canonical acceptance remain local delivery steps; no accepted recording was available for reuse.

## Scope and case coverage

The exact NRS 484D.165(3) clause includes subsection (1) lamp properties and references the times in NRS 484D.100(1). `case-plan.json` selects six exact cases: `dark_lamps_on`, `dark_lamps_off`, `dark_attended`, `dark_traveled`, `sufficient_light`, and `outside_referenced_time`. Five controlled comparisons test lamp activation, attendance, placement, the 1,000-foot revelation precondition and referenced time. The 1,000-foot and 500-foot distances are statutory observation stations; no photometric or legal verdict is assigned by this package.

## Prepared constructions and saved processing

`execution-manifest.json` binds six exact inline primary constructions and a shared `fallback1` exposure-compensation alternative for each. The fallback preserves case conditions, source-station transforms, four canonical camera views, 20 Hz, duration and recording description. Independent original-pixel review finding an underexposed 500-foot lamp or 1,000-foot revelation station is its predeclared trigger. All twelve constructions pass exact offline checks and positive/negative compatibility checks. Each of the six primary cases passes saved-only diagnostic processing with original sources preserved. These fixtures prove software behavior, not physical visibility.

The Native runner validates a source-hashed independent site document and OpenDRIVE map, captures 900 synchronized original frames from four source-specified camera stations, verifies distinct stable sensor IDs and frame joins, losslessly encodes the four views, restores world state with readback, and writes the pinned Native result and capture seal. The saved finalizer rejoins the exact source packet, original history and camera seals; it produces source-hashed measurements for all five selected statutory requirements while retaining unresolved photometric assessments.

## Semantic, physical and independent audit proofs

The canonical source-bound semantic chain validates eight stages and six selected cases. Its three qualitative judgments remain unresolved. The sweep specification is explicitly incomplete because the frozen range inventory provides no applicable physical feasibility bounds. Each case has a source-bound measurement contract. Six independent delivery audit CPU positives validate saved source bindings, and six negatives reject diagnostic pixels as physical completion. Physical preparation fixtures exercise complete, incomplete and missing parked readbacks and the Native exit, owner release and saved-processing order.

`comparison_audit.py` independently checks all five exact pairs from saved analysis reports and original attempt sources. It verifies report and source hashes, exact case conditions, fixed map and site, and only the declared difference. Native mode also checks the independent site document and all 900 original 20-Hz parked frames. Five diagnostic CLI positives and five wrong-source negatives, with hashes, are in `comparisons/proofs.json`. Focused tests cover every pair in diagnostic and Native-shaped modes, including changed fixed site, undeclared difference, wrong source and changed original frame rejection. Diagnostic mode never claims physical or legal acceptance.

For each comparison in `case-plan.json`, the local queue can run:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/testing__C229398__NRS-484D-165-3__motor_vehicle_driver/comparison_audit.py --comparison <comparison_id> --left-report <left-saved-analysis-report.json> --right-report <right-saved-analysis-report.json> --left-attempt <left-original-attempt> --right-attempt <right-original-attempt> --output <audit-receipt.json>
```

Use the pair order recorded in `case-plan.json`. Omit `--diagnostic` for Native delivery. The separate delivery auditor must still review the original pixels and physical completion.

## Verification

The focused assignment suite passes 28 tests (`cpu-tests.log`). The exact scoped strict command passes (`cpu-strict-check.log`):

```sh
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python worker_check.py --assignment testing__C229398__NRS-484D-165-3__motor_vehicle_driver --complete --require-delivery-ready
```

`result.json` declares `ready` and `delivery_prepared`. Actual Native station sight lines, lamp color/readability, 1,000-foot revelation, independent physical review and local canonical acceptance remain unverified. All scratch outputs stayed under `.runtime-work/`. No Git, frozen input, runtime, batch or shared file was edited by this assignment owner.
