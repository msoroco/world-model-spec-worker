# C412593 delivery preparation

Status: ready after exact CPU construction, recorded-only feedback proofs and strict assignment gate. This status does not claim original physical or legal acceptance.

Ten exact residential, other-area and business-district right-turn cases and four comparisons have current semantic proposals, primary and fallback constructions, source-gated Native capture, saved measurement/finalization, and a canonical GPU queue proposal. Original trace/video is absent from the four prior accepted metadata records; they are not treated as measured coverage.

CPU evidence: all 20 primary/fallback offline checks; all ten synthetic physical-preparation and lifecycle checks; all 20 primary/fallback positive and negative compatibility checks; ten recorded-only saved processing checks; ten independent four-camera delivery audits with stale-pixel rejection; four saved-source comparisons with stale-site rejection; current unit tests and the exact strict assignment gate. All generated fixture work is under .runtime-work. The returned receipts are diagnostic software evidence only.

GPU handoff: review the original local right-turn site, district, frontage and loading-zone evidence. Run each exact case through the canonical prepare, execute and accept commands in gpu-queue-proposal.json, including source and comparison audits. Resolve legal and physical sufficiency from original footage and reviewed authority.

## Recorded-only post-capture handoff

Every one of the ten exact cases in `execution-manifest.json` has a `post_capture.command` and `feedback_command` calling `runtime.py process-saved` with the original attempt, separate versioned output, pinned library and validator, and an owner-release receipt. Execute these after Native exit and owner release. `process-saved` writes `v0001/processing.json` on a complete or source-incomplete analysis and `v0001/feedback.json` for source or validator failure. The source-incomplete path requests no Native replay.

`prove_post_capture.py --case CASE_ID` executes each case's source-shaped compatibility fixture and recorded-only processor. It requires the final video decode and unchanged originals in the positive run, removes `original-turn-signal.json` from a copy for missing-source feedback, and passes an absent validator path for processing-failure feedback. Exact cases and hashed logs are bound in each manifest `post_capture` and in `result.json.tests`. The fixture videos and packets are diagnostic only; original right-turn motion, physical signal visibility, site context and legal sufficiency remain for local review.

Reproduce with `SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c412593-postcapture" TMPDIR="$PWD/.runtime-work/c412593-postcapture" PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/testing__C412593__NRS-484B-413-2__motor_vehicle_driver/prove_post_capture.py --case CASE_ID`, replacing `CASE_ID` with each manifest ID. The final gate is `.venv-cpu/bin/python worker_check.py --assignment testing__C412593__NRS-484B-413-2__motor_vehicle_driver --complete --require-delivery-ready`; its output is in `strict-post-capture.log`.
