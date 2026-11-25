# training__C230259__NRS-484B-600-1e__motor_vehicle_driver

Status: CPU delivery preparation complete; original Native capture and independent source review remain pending. This handoff claims no achieved physical speed, legal verdict, or accepted recording.

## Exact scope

NRS 484B.600(1)(e) makes driving or operating a vehicle of any kind or character at a rate **greater than 80 mph** unlawful in any event. Posted speed is not an input to this clause. The three selected physical requests are 75, 80, and 85 mph; original post-tick velocity determines observed speed. The accepted membership snapshot for demo-train and full-train is empty.

## Selected CPU proofs

- `training__C230259__NRS-484B-600-1e__motor_vehicle_driver__probe_01`: primary construction SHA-256 `4d22441becd88d2e7631de32ec004248fe98858af3b6633f36057b9d5eb84678`; offline log SHA-256 `f11fbf1782806e10924462e4e949c2c37a5dd030120f66d5dfd40cc5722398c8`; public positive/negative receipt SHA-256 `2eb132fff0e9d638f73b4268b2c3ce59cc869631699e836fb9762e68c0876274`; recorded-only saved log SHA-256 `a97d06ff84d21260ff1d207bf1cd9048597e76126ced86efc1ef56e286411519`; delivery positive/negative log SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` / `d765c2a8c004598c38687636e0d6c349b7c8a0a3a24bd9fae6c773ebd21039d9`.
- `training__C230259__NRS-484B-600-1e__motor_vehicle_driver__probe_02`: primary construction SHA-256 `5e0538e96f9cab244f37bd9411a711f0d6aacd35463e5cae399ee5f89c1155f9`; offline log SHA-256 `2c4f163a136d22c0ba5c686d9f2c509f271243f75594b0d6a5a852debcb47f0e`; public positive/negative receipt SHA-256 `3a4a0d4b658bdd83c61b2a9b1661041b9a0f7844c451d692c486add7e6b28c15`; recorded-only saved log SHA-256 `8311e34a02b7c6b914f1c818065ad1c0d2296623455da2fc9be6a6ee89dfc43a`; delivery positive/negative log SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` / `d765c2a8c004598c38687636e0d6c349b7c8a0a3a24bd9fae6c773ebd21039d9`.
- `training__C230259__NRS-484B-600-1e__motor_vehicle_driver__probe_03`: primary construction SHA-256 `995aaa8b6bfc4911bb69c44932130f802425ec41b2233ee712be4bdd47d1d6ff`; offline log SHA-256 `1b301a5e82a364ad3cf16e01b76216f8595dc1f32ce6b950133dd85949acbae1`; public positive/negative receipt SHA-256 `77ec71993d952e7fea9e57645a92341f22ffaeb674c0aaea6345831c626c4a59`; recorded-only saved log SHA-256 `9c20488235380b0826081b0e7b73d61d72a90780af758e7f88e3a5dac2fcd6f4`; delivery positive/negative log SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` / `d765c2a8c004598c38687636e0d6c349b7c8a0a3a24bd9fae6c773ebd21039d9`.

The 85 mph case has a source-triggered throttle-gain fallback, construction SHA-256 `6a7ef55fbd0aa3e7adb8c5f306e40d592c1f5fec41061643994dfa0e38026ff7`, with offline and public positive/negative proofs. The fallback changes the proportional gain from 0.14 to 0.18 and keeps the requested speed, case, route, cameras, and measurement contract fixed.

The five-stage canonical semantic chain is bound by `proposals/semantic-index.json` (SHA-256 `376b7dc42fc82a01bb1e677c40c7ec9a2fad5c37b92902360af1b8cae1ca85ce`). The independent comparison audit and its positive/negative CPU tests are bound in `case-plan.json`; they require original source hashes and measured below/at/above observations, rather than inferring them from controller requests.

The Native runner records four synchronized cameras, original velocity and participant IDs, `trace.jsonl`, per-tick `PipelineCapture` evidence, Native provenance, and a capture seal after encoder closure and world restoration. The finalizer joins the original CARLA frame, not the zero-based video index. The original route, vehicle capability, actual pixels, and measured speed require GPU execution and source review.

## First exact GPU command

```text
PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python -m worker_exchange execute-delivery --repo . --batch full-train-delivery --db $DB --assignment training__C230259__NRS-484B-600-1e__motor_vehicle_driver --case training__C230259__NRS-484B-600-1e__motor_vehicle_driver__probe_01 --run $RUN --job $JOB_ID --python $CARLA_PYTHON --host $CARLA_HOST --port $CARLA_PORT
```

After the Native attempt, review the saved `road_context.template.json` against the original map, vehicle identity, other vehicle, driving state and four camera byte hashes to produce `road_context.json`. Then use the manifest `post_capture` command for recorded-only processing and run `delivery_audit.py` without `--diagnostic` for independent original-source acceptance. The CPU receipts use synthetic diagnostic sources only.
