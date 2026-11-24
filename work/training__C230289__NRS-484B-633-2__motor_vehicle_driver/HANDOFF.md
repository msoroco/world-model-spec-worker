# C230289 / NRS 484B.633(2) CPU handoff

Status: **partial**. Both planning probes remain unselected. The selected requirement in `case-plan.json` is a planning obligation, not a selected recording or covered branch.

## Exact source and cell

- Current assignment SHA-256 `aa1e318e420035325d18be17b81c4ec44c4c568995e143f1e1aa2f92bbf4a1fb`; witnesses SHA-256 `96ccc35f2f9ca4ecfb5c666f077208fe5cb88f2f693d326888a3a3af0a624a10`. No accepted recordings are listed.
- Fixed cell is `road / travel / speed_limit_sign`, driver `motor_vehicle_driver`. The exact provision concerns speed **over** a bridge or other elevated highway structure beyond a declared safe structural maximum, when it is signposted under the appended administrative conditions. An ordinary speed-limit sign or generic road is insufficient. The frozen witness is conditional and low confidence; it asks for chapter 408 highway status, Department investigation/finding/declaration and signs stating the structural maximum 100 feet before each end.
- Probe 01 is a below-maximum comparison draft; probe 02 is above-maximum planned only. Neither has an expected legal label. No fixed numeric structural maximum was invented: the Native controller requests a speed 10 mph below an original surveyed declaration, and that request is never treated as measured motion.

## CPU construction and proof

- `bridge_speed_measure.py` SHA-256 `33e45b6672fb4eacdb4afe86ac368f765ccee80c6613c154b7fabb1a1d84fb3a` requires a source-identified highway structure, chapter 408 context, Department administrative declaration and two authorized 100-foot structural signs. It joins 600 contiguous 20 Hz frames to the same vehicle and structure, computes speed from velocity vectors only during sourced structure occupancy, and leaves the legal result null. `prove_bridge_speed.py` SHA-256 `f7fab61517e628a3b3f9f1cd4197360fa3d5afde343b7c3d3c2bfaf498c76624` runs positive above/below synthetic cases and negative sign placement, declaration and missing velocity checks, binding current assignment/witness hashes. Normal and `-O` logs each SHA-256 `63a0c176de0e919fcf8c047fa01a68902fa93e78ec56f6326eeb1f88ef7045f7`. All synthetic packets are CPU diagnostics, not original source or accepted evidence.
- `native/runner.py` is an executable, original-survey-gated CARLA draft. It has a bridge-route controller, four source cameras, 600-frame 20 Hz PipelineCapture, FrameMap, and post-tick original position/velocity trace; it records structure occupancy as **unverified**. Construction SHA-256 `2d2a84d2fcb40e42033934f7afb918c5d740ec02305f93ccc3b72550c5da88ad`, partial manifest SHA-256 `8b087367fb8ed859919f0771781736f64a504418c2fac4c290d5f3dcef30cdd7`. Four Native CPU tests pass (log SHA-256 `b18123c57fe1f462dd17bb1b262821ec93b15b834fbeb652362e344f74f2b9cb`). Pinned `runtime.py offline` passes with `simulation_started: false` (log SHA-256 `328da1eb3abf19d5ca435c5336823881d859b06815a19a02db73a5b3c95f5099`).
- `.venv-cpu/bin/python worker_check.py --assignment training__C230289__NRS-484B-633-2__motor_vehicle_driver --complete` passes static checks. No strict ready claim is made.

## Remaining worker-owned CPU work

1. Bind an original source-hashed survey establishing that the selected road route actually crosses a chapter 408 highway bridge/elevated structure, its endpoints, both maintained structural signs 100 feet before each end, their visible instructions/governed approaches, and Department investigation/finding/declaration of the safe maximum. The current generic cell and witness do not supply these facts.
2. Implement a saved finalizer that derives structure occupancy from original route geometry and Native pose, joins post-tick velocity and four videos, then runs current-runtime positive and negative compatibility and saved processing. The synthetic diagnostic does not substitute for these selected-case proofs.
3. After source review justifies selection, finish both exact comparison cases and risk-based candidates, semantic proposals and independent delivery/comparison audits; run the assignment-scoped strict ready gate. Native physical execution and acceptance remain separate local work.
