# testing__C158196__NRS-484B-307-6a__motor_vehicle_driver

Status: **ready for GPU delivery preparation**. The exact scoped CPU strict gate passed on 2026-11-26. Manifest SHA-256: `93ede542792eb989f158e41612ecab04da8bddf6ad02a9364904061af31c6710`. The assignment-local GPU queue proposal is `gpu-queue-proposal.json` (seven exact cases, six comparison audit commands); lead integration into the shared queue remains separate.

## Scope and evidence

NRS 484B.307(6)(a) concerns a steady yellow signal alone facing vehicular traffic, warning of green termination or red immediately thereafter, and prohibits entry when red is exhibited. Cell C158196 is a one-way-to-two-way intersection for a motor-vehicle driver. The seven frozen accepted records lack exported original trace/video; `case-plan.json` reviews their frozen metadata and retains explicit source gaps. The measured 20 Hz body-entry and signal-transition brackets do not create legal timing cutoffs or claim a verdict.

The seven exact selected cases are `enters_yellow`, `enters_red`, `inside_on_red`, `red_other_route`, `yellow_red`, `stops_red`, and `yellow_non_alone`. Six controlled comparison plans cover yellow versus red entry, red after entry, stop versus enter, selected versus other-route red, phase response, and yellow-alone versus companion indication.

## Construction and proofs

`construction.py`, `signal_carla_adapter.py`, `signal_original_runner.py`, `signal_capture.py`, `signal_measurement.py`, `signal_capture_audit.py`, and `analysis.py` implement the source-gated Native scene, official facing/other/companion signals, surveyed entry polygon, original 900-frame four-camera acquisition, source hash/frame joins, and saved-only analysis. The adapter restores world settings and releases owned actors. One slower-controller physical fallback per case has a predeclared original phase/entry failure trigger; it preserves law, route, cameras and recording channels.

All seven selected constructions passed current-hash exact offline, positive/negative compatibility and saved-only CPU proofs. All seven fallback constructions passed exact offline and positive/negative compatibility. Each case has three source-shaped physical outcomes (met, not met, unverified), a Native ownership lifecycle protocol proof, and an independent delivery audit positive/negative diagnostic. All six comparison isolation checks reject a changed fixed map. Synthetic diagnostic receipts explicitly make no Native acceptance claim. The focused suite passed 20 tests. Original CARLA motion, four-view pixels, full video decode, physical completion and human interpretation remain for GPU execution and independent review.

## Reproduction

- `SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c158196-owner-nov26 TMPDIR=$PWD/.runtime-work/c158196-owner-nov26 PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python worker_check.py --assignment testing__C158196__NRS-484B-307-6a__motor_vehicle_driver --complete --require-delivery-ready`
- `.venv-cpu/bin/python -m unittest discover -s work/testing__C158196__NRS-484B-307-6a__motor_vehicle_driver/tests -v`
- `execution-manifest.json`, `comparison-proposal.json`, and `gpu-queue-proposal.json` bind the selected proof and review work.
