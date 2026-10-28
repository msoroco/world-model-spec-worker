# Fresh demo-test preparation: v4

The operator starts this agent manually. Use Python 3.11 or newer; create an
ignored `.venv-cpu` and install `runtime/main-pipeline-v1/requirements-cpu.txt`.
Software compatibility also needs FFmpeg and the Lean `lake` toolchain pinned
by the exported library. Record a precise dependency blocker if either cannot
be installed. Read `batch.json`, its four partitions,
`skills/worker-preparation/SKILL.md`, the exact assignment inputs and
`references/catalog.json`. Use up to four assignment owners, one per partition.
Run `python3.11 reference_select.py ASSIGNMENT_ID` to find matching
accepted source examples; read their hashes and limitations before adaptation.
The lead alone integrates shared changes, validates, commits and pushes the
configured return branch. Do not inspect earlier trial branches or copy their
packages. Do not run CARLA, NERSC tools or the main campaign database.

For every assignment, read the law, selected witness, cell, actor and prior
evidence. Complete the selected branch first. In `case-plan.json`, set
`selected_branch` to the exact `assignment.json.branch` and list
`requirement_dispositions`. Each row needs `requirement`, `source`, `status`
(`selected_required`, `alternative_pending` or `exception_pending`) and
`evidence_or_gap`. An officer/signal exception does not force a positive
demonstration in a base case; establish absence of actual governing control.

Build exact cases, connected road geometry, controllers, cameras, complete
capture channels, a measured-results finalizer and CPU tests. Use the
source-hashed accepted training implementations as adaptation examples, never
as test evidence. Check topology, routes, signs/markings, participants, camera
configuration and duration offline. Record unverified native motion and pixel
visibility as GPU checks.

`source_observation_terms` are law-evidence prompts, not Core IDs. Map every
term to actual acquisition in `case-plan.json.source_observation_mapping`.
`config.required_atoms` contains only pinned ontology IDs. Conditional atoms
must declare `config.source_packets`: `scenario_geometry` for one-way roadways
or medians; `scenario_geometry` plus `scenario_rule_evidence` for an
original-frame verified regulatory sign; `environment_calibration` plus
`surface_provenance` for measured visibility or authored ice/snow. Diagnostic
fixtures must contain these packets and converter coverage must pass. The
source declaration alone is not evidence of realized physical behavior.

If a portable adapter/capture/validation defect blocks the selected branch,
place source-hashed replacement Python files and `overlay.json` under
`work/_shared/runtime-overlay/`. See `overlay.py`; materialize with
`python3.11 overlay.py` and test the effective runtime. Keep the
pinned baseline and Core ontology unchanged. The local operator verifies any
overlay before adopting it into a new local runtime revision.

For every exact nonbaseline case, run `runtime.py offline` and store a hashed
log in its execution-manifest `offline` entry: `command`, `exit_code: 0`,
`log`, `log_sha256`, `construction_sha256`. Run actual package compatibility
with case-specific diagnostic data, including declared packets. A partial
package still needs executable, offline and compatibility proofs; use
`blocked` only for a precise, test-backed CPU barrier. Diagnostic fixtures
prove software compatibility, not physical behavior or legal compliance.

Run the full runtime selftest, including negative fixtures, assignment tests,
every exact-case offline check and every compatibility check. Copy its
`verification.json` and log into `work/_shared/`. Write
`work/_shared/runtime-proof.json` with `format: worker-runtime-proof-v1`,
`runtime_manifest_sha256` (effective runtime), `command`, `exit_code: 0`,
`log`, `log_sha256`, `verification_receipt` and `verification_sha256`.
Finish with:

```sh
python3.11 worker_check.py --complete --require-capability-ready
```

If that gate fails, report exact test-backed CPU blockers. Commit and push the
return branch. Report commit, counts, hashed logs and the first GPU capability
command per assignment. No physical acceptance is claimed.
