# training__C230207__LVMC-11-22-120-B__cycle_or_scooter_operator

Status: **partial**. The signed bicycle roadway Native draft passes CPU offline checks. No delivery-ready case, CARLA execution or accepted recording is claimed.

Exact source: LVMC 11.22.120(B) separates the City Traffic Engineer's designation of a heavily traveled street, erection of an appropriate sign, restriction actually stated on the sign, and disobedience by a covered traffic class. The selected human-propelled bicycle subtype is named by the law. Scooter and motor-driven-cycle coverage are not inferred. The source gives no numerical traffic-volume or sign-adequacy standard. No accepted membership IDs are present.

## Construction and measurements

- `native/geometry.py`: 120 m straight OpenDRIVE road, 3.5 m driving lane, 2.5 m shoulder and positive-direction signal metadata `BICYCLES PROHIBITED ON ROADWAY` at x=-45. This is authored metadata, not proof of official designation or a readable physical sign.
- `native/runner.py`: requires original map signal text/orientation and three driving-lane readbacks before capture; spawns `vehicle.bh.crossbike` at x=-50 and applies 2.3 m/s eastward velocity for 600 ticks. It retains original rider poses, `FrameMap` identities and four synchronized FFV1 camera streams, then destroys owned actors and restores the world. CPU fake-map tests reject wrong sign and lane. No CARLA run is claimed.
- `native/measure.py`: requires retained 600-frame bicycle trajectory, 20 Hz identity, sourced rider class/wheel review, exact sign source and Native roadway survey. It reports roadway use and use after the sign without a legal verdict. Native output deliberately leaves wheel review and official designation unverified; the fixture's `true` review flag is synthetic and cannot establish them.
- Draft construction SHA-256 `d0dcb757a27e8f4415c8347df6a0c390341053a1547523536d230dcedf101644` under pinned runtime `ade64f2acdaf6d4b653c38f49b71f8c4bd2cf4a985cab7313f160b97b06c3d90`.

## CPU proofs

- `SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c230207-proof TMPDIR=$PWD/.runtime-work/c230207-tmp .venv-cpu/bin/python runtime.py offline --manifest work/training__C230207__LVMC-11-22-120-B__cycle_or_scooter_operator/draft-signed-roadway-manifest.json --case training__C230207__LVMC-11-22-120-B__cycle_or_scooter_operator__probe_02 --output .runtime-work/c230207-offline-02 --python $PWD/.venv-cpu/bin/python` passed; `signed-roadway-offline.log` SHA-256 `2663a0656612f974e1758995afd6d988279b04652539ae0880c03dfb8c021357`. No simulation started.
- `.venv-cpu/bin/python work/training__C230207__LVMC-11-22-120-B__cycle_or_scooter_operator/prove-measure.py` passed synthetic roadway (600 occupied, 556 after sign) versus shoulder (0 occupied) positives, and rejected missing original frame, missing sign survey and wrong rider class; `signed-roadway-measure-proof.log` SHA-256 `4e5b932bf4978075ca0e1875d0338e607aa8a8a8bbc8734aca609d87299626eb`. Fixtures are under `.runtime-work/` only.

## Open work

Obtain source evidence for City Traffic Engineer designation and road restriction; inspect actual CARLA sign rendering, placement, direction, bicycle wheel/subtype and body trajectory. Build off-road probe_01 with fixed sign/route/camera conditions, current-runtime saved processing and negative compatibility, Core finalizer, semantic proposals, independent acceptance/comparison audits and risk candidates. Keep partial until all CPU proofs and strict scoped ready gate pass; later GPU physical review remains separate.
