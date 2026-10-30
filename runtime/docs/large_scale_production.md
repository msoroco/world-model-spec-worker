# Production of original CARLA / TrafficSpec evidence

The new campaign starts from the existing catalog, considers the full law corpus,
uses motor-vehicle drivers initially, and targets 100 pilot pairs then 1,000 pairs.
A milestone requires its selected comparison/sweep groups to finish; a numeric
pair count never hides incomplete groups. Baselines remain definitions.

## Prepare and execute

Use Python 3.11+ with the processing requirements, the existing CARLA 0.9.15
Python 3.8 environment, FFmpeg, and the full TrafficSpec decoder. All persistent
artifacts stay under `runs/scenario_pipeline`; no historical runs are modified.

```bash
cd scenario_pipeline
python3.11 production.py --db ../runs/scenario_pipeline/state/production-motor-v1.sqlite init
python3.11 production.py --db ../runs/scenario_pipeline/state/production-motor-v1.sqlite run \
  --engines ../runs/scenario_pipeline/work/production-motor-v1/inputs/engines.json \
  --validator /absolute/path/to/full-core-decoder --cycles 1 --milestone 100
python3.11 production.py --db ../runs/scenario_pipeline/state/production-motor-v1.sqlite status
```

Initialization freezes the law source (including ongoing independent changes),
its atom contracts, summaries, exact catalog and indexed fewshots. It checks
source hashes across the freeze and rejects a concurrent edit. It does not make
model calls or launch CARLA. Existing campaigns resume; they are not reinitialized.

Each cycle advances one resumable batch of at most 25 cells. The coordinator
continues relevance, bindings and case planning for the current and next
selected 25-cell slices while a second coordinator-owned worker watches for
completed case plans. It freezes each complete comparison group as soon as its
cell plan is ready, then queues construction without waiting for the remaining
cells. Both sides share one global model-request limiter. Remote CARLA workers
receive immutable attempt inputs and never access SQLite. Construction uses a
rolling queue of up to 10 cases by default (`--construction-batch-size` may be
set up to 25); a slow or blocked case does not hold a batch barrier in front of
other cases. Construction calls run concurrently up to the configured worker
limit, and each result is validated before its case is dispatched to CARLA.
Each selected case is added to the queue as soon as its complete comparison
plan is frozen. Failed or blocked constructions and failed executions retain their selected membership and all evidence, but do not reserve a production slot that stops unrelated groups from being selected. Pending and active repairs remain subject to their existing budgets. Concurrent semantic repairs serialize budget reservations and merge completion into the latest budget; worker calls remain concurrent. Explicit construction blockers in mechanisms or static-check status/result/outcome fields are classified as non-executable before runnable-field validation. Accepted-pair counts and full group completion remain separate; reaching 100 accepted pairs may advance scheduling toward 1,000 while the pilot is still reported incomplete. Construction
prompts retain the exact selected case, complete linked group, full bindings,
target-law template and recording requirements, while omitting unrelated
cell-wide case plans and templates. Their complete source artifacts remain in
SQLite and are identified in prompt provenance. A coordinator
restart resumes the current batch from SQLite and the saved
`production_batches.json` checkpoint. The scheduler uses the campaign's
`semantic_concurrency` setting (currently 7) and a 10-job/minute start limit. Model requests are
explicit campaign work; no relevance law pruning occurs.
Whole groups requiring unsupported primitive observations are reported in `selection_support.json` and remain unselected while supported families proceed. Relevance remains exhaustive. Only authorized dedicated engines are used, at most seven. Availability is
rechecked; snapshots are not allocations. No Slurm resource requests are made.

Dependency-ready planning runs alongside diagnosed failed-plan repairs, using separate SQLite connections owned by the single coordinator and the shared worker limiter. Fresh planning excludes repair-owned case jobs so their bounded retry windows stay intact. The coordinator joins both tasks before ending a cycle.

## Observations and verdicts

`traffic_spec_adapter/atom_contract.py` maps every canonical atom and retained
accessor contract through native observation, raw evidence, graph and Core JSON.
Known native attributes are merged by actor ID rather than duplicated by aliases.
Native device API states and governed lanes, actual acceleration, actual wheel
angle (when supported), participant motion outside the crop and requested
subject-to-user collision visibility are retained. Unobserved remains unknown.

The inventory is complete; observation support is not claimed complete where
capabilities remain absent. Required unsupported or missing observations fail
acceptance and require a diagnosed repair or explicit unsupported result.
Native surface roles overridden by verified custom median construction are
reconciled rather than emitted as duplicate sidewalk/median entities.

`run_selected.py --recorded-only --production` finalizes existing recorded
attempts using four expected verdicts: `compliant`, `violation`, `not applicable`,
`inconclusive`. The existing strict legacy mode is preserved.

Supported reference checks use actual delivered measurements and explicit
activation/assumptions. Current production cap checking covers an observed motor-vehicle subject and
the statutory “in any event” clause; original measured kinematic precision is retained rather than rounding away tiny exceedances. It compares every delivered
speed to 80 mph (35.7632 m/s), with equality compliant. It never uses the command
as the answer. Unsupported checks are `inconclusive/unsupported_reference_check`;
judgment sweeps are `inconclusive/unresolved_judgment`. Missing capture and
uncertain activation have distinct reasons. Missing mandatory evidence and an
unintended resolved outcome require repair. Inconclusive is excluded from labeled
counts. These are measured scenario expectations under their recorded assumptions.

