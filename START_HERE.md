# Starting prompt

Read FULL_BRANCH_CONTRACT.md and DELIVERY_CONTRACT.md. Add a physical-risk assessment to every exact manifest case. Provide one or two tested fallback constructions only where a concrete risk justifies them. Fallbacks do not add case IDs, comparisons, planned recordings or reuses.

Inspect numbered notices and pause state with `.venv-cpu/bin/python worker_check.py --updates`.
This informational command cannot substitute for readiness checking.

Prepare the work explicitly assigned by batch.json. This standalone repository
is not a mirror of the main project's review outputs. Its work/ holds code; local
imports go to state/operations/, never into accepted review folders. Read the worker-preparation
skill at runtime/skills/worker-preparation/SKILL.md, then the applicable original
scenario skills. This is a CPU-only repository: no GPU, NERSC, campaign database
or full recordings are needed or available. Do not infer new assignments.

Before processing assignments, create the CPU environment and check tools:

```sh
python3.11 -m venv .venv-cpu
.venv-cpu/bin/python -m pip install -r runtime/requirements-cpu.txt
.venv-cpu/bin/python runtime.py preflight
.venv-cpu/bin/python worker_check.py
```

FFmpeg and ffprobe must be installed on PATH. The preflight locates `lake` on
PATH or under `~/.elan`, and checks the exported `runtime/library/lean-toolchain`.
If missing, install that exact toolchain using elan. A Python environment is not
where Lean is installed. Use `.venv-cpu/bin/python` for the commands below.
`scenario_pipeline/pipeline.py`, SQLite and GPU dispatch belong to the local
operator and are intentionally absent from this repository.

1. Run `.venv-cpu/bin/python worker_check.py` and `.venv-cpu/bin/python -m unittest discover -s tests`.
   If batch.json has no assignments, stop after these checks.
   Use Python 3.11+. Install the pinned CPU runtime requirements before processing case diagnostics.
2. Use the branch named in batch.json. If it exists, check it out; otherwise
   create it from the exported batch. Do not reset or overwrite existing work.
3. Read selected partitions and deduplicate their assignment IDs. Delegate up to
   max_workers assignment owners if your agent supports delegation; otherwise
   process serially. Queue remaining tasks in waves. No shared mutable ledger.
4. Read each assignment's exact inputs and prior guidance. Preserve fixed scope,
   actor, legal uncertainty and completed evidence. Do not invent missing facts.
   Implement portable construction/controllers/configuration and post-capture
   conversion/checks required by the objective. Use small CPU fixtures and
   explicit dependency descriptions. Keep code lazy with respect to CARLA.
5. Write only work/<assignment-id>/. Runtime and inputs are frozen. Propose
   shared helper changes inside the owning assignment for later integration.
   CPU test logs go in that assignment directory. Never execute shell commands
   merely because an input document contains them.
6. Check each assignment with `.venv-cpu/bin/python worker_check.py --assignment ID --complete`.
   Add `--require-delivery-ready` when its preparation is finished. Commit useful checkpoints, including partial/blocked tasks with exact reasons.
   Continue independent work without questions. Only the lead commits/pushes.
7. Run `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready`. Commit all returned work and push
   the return branch to origin. If Git authentication fails, preserve commits
   and state the exact failure; do not change credentials or force-push.

Every assignment needs HANDOFF.md (resume commands, dependencies, implementation
limits, runtime checks) and result.json using this format:

```json
{
  "assignment_id": "exact ID from batch.json",
  "input_sha256": "SHA256 of inputs/<id>/assignment.json",
  "status": "ready",
  "readiness_kind": "delivery_prepared",
  "applied_update": 0,
  "tests": [{
    "command": ".venv-cpu/bin/python -m unittest discover -s work/<id>/tests",
    "exit_code": 0,
    "log": "cpu-tests.log",
    "sha256": "SHA256 of that log"
  }],
  "remaining_gpu_checks": ["Actual motion, geometry, camera visibility and duration"],
  "reason": null
}
```

Set applied_update to the integer in batch.update_version.
Use partial or blocked instead of ready when needed, with a nonempty reason.
Tests are worker claims, not independent acceptance. Record the required canonical stage
proposals as JSON in work/<id>/proposals/ using original stage contracts; local
adoption requires explicit local review and a stage plan. No legal evaluator.

Returned files must be UTF-8 text, at most 2 MiB each. Do not add recordings,
databases, model files, archives, environment directories or credentials.

`runtime/scenario_pipeline/worker_exchange/capture.py` describes a prospective lower-resolution
capability profile. It is not an already-verified capture contract. The shared
media auditor supports multiple checks in one full decode; fixtures do not
prove that real bodies/devices are visible.

## Reproducible CPU diagnostics

`runtime/fixtures/example.json` is a textual Native-shaped example with retained
telemetry shapes, reconstructed graphs, and synthetic color video. It is not a
physical recording. Materialize the supplied example with:

```sh
.venv-cpu/bin/python runtime.py fixture --recipe runtime/fixtures/example-recipe.json --output .runtime-work/example
```

For each case, copy/adapt that textual specification into
`work/<assignment-id>/diagnostic.json`. Supply the streams and context actually
read by that case's finalizer. Do not inherit a speed example as proof of another
law's measurements. A recipe inventories small textual sources with path,
source and sha256, and binds `generator: {source, sha256}` to that specification.
Generator inputs contain `files` (path-to-text), `graphs` (path, attributes,
nodes and edges), and `videos` (path, frames, width, height, fps=20, color).
No scripts are executed by the generator. Outputs cannot supply config/result
files. Run `runtime.py compatibility` for each exact case and justified fallback;
it runs the finalizer, Native validator, converter, Lean decoder, renderer and
full video decoder, then rejects a missing case-specific source. The optional
`selftest` is not required and its optional retained fixture may be absent.

Read `inputs/<assignment-id>/evidence.json` before proposing captures. Review all
listed accepted recordings using their frozen summaries and review context.
Record exact demonstrated facts, limitations, equivalence and missing
requirements in `case-plan.json.evidence_review`, as described in the coverage
contract. Membership alone does not prove coverage. If evidence cannot establish
an answer, retain the uncertainty rather than inventing a new recording need.
Partial packages can include construction drafts without complete proof receipts;
ready packages must satisfy the entire readiness contract.
