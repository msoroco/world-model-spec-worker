# NRS 484B.280(1)(c), C230266 motor vehicle driver

Status: **partial**. The frozen law is split into 11 source-distinct positions, 22 exact selected cases and 11 controlled comparisons. There is no accepted full-train recording. No legal near-distance or proper-caution threshold is asserted.

## Current CPU evidence

- All 22 selected current-runtime offline checks pass (`selected-offline/index.json`). Draft construction checks pass 22 positives, 22 missing-source negatives and 11 comparison-isolation checks (`native/branch-construction-proof.json`). Source meters and saved finalization retain actual driver observation as a separate source fact.
- All 22 physical/lifecycle CPU fixtures under `physical/` show complete travel, incomplete travel and missing evidence separately, plus capture seal, encoder closure, restoration, Native exit and owner release ordering. They are synthetic checker tests, not original motion.
- Current selected construction hashes have 16/22 public positive/missing-source compatibility receipts and 6/22 public recorded-only positive/negative processing proofs. The public proof loops are `native/run_selected_compatibility.py` and `native/run_selected_saved.py`.
- `statutory-source-audit.json` binds separate bus stop, bench, shelter, transit stop, bus boarding and other public transportation boarding positions. Original designation, use and actor class require independent sources; a label or prop alone cannot establish them.
- `proposals/semantic-index.json` passes the six-stage current-runtime semantic validator for all 22 selected cases. Driver observation and proper caution stay unresolved. The physical judgment sweep is explicitly incomplete pending original sources and a defensible sampling range.
- `delivery-audit/index.json` passes 22 positive and 22 missing-observation negative CPU predicate tests. `comparison-audit/index.json` passes 11 positive and 11 changed-source negative tests. Neither attests an original Native capture.

## Remaining CPU work

Finish the current-manifest public compatibility and recorded-only loops for all 22 cases. Bind the completed CPU receipts, physical risk decisions and independent audit contracts in `execution-manifest.json`, then run `.venv-cpu/bin/python worker_check.py --assignment training__C230266__NRS-484B-280-1c__motor_vehicle_driver --complete --require-delivery-ready`; keep partial until it passes. The lead integrates the shared exact GPU queue. Local Native execution and independent review of actual driver observation, original position/designation, motion and pixels remain separate from CPU readiness.

All scratch and generated diagnostics stay under `.runtime-work/`; every returned file stays below 2 MiB. No frozen input, runtime or batch file was edited.
