# training__C295180__NRS-484A-450-2__motor_vehicle_driver

Status: partial CPU construction checkpoint. The exact two inline cases remain unselected drafts; original Native, physical and legal outcomes are unclaimed.

The exact law has three ordered stopping references: before the near-side crosswalk; absent that, at a clearly marked stop line; absent both, at the nearest point with a view of approaching intersecting traffic. The frozen selected witness names the second branch: no crosswalk and a clearly marked stop line. The other two references remain separate unbuilt branches. No accepted membership rows are available for reuse.

## Current exact construction

`native/stop_line_request.py` generates two 600-frame, 20 Hz, 30-second authored requests for the exact planned comparison IDs on the same T-intersection approach. The fixed sign governs the approach, the near-side crosswalk is absent, and the stop line is at x=0 m. The comparison changes only the stop policy: one request halts its front footprint before the line and one continues through. The source meter requires the full frame/time join, sign/line source, finite ego readback and body/center agreement. It measures a 44-frame pre-crossing stop in the first request and no pre-crossing stopped frames in the rolling request. Three negative diagnostics reject a missing sign, missing stop-line source and forged original provenance. The 0.1 m/s and 20-frame probe is an engineering diagnostic, not a statutory duration threshold.

`native/build_draft.py` authors exact primary inline constructions with four named source cameras and a 30-second window. The pinned `runtime.py offline` command passes for both. They are unselected because they do not yet include Native capture, source-bound compatibility or saved processing. `native/measurement-contract.json` maps all twelve law-planning observation terms to later original sources; the sight-distance and visible-traffic terms belong to the separate no-crosswalk/no-line branch.

Source/proof SHA-256:

- `native/stop_line_request.py`: `d903ee303d0a16a0ed1835b2ab55b0c77da25d9adfdef869baf559fb90d3ab62`
- `native/stop-line-diagnostic-proof.json`: `9c541c6c8887a004e76469bb3d5b3e321e5feaa504264841fc50d1cd2500d16c`
- `native/measurement-contract.json`: `6b2cc7032dc5f406a0da626b59d7d3807cb5ee53559c1d70e6ab4ef48695314e`
- `native/draft-manifest.json`: `604c1e9ea46c03deb7d476934bcdf8d65f12881cf80686cb6d3d5c0698315197`
- `native/condition_a-construction.json`: `739f903b292cba681dc2b5e425602d315cf8c3620546d0951523fbdb7d62424f`; passing `native/condition-a-offline.log`: `739f903b292cba681dc2b5e425602d315cf8c3620546d0951523fbdb7d62424f`
- `native/condition_b-construction.json`: `f69acfaa9acafff05bcbc6bb8be5a3edbcb1ac907c868d2e1a4a68c5b228c98b`; passing `native/condition-b-offline.log`: `f69acfaa9acafff05bcbc6bb8be5a3edbcb1ac907c868d2e1a4a68c5b228c98b`

Diagnostic rows and negative fixtures are under ignored `.runtime-work/c295180-stop/`; current offline materializations are under `.runtime-work/c295180-stop-offline-a-new/bundle/` and `-b-new/bundle/`.

Passed commands:

```text
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C295180__NRS-484A-450-2__motor_vehicle_driver/native/stop_line_request.py prove --output .runtime-work/c295180-stop
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline --manifest work/training__C295180__NRS-484A-450-2__motor_vehicle_driver/native/draft-manifest.json --case training__C295180__NRS-484A-450-2__motor_vehicle_driver__selected_ef239a06__condition_a --output .runtime-work/c295180-stop-offline-a-new/bundle
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline --manifest work/training__C295180__NRS-484A-450-2__motor_vehicle_driver/native/draft-manifest.json --case training__C295180__NRS-484A-450-2__motor_vehicle_driver__selected_ef239a06__condition_b --output .runtime-work/c295180-stop-offline-b-new/bundle
```

## Next CPU work

Bind the authored Native acquisition to exact source-bound compatibility fixtures and recorded-only processing, with a saved finalizer and source-negative test. Add risk-based fallback only for a concrete overshoot or camera risk. Complete canonical semantic proposals, independent physical/lifecycle and delivery/comparison audits, selected execution manifest and exact strict gate. These are worker-owned CPU gaps. C111325 and C24805 have separate current-runtime ready packages for the crosswalk and no-crosswalk/no-line alternatives; their evidence is not treated as accepted reuse here. The three reviewed-scope crosswalk topics in this case plan must be mapped as observed absence for this stop-line branch before a ready claim.

## 2026-11-25 saved-source meter continuation

`native/saved_stop_line.py` now reads a hash-sealed source inventory containing exact-case Native body/speed rows, frame-map rows and a separate applicable-reference readback. It rejects missing or changed hashes, incorrect sign/crosswalk/line source, incomplete 600-frame joins, nonmonotone Native frames, invalid body/speed values and missing ordered line/intersection crossings. It measures the longest pre-line stopped run before the front footprint first crosses the line. The 0.1 m/s and 20-frame criteria remain engineering fixture probes; no statutory duration, physical completion or legal verdict is asserted. `native/prove_saved_stop_line.py` exercises the full-stop/rolling pair and three source-rejection branches in scratch under `.runtime-work/c295180-saved-meter`. Proof: `native/saved-stop-line-proof.json` (SHA-256 c597db00495811e6b9177b1f6cc72fc6aab435f672c75f5b67a52821c368c921).

The original Native acquisition and sealed original camera pixels still need construction. The current proof uses explicitly labeled synthetic CPU fixtures, and selected compatibility, recorded-only processing, canonical semantic proposals, physical/lifecycle and independent delivery/comparison audits remain CPU work. The exact partial check passes; the strict assignment gate correctly rejects the partial status.

## 2026-11-25 authored Native construction continuation

`native/authored-road.xodr` contains the signed T-intersection approach with one transverse roadMark stop-line object at world y=-11 m and no crosswalk object on the approach. `native/road_source.py` checks the connected lane/road topology, governing STOP sign, absence of crosswalk and marked line; `native/road-source-proof.json` includes wrong-sign, added-crosswalk and missing-line rejections. Physical rendering of the marking and visibility from the four cameras are pending local review.

`native/live_capture.py` lazily imports CARLA only during local acquisition. It authors 600 synchronous 20 Hz ticks, a full-stop versus rolling speed request, four named camera streams, original ego centre/front footprint and speed, frame map, source seal and world restoration. `native/live-capture-check.json` and `native/live-controller-proof.json` pass CPU control and request checks without launching simulation. The inline primary constructions now bundle the road, acquisition, meter and exact controller sources; pinned offline passes both cases again. These are prospective acquisition implementations, not physical recordings or accepted evidence.
