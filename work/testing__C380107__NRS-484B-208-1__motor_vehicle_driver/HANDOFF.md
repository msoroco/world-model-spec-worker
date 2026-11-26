# testing__C380107__NRS-484B-208-1__motor_vehicle_driver

Status: CPU delivery prepared; original local CARLA capture and independent legal review remain pending. The exact scoped strict CPU gate passed on 2026-11-26. No physical acceptance or legal verdict is claimed.

## Selected construction

The canonical semantic draft selects 18 exact NRS 484B.208(1) cases and 11 controlled comparisons. The nine source-law variants cover the core extreme-left-lane encounter, qualified/ineligible/inactive HOV operation, posted-limit equality, no faster rear vehicle, moving right, city boundary, and hazard necessity. Three bounded three-point sweeps cover sign exposure onset, rear speed delta, and original HOV occupancy. Sweep stations are engineering controls, not legal thresholds. All selected requirements have explicit source-bound measurement methods; legal knowledge, continued operation, and HOV qualification judgments remain unresolved.

Each selected case has an inline exact Native construction. The runner requires a SHA-linked reviewed controlled-access highway, marked same-direction lane geometry, posted limit, geography, HOV designation/hours/occupancy/access/sign/category/compliance, knowledge circumstances, exception authority, and reviewed actor/camera poses. It checks the selected controls against source packets, samples ego and rear actor/lane/speed/gap and four synchronized RGB views at 20 Hz for 900 frames, and emits a SHA-bound original context, motion JSONL, frame map, wrapper, and receipt. The finalizer checks the receipt and wrapper against original motion before deriving measurements. Source and capture gates fail closed; the diagnostic fixtures remain synthetic.

## CPU evidence

- Pinned runtime verify and preflight: exit 0.
- Focused tests: 25/25 pass, including reviewed-site source joins, original capture receipt tamper rejection, exact control bounds, source-bound measurement, comparison isolation, and delivery audit refusal.
- Pinned offline construction: 18/18 pass against current inline hashes.
- Exact saved compatibility: 18/18 pass, including native validation, Lean decoder, final video decode, measurement contract and missing-source negative proof.
- Saved processing: 18/18 pass, recorded-only with originals preserved and no physical acceptance claim.
- Physical/lifecycle/delivery CPU protocols: 18/18 pass, with expected unreleased-attempt rejection.
- Exact comparison protocols: 11/11 pass against current case construction and compatibility seals; original comparison receipts remain a later local task.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C380107__NRS-484B-208-1__motor_vehicle_driver --complete --require-delivery-ready`: exit 0; output in `cpu-scoped-strict.log`.

`execution-manifest.json` binds all 18 current case chains. `gpu-queue-proposal.json` contains 18 canonical local delivery rows and 11 comparison audit commands for lead review and queue integration. Original site authority, CARLA realization, camera pixels, HOV eligibility, legal exceptions, and independent physical review remain local checks. No frozen input, runtime, batch, or shared queue file was edited by this owner.
