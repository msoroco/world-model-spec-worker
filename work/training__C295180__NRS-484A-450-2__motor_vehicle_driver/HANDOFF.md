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
- `native/draft-manifest.json`: `48012b7f92364a5e21a13359b1232fae59b6a94080287f757427fb31eac05ac9`
- `native/condition_a-construction.json`: `1303c9e208bb6de14915237c7f1d9c3c5cc43a0450e6a1d314f7307dabe31239`; passing `native/condition-a-offline.log`: `8645a33fc0b7697036886dd714f95d077a63e2d97bfdc56332872db2df037add`
- `native/condition_b-construction.json`: `611526586b8ed35ecec5ed7c33fa7d28d206cad586c220896718b5aa911e61d2`; passing `native/condition-b-offline.log`: `8338ca85f8fdf3464273034ea9d15f2d03a770779884484d74ce5fb612398091`

Diagnostic rows and negative fixtures are under ignored `.runtime-work/c295180-stop/`; offline materializations are under `.runtime-work/c295180-stop-offline-a/` and `-b/`.

Passed commands:

```text
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C295180__NRS-484A-450-2__motor_vehicle_driver/native/stop_line_request.py prove --output .runtime-work/c295180-stop
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline --manifest work/training__C295180__NRS-484A-450-2__motor_vehicle_driver/native/draft-manifest.json --case training__C295180__NRS-484A-450-2__motor_vehicle_driver__selected_ef239a06__condition_a --output .runtime-work/c295180-stop-offline-a
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline --manifest work/training__C295180__NRS-484A-450-2__motor_vehicle_driver/native/draft-manifest.json --case training__C295180__NRS-484A-450-2__motor_vehicle_driver__selected_ef239a06__condition_b --output .runtime-work/c295180-stop-offline-b
```

## Next CPU work

Implement a connected Native T-intersection with actual sign, marked line, vehicle controller and four synchronized camera streams. Bind original map/sign/actor/frame readback to a saved finalizer; test exact source-bound positive/negative `runtime.py compatibility` and actual `process-saved` fixtures. Author the crosswalk and no-crosswalk/no-line visibility branches with controlled comparisons. Add tested risk-based fallbacks, independent delivery and comparison audits, semantic proposals and execution-manifest bindings. These are worker-owned CPU gaps; the draft does not prove readiness. Run scoped strict only after they pass.
