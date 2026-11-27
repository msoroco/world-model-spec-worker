# C377875 LVMC 11.52.070 motor vehicle driver handoff

Status: CPU delivery prepared. The exact assignment strict gate passed on 2026-11-27. Original CARLA capture and external legal/source review remain for GPU delivery; no original scene or legal outcome is claimed.

The selected branch is vehicle front orientation while standing or parking in an angle-parking space on a street designated by the City Traffic Engineer and indicated by signs or markings. Four exact cases cover stand/park and forward/opposing orientation. Two controlled comparisons hold the activity and reviewed site facts fixed while changing the requested front orientation. The 0/180-degree yaw values are engineering requests, not a statutory threshold or legal tolerance.

The Native runner records original vehicle pose and controls at 20 Hz, roadway and marking context, and four synchronized views. The saved-only analyzer binds frame evidence to source hashes and requires the original Engineer determination, permission extent, marking, lawful traffic direction, vehicle front, and stand/park purpose. It reports front-versus-lawful-direction geometry and leaves legal classification unreviewed. Missing or inconsistent original sources fail closed.

CPU evidence: eight selected construction offline proofs, eight positive and negative compatibility proofs, four saved-only processing proofs, physical complete/incomplete/missing/lifecycle fixtures for all four cases, four positive and negative delivery audits, and positive and negative source-bound audits for both comparisons. Eight focused unit tests and the scoped static check passed. All proof receipts are bound in `execution-manifest.json`. The first GPU command and ordered case/comparison instructions are in `gpu-queue-proposal.json`.

After actual CARLA capture, review the original City Traffic Engineer authorization and marking extent, lawful lane movement, vehicle front and activity purpose, then run the source audit, saved-only processing, and comparison audits before acceptance. A diagnostic synthetic media fixture was used only to exercise the CPU audit; it is rejected without diagnostic mode. No accepted recordings were available for this exact branch.

Strict command: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python worker_check.py --assignment testing__C377875__LVMC-11-52-070__motor_vehicle_driver --complete --require-delivery-ready`.
