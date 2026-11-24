# LVMC 11.52.340 at C150129 — partial CPU construction checkpoint

The frozen one-way/park/restriction-device cell and two controlled case IDs are preserved. The exact text distinguishes a City Council designated space, due posting or marking, a non-City vehicle, and parking within the space. No accepted membership exists. The street branch is drafted; the City parking facility alternative needs separate cell review because this fixed layout is a one-way road.

## New construction and proof

- `native/geometry.py` authors a one-way OpenDRIVE street with driving and curb parking lanes, two separated parking segments, and a survey gate for original Native lane readback.
- `native/runner.py` drives and brakes an original subject toward each distinct segment, records 600 frames at 20 Hz with four source cameras, original vehicle poses/speed/bounding boxes, FrameMap joins, FFV1 video, and world restoration. Its output explicitly leaves City designation, posting, street jurisdiction, and vehicle status unverified.
- `parking_measure.py` computes full vehicle footprint and stationary proxy intervals from retained frame samples and rejects missing authority/status provenance. It emits no legal verdict. `prove_parking.py` passes normal and optimized Python 600-frame source-shape tests, including missing designation, wrong posting-space join, unknown vehicle status, changed identity, and short recording rejection.
- Both exact primary construction drafts passed pinned `runtime.py offline` using `.venv-cpu/bin/python` and `.runtime-work/` output. `worker_check.py --assignment training__C150129__LVMC-11-52-340__motor_vehicle_driver --complete` passed after the case-plan update.

Proof hashes: controlled_1 construction `573c8c01f137e5ec7cbf9c21e70317677b4fc9a4d70ed1078a7265cbad8968bd`; controlled_2 construction `624f0b9cc6dc144453119806ae01a3cb4f1ac02c5bb822d3482c27f0d27b7d45`; 600-frame proof `1c347465076d09fabcdb43c1527db7db4ad2350918567dbc426f77d5d9a325ef`; scoped check `cd82416b693bc6040379e9e1fb9ea8cd34ef0cefe6d7e367852077b6a0794bb9`. Both pinned offline logs hash `d977382215fc24d41c0231c64b7d6f5c0a518062fc28e40089edab41d2f7aaba`.

## Remaining worker-owned CPU work

Bind source records for City-street jurisdiction, City Council designation, posted/marked space and its spatial association, and the subject's City-vehicle classification; geometry, livery or blueprint alone do not establish these facts. Complete selected execution manifest, one primary plus three distinct tested fallbacks for each selected case, saved-result finalizer, positive and negative compatibility fixtures, independent acceptance and comparison audits, canonical semantic proposals and exact queue entries. Review the City facility alternative against the full statute and candidate cells. Re-run affected receipts and the assignment strict ready gate only after those parts exist. Native physical results and legal sufficiency remain unobserved.
