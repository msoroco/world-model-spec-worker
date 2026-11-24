# training__C230259__LVMC-11-30-060-A__pedestrian

Status: **partial**. No selected delivery case, Native execution, source-camera footage, saved processing, or accepted recording is claimed.

The frozen cell is `road` / `travel` / `other_vehicle` with a pedestrian subject. The exact text imposes an outside-crosswalk yield duty to all roadway vehicles, subject to the Section 11.30.070 designated-place exclusion. The witness calls for complete crossing, both crosswalk categories, every roadway vehicle, and physical precedence evidence. No accepted recording ID is supplied for this assignment.

## Worker-owned CPU checkpoint

- `native/crossing_meter.py` validates 600 continuous original 20 Hz rows, a hash-bound context survey, the complete vehicle inventory, pedestrian body entry and exit, marked-crosswalk and intersection overlap at entry, and vehicle conflict-point precedence. `native/prove_meter.py` passed three positive and four negative fixture checks. `native/source-meter-proof.json` SHA-256: `bc3da9c30d787711283598cff90ff2c940ff405057349eb7b5f151c84a184632`. The rows are synthetic scene requests; they are not observed Native motion or legal findings.
- `measurement-contract.json` names original post-tick rows, source-camera streams, frame map, and unresolved legal reviews. `case-plan.json` maps each source observation term to a named measurement or context.
- Two exact unselected 30-second / 20 Hz / four-camera draft construction bundles are in `draft-probe-01/` and `draft-probe-02/`. Both passed `.venv-cpu/bin/python runtime.py offline` with two unit tests each. `draft-manifest.json` SHA-256: `f28c9830b21a78c442dd46abde4703d85195258c45e5b7ae0431c1bce8343cac`; `draft-offline-receipt.json` SHA-256: `4fc5a53843d67f78a3fc1d7fa8f1c1566866c577999f0ed44c35886efe82806a`. The draft runner implements source packet extraction and checked requests, but does not yet orchestrate Native CARLA capture.
- `.venv-cpu/bin/python runtime.py preflight` passed. `.venv-cpu/bin/python worker_check.py --assignment training__C230259__LVMC-11-30-060-A__pedestrian --complete` passed.

## Remaining CPU work

Implement the complete Native world/actor/camera capture and saved source processing, review actual crossing geometry and the Section 11.30.070 exclusion, select source-grounded cases, construct three tested fallbacks per selected case, and pass exact positive/negative compatibility, saved processing, acceptance, and comparison audits. Keep actual vehicle yielding and legal applicability separate from request timing. Run the assignment-scoped strict gate before any ready status.
