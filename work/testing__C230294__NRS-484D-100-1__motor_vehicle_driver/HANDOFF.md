# C230294 official device-directed lamps handoff

Status: ready as a delivery-prepared CPU package; exact scoped strict gate passed. Five selected branch (c) cases and four controlled comparisons are pinned. No local Native capture or legal verdict is claimed.

## Selected recordings

- `testing__C230294__NRS-484D-100-1__motor_vehicle_driver__day_device_lamps_on`
- `testing__C230294__NRS-484D-100-1__motor_vehicle_driver__day_device_lamps_off`
- `testing__C230294__NRS-484D-100-1__motor_vehicle_driver__day_no_device_lamps_off`
- `testing__C230294__NRS-484D-100-1__motor_vehicle_driver__night_device_lamps_on`
- `testing__C230294__NRS-484D-100-1__motor_vehicle_driver__poor_visibility_device_lamps_on`

Comparisons: `device_lamps_on_off`, `device_vs_no_device`, `day_vs_night`, `day_vs_poor_visibility`. The official-direction branch is selected. Night and reduced visibility remain independent source-backed context. Focused tests cover below, at and above the inclusive half-hour sunset/sunrise boundaries and the 304.8 m (1,000 ft) discernibility boundary.

## CPU proof inventory

- Five primary and five fallback1 source-gated offline constructions passed.
- Ten 900-frame, four-camera compatibility recipes passed with positive and negative receipts.
- Five recorded-only `runtime.py process-saved` replays passed through the Core/Lean decoder and final video decode.
- Five positive and five negative delivery audits passed on synthetic original-source fixtures.
- Four positive and four negative controlled comparison audits passed.
- Five physical preparation receipts cover candidate outcomes and lifecycle teardown; no physical acceptance claimed.
- Seven focused tests, five semantic stages and the 44-command exact-case queue proof passed.

## Stable artifact hashes

- `case-plan.json` SHA256 `8f9b8f5df7dcc619d8e19179ffd4a91c7d1651b77de367b42de9548eabcfc441`
- `execution-manifest.json` SHA256 `fdf5a217b4fa9d4f5408437731f6eb5377a6df42231eb306c4890c969476fb0b`
- `proposals/cases.json` SHA256 `dc393644627a03537ae0231988471931faf7ca31b9c07faf7158ec57800e6372`
- `proposals/semantic-index.json` SHA256 `a3d5ba6c18174d681b0a91c53009033144f3b8bc6781cfebbb66695cdb786ccf`
- `gpu-queue-proposal.json` SHA256 `fad63ad5f7059309843dce53c4d814a40ba37bd9cb1e40189d94241571c3ed81`
- `queue-proof.log` SHA256 `94c6f531aac15d350a3f82ab4e7d496dc869d6b0eff940fd6d4d67a61d822753`
- `comparison-proofs.json` SHA256 `db23ee6b75f4681717820c129edeec0e8e408a4ef8212dab4b21dbb273a0a8b2`
- `cpu-tests.log` SHA256 `1e997e9badcb6c51f2fff0c73fb30e6ae1fee88b220e23d632c87665345761b3`

## Acceptance gate

`.venv-cpu/bin/python worker_check.py --assignment testing__C230294__NRS-484D-100-1__motor_vehicle_driver --complete --require-delivery-ready` exited 0 with `static_checks_passed: true`. The direct ten-fixture compatibility validator also returned `True`. Strict log SHA256 `03451a9a5d48eb7031423eb7aa9ab35d1e357007a0538ead8d0bc74ff687c2b6`.

## Local execution handoff

The assignment-scoped `gpu-queue-proposal.json` provides production prepare, execute, capture, accept, owner release, saved processing and source audit commands for each exact case, plus fallback and comparison commands. Set local `CARLA_PYTHON`, `CARLA_HOST`, `CARLA_PORT`, database, run, job and audit variables before dispatch.

The local Native owner must review the actual official-device authority, route, message and timing; original lamp output; camera pixels; physical completion; and class-specific statutory sufficiency. Synthetic CPU receipts prove wiring and source integrity only. The saved-only finalizer reports measurements without a legal verdict.
