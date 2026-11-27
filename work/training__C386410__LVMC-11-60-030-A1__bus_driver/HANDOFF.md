# training__C386410__LVMC-11-60-030-A1__bus_driver

Status: partial. No selected delivery case, accepted recording or legal verdict is claimed.

## Source and scope

LVMC 11.60.030(A)(1): The operator of a bus, other than a tour bus, shall: Not stand or park such vehicle upon any street at any place other than a bus stop, bus stand or the origin or destination point for the route to which such vehicle is assigned which has been designated in accordance with Section 11.60.010 [DEF-LVMC-11-60-010] of this Chapter.

Cell: one_way_road / stop_stand / bus_route_terminus; actor: bus_driver. Frozen witness count: 1. Membership rows: {'full-train': 0}. Membership alone does not prove coverage or reuse. Exact source and topic hashes are in `case-plan.json`.

## Proposed comparison

non-tour route bus stands on one-way street; same assigned route Vary only `bus_standing_location` (category) across ['designated_terminus', 'undesignated_street']. Record standing/parking interval, assigned route and official terminus designation. The definitions are not selected recordings, and requested settings are not measured results.

## New CPU construction and proof

`analysis/branch-expansion.json` quotes seven distinct source branches: bus stop, bus stand, route origin, route destination, standing, parking and tour-bus exclusion. The source text does not list passenger loading zone as an A1 permitted place. The added branches remain unselected until catalog and designation authority review.

`analysis/bus_standing.py` measures a 20 Hz, at least 30-second bus stationary event with original-shaped velocity, brake, driver-presence, occupied-zone and four source-camera frame joins. It checks route identity and a designation-reference hash for named zones, while leaving standing/parking interpretation and legal judgment unresolved. A formatted reference is not verified authority. `analysis/test_bus_standing.py` passes a 600-frame `synthetic_native_sample` diagnostic and rejects missing camera, brake, driver-presence, designation reference, route binding, location readback and short duration. Log SHA-256: `4ef2268b75ebc5b8c3189b52a6fd922f10805657f1872dc073c8a4ec8d0ad838`. Invented fixture motion is not original Native velocity.

The assignment-scoped checkpoint `.venv-cpu/bin/python worker_check.py --assignment training__C386410__LVMC-11-60-030-A1__bus_driver --complete` passes static checks. The strict ready gate has not passed.

## Current Native and saved-source implementation

`geometry.py` authors a one-way driving lane and curb parking lane with a route-terminus map marker. `runner.py` implements two exact location targets (`designated_terminus`, `undesignated_street`) with an approach-then-brake controller, original 20 Hz CARLA velocity/pose/control, `PipelineCapture`, `FrameMap`, four synchronized FFV1 camera streams, world restore and capture seal. It checks the Native parking-lane waypoint at spawn and target. It sets the runtime output-root guard before direct runtime imports. Its CARLA-free `--check` passes; `analysis/runner-check.log` SHA-256 is `759c52fd6d9556aee0be4da087c44984f2a4415a60c411bc4e1fcf7f2dd5975c`. This is authored acquisition code, not evidence that CARLA motion or camera framing succeeded.

`analysis/bus_standing.py::measure_saved` joins original bus history, Native frame IDs, four camera file bytes and the saved location-reference hash. It requires an original Native seal for original mode, and explicitly leaves official designation, vehicle class, route assignment, driver presence and legal judgment unverified. `analysis/test_saved_source.py` passes a synthetic positive plus changed designation, missing camera and frame-identity negatives; `analysis/saved-source-cpu.log` SHA-256 is `428099b1924c0a124d35db2228b8e7d117afe9c8d1706de44ff3087c29d5264f`.

`comparison_audit.py` checks exact location difference and fixed bus class, route, street, controller, weather and capture profile; `analysis/test_comparison.py` passes a positive and rejects fixed-weather change and a missing camera. Log SHA-256: `6087ccc076aa1d385a6586fab523f5f7f22be09bf6d9b0ef9735a4fdd62a5cb9`. `delivery_audit.py` implements original Native seal, lifecycle, saved-processing, source review, all-camera decode and Core join checks. Its CPU selftest inventories six checks and rejects synthetic acquisition, with positive inventory log `8df2d23f0d374db0fde7185ab7a6f1359cfb617f75e5c9c54ce462ba694105a5` and rejection log `5f8c051389b17f3de516c8c7885d56faad76a96841f4529f0670153a820c2290`. These tests do not establish an original-source delivery success.

## Remaining CPU work

`build_primary.py`, `bind_compatibility.py` and `build_diagnostic.py` bind two exact source-hashed primary bundles, measurement contracts and small textual diagnostic recipes. Both exact cases pass `runtime.py offline` and `runtime.py compatibility`, including the missing `bus-context.json` negative, Native validation, Core conversion, Lean decode, render and full video decode. Receipts and logs are under `proofs/designated_terminus/` and `proofs/undesignated_street/`, bound in `execution-manifest.json`. The pinned decoder was built under `.runtime-work/c386410-decoder`. Both exact cases also pass recorded-only `runtime.py process-saved` on independently materialized synthetic attempts; the bound logs and receipts are in their proof directories. `build_physical.py` passes complete, incomplete, missing-evidence and lifecycle-order diagnostics against the pinned physical checker, with source-hashed receipts. All of these are software fixtures, not original Native or legal proof.

`case-plan.json` lists eight distinct planned case variants across seven statutory comparisons, reusing `undesignated_street` instead of duplicating its recording. Six additional variants need exact Native scenes/controllers, diagnostic recipes and full proof chains. The current comparison audit executes only location alternatives; add standing/parking and tour-bus comparisons while preserving the frozen bus-driver role. Add risk-based fallback for the concrete bus stopping risk, all canonical semantic proposals and original-only delivery positives/negatives for every exact case. Review compatible catalog cells for any genuinely incompatible branch. `DEF-LVMC-11-60-010` and official route designation were not found in supplied assignment or coverage inputs; a map marker and formatted hash are not authority. Preserve this dependency in later original-source review. The scoped static gate passes; strict readiness remains partial because CPU deliverables are unfinished. Original motion, pixels, administrative designation and legal interpretation require later review.
