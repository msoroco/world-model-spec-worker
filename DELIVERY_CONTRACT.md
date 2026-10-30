# Complete delivery preparation (update 007)

Prepare the selected cases for canonical delivery, not research-only capability.
CARLA motion and legal judgments remain unverified until local execution. The
worker never accesses NERSC or the local SQLite database.

## Required return

Keep the reviewed assignment identities, branches, comparisons, and explicit
recording reuses. Every selected `execution-manifest.json` case has
`"kind":"delivery"`; every ready `result.json` has
`"readiness_kind":"delivery_prepared"` and
`first_gpu_delivery_command`. Do not use capability labels in selected cases or
the GPU handoff. Failed diagnostic fixture runs are test evidence, not selected
recordings.

For every assignment, add `proposals/semantic-index.json`:

```json
{
  "format": "worker-semantic-delivery-v1",
  "assignment_id": "EXACT_ASSIGNMENT_ID",
  "stages": {
    "relevance_batch": {"path": "proposals/relevance_batch.json", "sha256": "SHA256"},
    "relevance": {"path": "proposals/relevance.json", "sha256": "SHA256"},
    "template": {"path": "proposals/template.json", "sha256": "SHA256"},
    "judgment_observables": [{"path": "proposals/judgment-0.json", "sha256": "SHA256"}],
    "bindings": {"path": "proposals/bindings.json", "sha256": "SHA256"},
    "cases": {"path": "proposals/cases.json", "sha256": "SHA256"}
  }
}
```

Use an empty judgment-observables list only when the template has no judgment
phrases. The shared `semantic_delivery.validate` runs the actual stage
validators against the exported law/cell input. It requires an exact-law
relevance decision, a complete template and active binding, a neutral baseline
definition, and full canonical case metadata. The baseline is not a selected
capture. Nonbaseline case IDs and recording descriptions must equal the
execution manifest. A prior `proposals/cases.json` that only passes the older
worker shape check is insufficient.

For each selected manifest entry, add `delivery_acceptance`. Its `script` is a
worker-authored, CPU-tested saved-evidence audit, with positive and negative
fixture logs. The local runner invokes it after CARLA and saved processing;
the script writes `worker-delivery-audit-v1` JSON for the exact case, job,
attempt and canonical recording. Required entry fields:

```json
{
  "case_id": "EXACT_CASE_ID",
  "sets": ["demo-test", "full-test"],
  "checks": ["native_source", "all_participants", "time_join",
             "full_video_decode", "actual_pixels", "physical_completion"],
  "script": "delivery_audit.py",
  "script_sha256": "SHA256",
  "command": "python3.11 delivery_audit.py --case EXACT_CASE_ID ...",
  "test_log": "receipts/delivery-positive.log",
  "test_log_sha256": "SHA256",
  "test_exit_code": 0,
  "negative_command": "python3.11 delivery_audit.py --case EXACT_CASE_ID ...",
  "negative_log": "receipts/delivery-negative.log",
  "negative_log_sha256": "SHA256",
  "negative_exit_code": 1,
  "negative_expected_error": "specific rejected defect"
}
```

The actual audit JSON must contain `format`, `passed`, `case_id`, `job_id`,
`attempt`, `recording_id`, `frames`, `source_result_sha256`, relative `video`
and `trace` paths, their SHA-256 values, and a `checks` object with all six
named checks true. It must fail when original evidence, timestamps, required
participants, complete decoding, relevant visible pixels, or physical outcome
fails. A positive CPU fixture proves code behavior only; it never claims that
future Native evidence will pass. Include at least one negative fixture that
actually exercises each independent audit implementation across the return.

The ordered `work/_shared/gpu-queue.json` must contain every selected case
once and every comparison audit once. Preserve exact IDs, participant histories,
duration, evidence channels, and same-cell comparison controls. The queue is
the local execution order, not a record of completed GPU work. A successful
case is referenced by the same canonical recording ID in both test sets;
explicit reference reuse requires a hash-bound receipt.

Update 008 requires each queue row to include `prepare_command`,
`execute_command`, `accept_command`, and `candidate_commands` keyed by every
declared fallback. Preparation selects one exact case and candidate, freezing
a separate local run and input revision. Execution dispatches only its returned
job ID to an operator-owned CARLA server. Acceptance uses the completed
canonical attempt and independent saved audit; a portable `.runtime-work/`
capture cannot be directly selected into sets. Commands use local variables
for database, host, port, Native Python, job ID and attempt number. The worker
must not assume NERSC paths or invent job IDs.

Write `work/_shared/local-integration-proof.json` with format
`worker-local-integration-proof-v1`, `passed: true`, a tested `command`,
`exit_code: 0`, `log`, `log_sha256`, and `scenarios` containing `primary_job`,
`fallback_job`, `saved_processing`, `rejected_audit`, and
`accepted_both_sets`. Its synthetic local fixture must show one accepted
recording ID in both test selections and no membership from a failed audit.
This is a software integration proof, not a physical acceptance claim.

The local operator imports the committed worker return once, then uses the
`local_checkout` path in the import receipt for preparation, execution and
acceptance. That checkout lives under the main scenario pipeline artifact root
and does not need `.git` or subsequent access to the remote worker repository.
The integration proof must exercise this path, including a repeat import from
the local checkout.

## Completion gate

Run `python3.11 worker_check.py --complete --require-delivery-ready` after the
full runtime selftest, exact offline checks, compatibility recipes, fallback
proofs and saved-audit fixture tests. Return only when all assignments are
delivery prepared. Report any physical uncertainties separately; they are GPU
checks, not missing CPU implementations.
