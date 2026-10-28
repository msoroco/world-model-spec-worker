# Partition 2 executable preparation return

Status: **partial**. Implemented executable controller, OpenDRIVE/path draft builder, event geometry, lazy capture runner and CPU tests. The runner fails closed before connecting because target-critical mechanisms remain incomplete:

- Paved-road cell still requires its fixed control and authored context to be realized; the generic road draft is not a reviewed cell construction.
- Stopping-distance and sight-distance raw measurement channels are not fully integrated; no judgment classifier is supplied.

Exact source law, actor, cell, witnesses, summaries, existing evidence and text conflicts are retained in source-review.json. Proposals include fresh template, relevance, binding, judgment-observable and cases drafts. Templates are not held for human approval. Baseline is not selected. All nonbaseline case-specific canonical proposals are in constructions/<case-id>.json; adopt each with its own inline config.json and identical runner.py/geometry.py. Root construction.json is baseline anchor and matches materialized files.

Offline: `/usr/bin/python3.11 work/testing__C179789__NRS-484B-600-1a__motor_vehicle_driver/runner.py --check`; `/usr/bin/python3.11 -m unittest discover -s work/testing__C179789__NRS-484B-600-1a__motor_vehicle_driver/tests`. Hashed logs are in result.json. No mocked physics or observations are offered as acceptance.

Later CLI: `runner.py --output-dir PATH --host HOST --port PORT --case-id ID`. Existing empty output dirs allowed. This currently writes explicit failed preflight result with missing capabilities and exits 2. Complete the named mechanisms and live binding before clearing implementation_gaps. No simulation is authorized here.

For measured-results finalization, retain the original entire run, check actual setup/geometry/participants and all channel coverage, recompute declared summaries with original sample windows and entry-event brackets, inspect RGB for visible lamps/signs and maneuver completion, then freeze physics-supported sweep ranges/durations. Preserve failed settings and observations; any same-setting repair must change the diagnosed cause. Do not infer public authority from a physical opening, legal district status from props, or legal compliance from controller requests.

Physical sweep execution is implemented with `--output-dir PATH --host HOST --port PORT --sweep-index 0..4`; the deterministic runtime materializer leaves the canonical judgment proposal unexpanded. Frozen physical grid details are in config.physical_sweep_execution. These are capability drafts with explicit missing mandatory observations, not accepted cases or judgment classifications. Both grids preserve baseline nonselection.
