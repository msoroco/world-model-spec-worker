# C110875 taxi driver delivery handoff

Status: **ready for local delivery preparation** after the exact assignment strict CPU gate passed on 2026-11-25. This is not a physical capture or legal verdict. Input SHA-256: `966c41984789f72b6a2f89785fcb6abdfbc7c9e5a1a57a38db7dd920eef1f863`.

The exact rule applies to a cab leaving a stand designated under LVMC 11.60.090 when a sign is posted giving notice of a required right turn. The required turn is at the **first street intersection** after the stand. Two selected delivery cases share the stand, notice, road, timing, camera profile and taxi context; probe 01 requests right at that first junction and probe 02 requests straight. Neither diagnostic observation is treated as original Native proof.

## CPU proof

- Both primary constructions and both target-preserving fallback constructions passed pinned-runtime `offline` and current-runtime public `compatibility` positive plus missing-route-survey negative checks. The compatibility receipts were independently rechecked by `package_compatibility.check_receipts`.
- Both primary cases passed exact recorded-only `process-saved` on source-hashed diagnostic attempts: 600 frame joins, four original-camera decodes, and no missing evidence in the positive sources.
- Semantic delivery validation passed the exact source-observation mapping and selected pair. Physical preparation passed complete-motion, incomplete-motion and missing-evidence diagnostic paths, including lifecycle release.
- `delivery_audit.py` passed positive diagnostic and missing-route-survey rejection for each case. `comparison_audit.py` passed paired source joins and the observed right/straight distinction, and rejected an omitted case. Root unit tests passed.
- `.venv-cpu/bin/python worker_check.py --assignment training__C110875__LVMC-11-60-090__taxi_driver --complete --require-delivery-ready` passed on 2026-11-25. The exact gate output is retained in `proofs/assignment-strict.log`.

## Local delivery and original-source review

The Native runner builds the road, designated-stand marker, posted right-turn notice, first and later junctions, taxi controller, and synchronized four-camera capture. Its readback retains `road.xodr`, route survey, actor poses, frame map, trace, and original videos. The independent delivery audit requires a separate reviewed `route-survey.json` and original pixel review before it can accept actual Native delivery. That review must establish the taxi's licensing/identity, stand designation, sign placement and posted notice authority, that the surveyed junction is the first **street** intersection after departure (with the later junction kept distinct), and the actual measured turn. A synthetic geometry marker or requested direction alone cannot establish those facts.

Run the first exact job with `runtime.py execute-delivery --python $CARLA_PYTHON --host $CARLA_HOST --port $CARLA_PORT --case training__C110875__LVMC-11-60-090__taxi_driver__probe_01 --job $JOB_ID --db $DB --run $RUN --assignment training__C110875__LVMC-11-60-090__taxi_driver`. Run probe 02 as the paired comparison under the same fixed conditions. The canonical manifest retains fallback triggers, saved-processing commands, delivery audits, and source-to-channel acquisition mappings.
