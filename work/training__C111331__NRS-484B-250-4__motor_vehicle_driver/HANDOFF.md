# NRS-484B-250-4 at C111331

Actor: `motor_vehicle_driver`. Frozen cell: `intersection` / `travel` / `traffic_light`.

Exact source: NRS 484B.250(4). The full text and source hash are retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branch: Marked stop line; complete cessation; all-entrance stop treatment..

Controlled variable: `complete stop and precedence under inoperative uncovered signal`. Requested pair: stop at governing point and yield before cautious entry; enter past governing point without a complete stop. These are construction requests, not measurements or legal verdicts. The baseline is unselected.

Statutory branch dispositions: 3. Review each exception and dependency against the exact text before physical selection. Accepted membership rows: 0; no source-hashed equivalence receipt is available, so reuse is unclaimed.

Status: `partial`. Two unselected 30-second source requests and pinned offline proofs now exist. Executable Native capture, current compatibility and saved processing, selected measurement and physical verification remain open work.

Resume: build Native geometry, actor control, cameras and mandatory capture for each runnable branch; prepare the primary and risk-justified source-preserving fallbacks per selected case; run exact pinned-runtime compatibility, saved positive/negative fixtures and an independent audit. Set `ready` only after those CPU proofs pass.

Source-context review: Signal must be installed, vehicular indications uncovered and inoperative at ego entry. Stop-point priority is line, then near-side crosswalk, then nearest point with view. The after-stop yielding and cautious-entry duties need separate observations.

## 2026-11-23 exact source request and current offline proof

`native/build.py` constructs two 600-frame, 20 Hz, 30-second unselected source requests bound to frozen assignment SHA-256 `8f4584097a04f11c2af5ccffe5a5a43e675b9160afea1d235cbf5ef735d2a7ae` and exact NRS 484B.250(4) text. Both request the same installed, uncovered, inoperative vehicular head, marked stop line, near-side crosswalk and other vehicle. `controlled_1` requests ego stop with its front at -13 m, before the -12 m stop line, through frame 210 while the other vehicle passes; `controlled_2` requests uninterrupted travel past the line. The signal/head, stop and yielding are authored requests only. No Native state, actual inoperative indication, physical stop, cautious entry or legal result is inferred.

The pinned `runtime.py offline` checks pass both exact primary constructions (logs SHA-256 `c250314d772b4155fd93d3ce8d6df4edebd3ee8f4652dd27bfb12273aa0c3d35`, `4358fccea14064ff553af842272833454b6767193ba05fd5f2fd6a0b0001be37`). Manifest SHA-256 `bd45458f387a347549a86d074788efbc9ee7e5150aa31bc29e3e4272e14b3c7c`. `native/prove.py` independently checks construction hashes, the fixed signal and other-vehicle request, the stop/no-stop contrast, and rejects four malformed source bundles including rehashed route, altered indication, shifted stop line and missing source. Proof SHA-256 `cd41d14f5d2baf69af4961f8ad824cee8d34b28a6c79572ed93dfc77dfa00258`.

Reproduce from repo root with `TMPDIR="$PWD/.runtime-work/c111331-2504-tmp" PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C111331__NRS-484B-250-4__motor_vehicle_driver/native/build.py`, then `runtime.py offline --manifest work/training__C111331__NRS-484B-250-4__motor_vehicle_driver/native/draft-execution-manifest.json --case ASSIGNMENT__controlled_1 --output .runtime-work/c111331-2504-tmp/offline-1 --python "$PWD/.venv-cpu/bin/python"` (and controlled_2/offline-2), then `native/prove.py` with the same TMPDIR. Offline output is scratch under `.runtime-work/`.

Next CPU work: implement actual Native junction geometry, installed/uncovered vehicular signal and inoperative-at-entry acquisition, controlling stop at the governing line, other-vehicle precedence and cautious-entry observations, four cameras and FrameMap. Add source-only saved finalizer and public compatibility/process-saved positive and missing-source negative proofs for selected cases, plus risk-based fallbacks and independent comparison/statutory audits. The no-line crosswalk and no-crosswalk visible-point alternatives need separate controlled requests or source-backed disposition.

Assignment-scoped `.venv-cpu/bin/python worker_check.py --assignment training__C111331__NRS-484B-250-4__motor_vehicle_driver --complete` exits 0; log SHA-256 `0c938932e3cf889879c9535ae000226fcc669f888a6cdfb5292344a4b1166989`. The strict ready gate was not run because the package is partial.