## Storage and publication

Persistent scratch is the default. Only a diagnosed filesystem failure enables
an engine's optional `scratch_fallback`:

```json
{"id":"gpu-a","ssh":"AUTHORIZED_HOST","python":"/absolute/carla-python",
 "host":"127.0.0.1","port":23000,"allow_login_node":true,
 "scratch_fallback":{"root":"/tmp/scenario-pipeline-USER-CAMPAIGN",
                     "max_bytes":8589934592,
                     "diagnosis":"Documented scratch EIO with retained diagnostics"}}
```

Use a task-owned root, never the shared `/tmp` root. Storage is bounded and
checked during execution. Closed files transfer with hashes; result.json is
published last. Location-only metadata projections preserve originals. Clean
only registered inactive data with durable evidence; untransferred/active data
is retained. Host/process start identity prevents unsafe cleanup after PID reuse.
No staging is enabled merely because /tmp is faster. `/global/u1/m/msoroco` is
also only a bounded temporary fallback, not a permanent second output root.

The existing exporter produces one current video/trace/evidence triple per case.
Production manifests include grouping, catalog/law versions, reference-check
provenance, inconclusive reasons and separate pair/group counts. Batch additions
are explicit selection replacements; previous evidence remains in source runs.

Split tooling is deferred from the production critical path. The
metadata supports later grouped splits and law-family holdout selection. Training/test assignment can be added later using the accepted manifest.

## Large semantic inputs

The bridge preserves all laws and observation plans. Oversized requests retain the complete original JSON in the worker evidence directory and supply exact JSON-pointer references. A per-worker STDIO reader exposes only this supplied JSON in bounded read-only chunks. It has no shell, network, database, arbitrary-path access or writes. The worker sandbox stays read-only. It is not a scheduling service. Request and transport hashes are retained. See the official [MCP configuration documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).

## Structured recording views

Shared requirements sometimes request both timestamp-only and complete motion views of the same retained history. Keep one uniquely named structured recording and declare `unit_views` with exact requested unit strings and JSON pointers into the saved JSONL row. For example, a `s` view can select `/time_s`; a `s; m; m/s; rad` view also selects the recorded position, speed and heading fields with their individual units. Every selected physical field must exist and be finite in every sample. Context views select pointers into the saved context object.

This representation preserves each source requirement without duplicating recording names. It does not convert units or establish equivalence between different physical quantities. Scalar channels cannot claim structured views; missing fields, unknown values and incomplete component inventories fail evidence validation. Methods and physical provenance remain mandatory.

Descriptive-only view syntax is normalized to the existing `representation_units` field. Authored selectors remain verbatim in `descriptive_unit_views`; numeric views, source methods and all original requirements stay unchanged. A retained candidate from the same planning job can be reused only after this mechanical normalization passes every current-input planning check. Original responses and hashes remain available, and this recovery performs no new model call or driving episode.

## Closed recordings and repair evidence

Repeated diagnosed repairs match the same retained request while ignoring only `delivery_repair_failure.json` in the matching identity. That file is scheduler feedback, not new physical evidence. All original requests, diagnostic files, and physical evidence stay intact; pending or terminal matching repairs keep their existing attempt budgets, and a running repair is never duplicated. Genuine changed evidence remains distinct.

The completion sealer preserves a runner’s original result before projecting structured video references to their exact file paths. Direct context references may select only their exact named field in an existing in-attempt JSON object; all values, unknowns, targets and receipt metadata remain unchanged. Missing evidence and failed physical targets still prevent acceptance.

Read-only construction repairs receive the exact retained result and logs as supplied inputs, alongside the original evidence hashes. Hash-only paths cannot substitute for readable measurements. A worker that has waited for its runner, verified the same server identity and runtime, and published closed files can distinguish a subsequent sealing failure from uncertain transport or termination. Quarantine remains required when closure or server identity is uncertain.

## Focused test episodes

An explicitly authorized focused group uses new case IDs and retains the original
case definitions and every prior attempt. Target-specific bindings and recording
requirements apply only to the selected law family; exhaustive campaign relevance
and other law families remain separate work. The catalog cell must describe the
recorded maneuver: the focused speed group uses C230222 (road / travel / curb) and
records its C229398 scene provenance without claiming a completed parking maneuver.

For `focused-speed-v1`, physically accelerate under the controller and retain
preparation telemetry separately. A predefined start condition requires twenty
consecutive native samples within 0.1 mph of the command, with preparation bounded
to sixty simulated seconds. Capture then delivers exactly 160 consecutive frames
at 20 Hz (eight seconds), including any target failure. No delivered frames are
trimmed, substituted, or selected after seeing their outcome. The three commands
are 75, 79.5, and 85 mph; the 0.5 mph tracking allowance is an engineering target
check, while the existing reference check uses actual speed and the exact 80 mph
cap throughout the delivered episode. Synthetic public-highway assumptions remain
explicit. Raw acceleration history, complete episode graphs/cameras, native map
verification, conversion receipts, and failed evidence remain in the same run.

A quarantined existing server can be reused only after independently checking its
unchanged process identity, successful API response, released actual-server lock,
absence of leftover dynamic actors, and restored asynchronous world settings. The
readiness receipt and resource-lease transition are recorded by the sole coordinator;
the original timeout failure is retained. This check starts no server or allocation.
