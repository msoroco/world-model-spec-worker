# C229452 red curb delivery handoff

Status: ready for exact CPU package delivery. The scoped strict gate passed on 2026-11-26. Native physical and legal acceptance require actual capture.

## Selected scope

- 20 exact red-curb cases, each with a source-gated primary and camera-pose fallback construction.
- 17 source-shaped comparisons with positive and damaged negative CPU audits.
- Four original synchronized cameras at 20 Hz for a 1806-second capture envelope; original event times measure the 1799/1800/1801-second passenger boundary.
- Ordinary park, stop and stand; signed tour, shuttle, limo and RTC passenger branches; special-vehicle business purpose; adjacent U.S. mail deposit and negative controls.
- Qualitative necessity and expeditiousness stay unresolved. Their sweep plans are incomplete pending independently reviewed business/mail activity and feasible ranges.

## CPU proof results

- All 40 primary/fallback offline checks and source-bound positive/negative compatibility checks passed.
- All 20 per-case physical fixture triples and lifecycle-order proofs passed; synthetic fixtures claim no Native physical completion.
- All 20 recorded-only saved-processing positives and missing-source negatives passed without Native replay.
- All 20 independent diagnostic delivery positives and missing-source negatives passed, including full four-view decode.
- All 17 controlled diagnostic comparison positives and damaged negatives passed.
- Thirteen focused unittests, package execution/semantic/delivery/compatibility validation, and exact scoped strict gate passed.

## Exact artifact hashes

- `case-plan.json` SHA-256 `d3e8d113a1aef1b92231b72d4bbbfe8d5fe62d9ee0d7da2f0dbe3260ddcbdf14`
- `execution-manifest.json` SHA-256 `aab5c679223314d57c18a852180885c538c725296d8e2478dd642a8d1df0e867`
- `proposals/semantic-index.json` SHA-256 `4668235f402a4d82531a51eba457b59507698e1c3b6a3d438555beef4c7e3fc3`
- `proposals/cases.json` SHA-256 `676dff67be8ae50074eb77ff58d5760d2e53e8d051b4d8ef274e220414c25d27`
- `gpu-queue-proposal.json` SHA-256 `60da90c1f284baad7e9d8419ae77dea09fc5bde24c9d866daee6575a83b3dd84`
- `red_curb.py` SHA-256 `6a772888c44441ae0dde99835f0f4a14254c492a9e7eb54fcd027e9ff6fa06b4`
- `native_capture.py` SHA-256 `d9add6da5cae4de10c07e8ecdd72219f18a9989261a17780985bcf8fa543b499`
- `analysis.py` SHA-256 `b9bf590d85aa7b8bb9f9d4fc55c9929bfeb2764885385e95fed44bce864c476a`
- `physical_completion.py` SHA-256 `73eb54baabe183e34042407e8ba5004a6afcb28e17aad6b87d52025a3a5a9c53`
- `delivery_audit.py` SHA-256 `3e9dfd07d1a4dd322f7b87daadcdb5e8c8df26739b1fa20a50d7a33eabbf3cdb`
- `comparison_audit.py` SHA-256 `d08bf4b3e514176e6de2e9a58d7035063529793bee975c4112fe823aa3206c08`
- `result.json` SHA-256 `5e56b313e6796d26594ce60b96d6fd12d34989b22be876f9bf7b0783e995b388`
- `cpu-tests.log` SHA-256 `67ebd99c5d5cbf4bf523a304698a6664ea1637e54c5f7daa576900e1dfc128c7`
- `cpu-package-validation.log` SHA-256 `c01549645df6a2b5b17241d537803eb47c58a8fcbebbcfb72662d4598155b26c`
- `cpu-strict-check.log` SHA-256 `e6c4b636ea169282984d9a421a87b9cfc75ced7f2b59036f16021bd821a5c80b`

## Local delivery handoff

The lead integrated `gpu-queue-proposal.json` into `work/_shared/gpu-queue.json` after independent scoped strict checks before and after publication. Every exact case has direct prepare, execute, accept, capture, saved-processing, owner-release and source-audit commands; the fallback command names its exact case and candidate. The proposal lists all 17 original-attempt comparison audits. `queue_original.py` checks reviewed original source custody, trace/camera joins, four video dimensions and full decodes, and exact pair fields. It rejects synthetic saved attempts; a scratch-only source-shape pair exercised its comparison path without claiming original evidence. The original source audit's physical result remains unverified until local review supplies original curb occupancy evidence. Queue proposal SHA-256 is `b3b0c3d5440f7962c6945052a3ef0a274d8064040142c45de59dca7724b3c2b7`; shared queue SHA-256 after this integration was `9976c1e5394f8a5ad4027ccb4064beb0b13bbf6f7a68b2ad51f8d00d2327d86a`. Independent post-publication strict log is `.runtime-work/c229452-lead-nov26/strict-after-queue.log` (SHA-256 `e6c4b636ea169282984d9a421a87b9cfc75ced7f2b59036f16021bd821a5c80b`).

First Native command:

```sh
PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m scenario_pipeline.worker_exchange --root "$LOCAL_ROOT" execute-delivery --repo "$PWD" --batch full-test-delivery --db "$DB" --run "$RUN" --assignment testing__C229452__LVMC-11-52-030-A__motor_vehicle_driver --case testing__C229452__LVMC-11-52-030-A__motor_vehicle_driver__ordinary_park --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"
```

Actual original red curb, jurisdiction, sign, vehicle status, passenger/business/mail activity, full pixels, cleanup and legal conclusion remain subject to independent local review. Diagnostic media and synthetic fixture rows are software probes only.
