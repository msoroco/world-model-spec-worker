# Partition 2 executable preparation return

Status: **partial**. Implemented executable controller, OpenDRIVE/path draft builder, event geometry, lazy capture runner and CPU tests. The runner fails closed before connecting because target-critical mechanisms remain incomplete:

- Business-district frontage/building-use and freight loading-zone construction is not implemented.
- Turn surface, physical lamp flashing RGB verification, and signal-onset/course-change finalizer are not implemented.

Exact source law, actor, cell, witnesses, summaries, existing evidence and text conflicts are retained in source-review.json. Proposals include fresh template, relevance, binding, judgment-observable and cases drafts. Templates are not held for human approval. Baseline is not selected. All nonbaseline case-specific canonical proposals are in constructions/<case-id>.json; adopt each with its own inline config.json and identical runner.py/geometry.py. Root construction.json is baseline anchor and matches materialized files.

Offline: `/usr/bin/python3.11 work/testing__C378304__NRS-484B-413-2__motor_vehicle_driver/runner.py --check`; `/usr/bin/python3.11 -m unittest discover -s work/testing__C378304__NRS-484B-413-2__motor_vehicle_driver/tests`. Hashed logs are in result.json. No mocked physics or observations are offered as acceptance.

Later CLI: `runner.py --output-dir PATH --host HOST --port PORT --case-id ID`. Existing empty output dirs allowed. This currently writes explicit failed preflight result with missing capabilities and exits 2. Complete the named mechanisms and live binding before clearing implementation_gaps. No simulation is authorized here.

For measured-results finalization, retain the original entire run, check actual setup/geometry/participants and all channel coverage, recompute declared summaries with original sample windows and entry-event brackets, inspect RGB for visible lamps/signs and maneuver completion, then freeze physics-supported sweep ranges/durations. Preserve failed settings and observations; any same-setting repair must change the diagnosed cause. Do not infer public authority from a physical opening, legal district status from props, or legal compliance from controller requests.

Additional implemented module: signaling.py recomputes observed continuous-signal distance and preserves original RGB ROI luminance histories separately from lamp API bits. Optical variation is not itself visible-flashing acceptance.

Integration update: runner now executes the authored physical maneuver and original measurement helpers. Earlier references to unintegrated helpers are superseded. Remaining exact gaps are result.reason/config.implementation_gaps. Still partial; no simulator run occurred.
