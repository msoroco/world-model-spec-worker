# C80909 / NRS 484B.227(1) delivery preparation

Status: **ready for local GPU dispatch**, CPU scope only. The exact assignment gate passed:

```sh
export SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c80909-227-owner/output" PYTHONDONTWRITEBYTECODE=1
.venv-cpu/bin/python worker_check.py --assignment testing__C80909__NRS-484B-227-1__motor_vehicle_driver --complete --require-delivery-ready
```

The command returned 0; see `strict-assignment.log`. This does not establish actual CARLA motion, visible pixels, legal compliance, or public-authority establishment.

## Source and exact scope

The frozen law requires the right-hand roadway on a divided highway and prohibits divider crossing and left, semicircular, or U-turns except through an opening, or at a crossover or intersection established by a public authority. This assignment selects the median-opening U-turn with a multiple-movement variant, not the separate crossover or intersection branch. The physical opening is measured separately from any administrative establishment fact. The fixed C80909 cell is a divided road with an observed other vehicle; both cases use the same source/destination roadways, divider, vehicle, camera profile, other-vehicle pose, and opening geometry.

`case-plan.json.evidence_review` lists the one accepted `opening_aligned` recording `532c32e79b54dde98a7d7bf086a66014c02e70486ad1509f418d7176f9023102` with its frozen metadata hash. The export gives accepted membership and 1200-frame metadata, but no original video or body/heading/gear trace to establish complete U-turn or a reverse movement. The authored review context is treated as setting, not measured outcome. Both new cases address that exact source gap; the accepted recording remains unchanged.

## Exact cases and comparison

- `testing__C80909__NRS-484B-227-1__motor_vehicle_driver__opening_single`: one continuous forward U-turn through the authored opening.
- `testing__C80909__NRS-484B-227-1__motor_vehicle_driver__opening_multiple`: same opening and fixed context, with an observed-stop reverse segment and subsequent forward movement.
- `continuous_vs_multiple_movement`: compares original body, heading and velocity histories; only the realized reverse movement differs. The independent comparison audit rejects changed original bytes and changed fixed other-vehicle position.

The returned `gpu-queue-proposal.json` has two exact dispatch rows, one comparison audit command, and tested fallback preparation commands. The lead integrates it into the shared ordered queue after independent review.

## Implementation and CPU proofs

`candidate-median-opening.xodr`, `candidate-reviewed-median.json`, and `candidate-authority-review.json` bind the authored map, closed divider extents, opening, right-hand roadways and unresolved authority review by hashes. `divider_construction.py` checks a real gap between spawned barrier segments and their original footprints. `uturn_control.py` checks full-width route clearance and applies next-tick gear transitions only after observed stopping. `native_driver.py` spawns the conventional ego and fixed other vehicle; `native_capture.py` records original 20 Hz ego/other body histories, road ID readback, controller history, the four synchronized camera streams and frame map, then closes/restores before sealing. `analysis.py` performs saved-only source hash, actor/frame/time and road/context joins. `delivery_audit.py` independently rejects missing or changed original evidence and requires physical target completion. `comparison_audit.py` checks same map/authority and fixed configuration as well as the declared movement difference.

The two primary and two route-clearance fallback constructions passed current-runtime offline checks, full positive/negative compatibility, adapter/Lean/video decoding, and source-bound analysis. `prove_physical_cases.py` passed complete, incomplete and missing-evidence fixtures plus ordered Native-exit/owner-release/saved-processing lifecycle for each case. `prove_saved_exact.py` passed saved-only finalization and changed other-vehicle source rejection for each exact case. `prove_comparison_exact.py` passed the pair and both changed-original and changed-fixed-context rejection. `run_delivery_probes.py` passed independent positive/negative audit fixtures for both cases. Nineteen CPU unit tests passed; their log is `cpu-tests.log`. Synthetic fixtures establish software behavior only.

## Local execution and remaining review

Use the lead-published exact queue; keep its owner release before `runtime.py process-saved`. The local operator must review the live OpenDRIVE and divider collision/visible surfaces, actual source and destination road IDs, full-body passage through the opening, the reverse segment, other-vehicle presence, every frame and all four views, the independent video/pixel audit, and any public-authority record. The selected candidate must be reported independently of outcome. Retain failed attempts and use a pretested fallback only on its declared physical trigger.
