# C229628 LVMC 11.16.090(A) handoff

Status: partial CPU preparation. Frozen accepted evidence is empty. The selected branch is aiding or abetting another motor vehicle speed contest upon a highway; engagement or exhibition alternatives are separate statutory questions. Cue and motion observations do not decide the meanings of contest, aid or abet, or intent.

## Exact cases and controlled reuse

- `start_cue_candidate_contest` is the common two-person/two-motor-vehicle reference with a physical high-beam start cue, candidate episode and source-designated highway.
- `no_cue_candidate_contest` changes only the cue. The `cue` comparison holds participant, vehicle, route, lane, episode and highway context fixed.
- `start_cue_no_contest` changes only the underlying candidate episode. The `episode` comparison holds the cue and highway fixed.
- `start_cue_off_highway` changes only source-designated highway status. The `highway` comparison holds the cue and candidate episode fixed.

All four cases reuse the same reviewed route, lane marking, person and vehicle identities and 45-second four-camera contract. This is four planned recordings and three controlled comparisons. The candidate episode is an observation request, never a legal finding.

## Constructed and tested

`contest_aid.py` gates two distinct persons and vehicles, cited independent source roles, cue/start ordering, route and lane-marking geometry; its original finalizer requires 900 consecutive 20 Hz frames and preserves unresolved judgments. `native_source.py` verifies the exact reviewed site, Native map source hash and every independent source file hash. `runner.py` selects the exact bundled case. `contest_carla_adapter.py` lazily connects to the reviewed CARLA map, spawns and routes two motor vehicles, controls their motion, flashes the ego high beam for the cue and reads back its Native light state, attaches four cameras, and restores synchronous world settings. `contest_capture.py` acquires 900 original Native frames and four synchronized image streams, joins two-vehicle motion and cue readback, and writes trace, frame map, packet, measurement and source receipt under `.runtime-work/`. `analysis.py` is a saved-only source-joined finalizer with no legal verdict. `build_constructions.py` materializes four exact inline bundles, including the root construction. `build_semantic.py` writes draft relevance, template, judgment-observable, binding and case proposals. `comparison_audit.py` independently checks the three fixed-condition/difference pairs and rejects altered source packets. The comparison audit has not yet been bound to selected manifest proof receipts.

`cpu-tests.log` records eight focused passing tests, including source tampering and comparison isolation. `cpu-preflight.log`, `cpu-runner-check.log` and `cpu-static-check.log` pass. The scoped static command is `.venv-cpu/bin/python worker_check.py --assignment testing__C229628__LVMC-11-16-090-A__motor_vehicle_driver --complete`.

## Remaining CPU work

Complete source-shaped diagnostic recipe and measurement contracts; bind four selected constructions into `execution-manifest.json`; run exact offline and positive/negative compatibility per case; test saved-only processing and physical/lifecycle checks; implement and prove independent delivery audit; prove all three independent comparison audits from sealed fixtures; review any concrete physical risk and test a fallback only if justified; generate exact queue proposal. Then set `result.json` ready only after all CPU proofs pass, and run `.venv-cpu/bin/python worker_check.py --assignment testing__C229628__LVMC-11-16-090-A__motor_vehicle_driver --complete --require-delivery-ready`. Current partial status is intentional. Native route realization, camera visibility, physical completion and legal review remain local post-CPU checks.
