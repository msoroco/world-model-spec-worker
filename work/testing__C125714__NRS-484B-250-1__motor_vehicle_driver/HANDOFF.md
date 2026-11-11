# C125714 CPU handoff — NRS 484B.250(1)

Status: **partial**. The selected median-opening branch requires another vehicle from a different highway to enter the same statutory crossing before ego; the duty lasts while that vehicle occupies it. Official traffic-control devices exclude subsection 1 unless subsection 4 applies separately. Opposite-direction approaches with either driver intending or making a left turn are also excluded.

`case-plan.json.evidence_review` reads all seven accepted metadata sources: each identifies the assigned law/cell/actor, 1100 frames and a passing decoder. Raw trace/video and delivery-audit content are absent, so labels do not prove crossing identity, entry order, device exclusion or comparison isolation. No accepted original is replayed or claimed sufficient. Conditional source-verified cases retain these unresolved comparisons.

`crossing_precedence.py` joins original frame maps to full ego/other bodies and sourced crossing geometry. It measures first body entries, different-highway identity and other occupancy at ego entry while rejecting unknown device and opposite-left-turn exclusion status. `native_crossing.py` inventories controlling entrance devices and calls `world.try_spawn_actor` for a real other participant with cleanup. Three CPU tests pass, including negative timing, device, frame and Native construction branches. These tests do not prove actual legal applicability or yielding.

Next CPU work: source-review original accepted evidence for exact equivalence, if available. Source one median-opening crossing and complete device inventory; construct ego and other vehicle timing for each uncovered primary/comparison case. Implement runner, four raw cameras, original-frame capture, saved finalizer, distinct fallbacks, semantic proposals and independent delivery/comparison audits. Run exact offline, compatibility, saved-processing and assignment strict gates. These are worker-owned CPU actions; actual motion and visibility remain later physical checks.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C125714__NRS-484B-250-1__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C125714__NRS-484B-250-1__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight passes. No frozen input, runtime or batch file was edited; no Git command was run. Assignment and full-gate outputs are retained in `assignment-check.log` and `strict-gate.log`.

Checkpoint: assignment-scoped static check passed. Complete strict gate next reports missing result `testing__C125751__NRS-484B-250-1__motor_vehicle_driver`; this is unfinished worker preparation, not an external dependency.
