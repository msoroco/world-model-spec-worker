# Exact-case delivery handoff

Preparation proves software readiness. Local execution, independent audits, and
canonical acceptance remain separate. Never infer physical success from fixtures,
expected labels, or successful process exit.

Each selected case has kind `delivery`, executable measurement/finalization code,
its exact construction hash, a measurement contract, explicit diagnostic sources,
and offline and positive/negative compatibility receipts. Include the canonical
semantic proposals and `proposals/semantic-index.json`; preserve source quotes,
assignment identities, recording requirements, and comparison differences.

Every execution-manifest case includes `delivery_acceptance` with its `case_id`,
exact target `sets`, and checks `native_source`, `all_participants`, `time_join`,
`full_video_decode`, `actual_pixels`, and `physical_completion`. Bind the independent
audit script (`script`, `script_sha256`), exact-case positive `command`, passing
`test_exit_code`, `test_log`, `test_log_sha256`, and negative `negative_command`,
nonzero `negative_exit_code`, `negative_expected_error`, `negative_log`, and
`negative_log_sha256`. The negative log must contain the declared rejection.

Return `work/_shared/gpu-queue.json` with format `worker-ordered-gpu-queue`.
List every exact case once in consecutive `order`, with `assignment_id`, `case_id`,
`capture_command`, `postprocessing_command`, `owner_release_command`, and
`additional_source_audit_command`. Canonical local dispatch additionally requires
`prepare_command`, `execute_command`, and `accept_command`, using the corresponding
prepare-delivery, execute-delivery, and accept-delivery local commands. Include
`candidate_commands` keyed by each fallback ID, each preparing that exact candidate.
Do not launch these GPU commands in the worker.

Include one `comparison_audit_commands` entry per comparison with its assignment,
comparison ID, and independent audit command. Test what stayed fixed as well as
the declared measurement differences. Saved processing starts only after Native
exit and owner release and must produce actionable failure feedback.

For canonical dispatch, return one batch-level
`work/_shared/local-integration-proof.json` with format
`worker-local-integration-proof`, `passed: true`, a passing `exit_code`, command,
and hashed log. Cover `primary_job`, `fallback_job`, `saved_processing`,
`rejected_audit`, and acceptance into the exact target sets (`accepted_targets`,
or `accepted_both_sets` for the paired demo-test/full-test delivery).

Run `worker_check.py --complete --require-delivery-ready`. Ready means CPU-prepared;
physical realization, complete evidence, and local canonical acceptance remain
unconfirmed until the authorized original recording is independently reviewed.

## Source-bound acceptance audit

The saved independent audit uses format `worker-delivery-audit` and binds the
exact case, job, attempt, recording ID, sealed Native result hash, frame count,
video/trace references and hashes, and the required checks. Include
`auditor_path` and `auditor_sha256`, plus `source_decode_receipt_path`,
`source_decode_receipt_sha256`, and `source_decode_auditor_sha256`. The auditor
must be named `delivery_audit.py`; it and its decode receipt live under the
batch's local `state/operations/worker_exchange/` directory. Acceptance verifies
the receipt against the promoted video bytes, complete frame count, original
frame map, and current media auditor. It rejects missing or stale bindings
instead of falling back to a legacy audit path or decoding unchanged footage
again. Software fixtures cannot establish physical acceptance.

A CPU fixture tests the physical-completion and lifecycle checkers, not realized
CARLA motion. Partial/blocked packages may checkpoint missing proofs and must
state the exact gaps. Existing-evidence-only dispositions follow the coverage
contract and add no GPU job. Every ready executable case retains all proofs.
