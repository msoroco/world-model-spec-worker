# NRS-484B-213-2c at C313130

Actor: `motor_vehicle_driver`. Frozen cell: `tunnel` / `travel` / `centerline`.

Exact statutory source: NRS 484B.213(2)(c); with 484B.213(3). The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branches: tunnel approach.

Controlled planning variable: `left_side_occupancy_within_100ft`. Proposed requests: remain right of highway center approaching tunnel with obstructed view; cross to left side within 100 ft of tunnel with obstructed view. These are scene/controller targets, not observed conduct or legal verdicts.

Statutory alternatives and exceptions still to cover or disposition: bridge and viaduct alternatives; one-way-highway exclusion.

Accepted membership: 0 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

Current CPU gap: selected Native construction and offline tests now pass for both cases. Public positive/missing-source, saved-only, semantic, physical/lifecycle, fallback-risk, delivery, and comparison proofs remain unfinished. Physical realization and legal outcome are unverified.

Resume: reconcile every branch against exact text and physical cell; construct Native routes and controllers, mandatory measurement mapping, four distinct plans per selected case, and execute pinned-runtime offline, compatibility, saved-only and independent audit proofs. Mark `ready` only after all CPU proofs pass.

## 2026-11-23 tunnel construction and measurement checkpoint

`.venv-cpu/bin/python runtime.py preflight` passed (`cpu_preflight_passed: true`, simulation not started). The exact statute covers a bridge, viaduct, or tunnel approach with an obstructed view within 100 feet and an exception on a one-way highway. The present frozen cell is a tunnel; bridge and viaduct alternatives remain separately pending. The two current probes are still `planned_only`, with right-side and left-side requested lateral paths on the same two-way tunnel approach.

`measure_tunnel.py` SHA-256 `1cf043b2f08c3a1fd6c8cf38b994781b4c1337332c1eecb4faae1ebb0d6b08fe` measures a complete 600-frame, 20 Hz original-source-shaped trace joined to four cameras. It requires map, portal, road-direction survey, centreline, vehicle-extent, and incoming-lane sight-ray hashes. It reports full-body left-of-centre occupancy within 100 feet of the portal, blocked-ray frames, one-way exception context, and retained sight brackets. Clear-to-limit is treated as a lower bound, and the virtual incoming-lane observer is not equated with actual driver perception. Legal view obstruction and compliance remain unassessed. `tunnel-measurement-contract.json` SHA-256 `f974423ffc95d1101283c5649ad28bb28829aff44322705b67b23251054321ea` maps all eight source observation terms.

`tunnel_scene.py` SHA-256 `a5f14d3ce0f9043808418ddc4efe33abafeb939676d428ae874bc47cea123ece` specifies the two-way OpenDRIVE approach, tunnel and occluder prop requests, four cameras, and a feedback lateral controller. The only deliberate scene difference is the requested lateral target; its controller rejects a late unattained left shift. This is an authored request, not proof that a particular installed blueprint forms a physical tunnel or obstructs the view.

- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python prove_tunnel.py` passed right, left, and one-way context positives plus eight negative source/trace tests. `tunnel-proof.json` SHA-256 `e8df897b1a11ef5abc66273ca1576d5a4ff3a42bad0d63c88e3bccca324c6f57`.
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python prove_tunnel_scene.py` passed two authored-scene positives and six negatives. `tunnel-scene-proof.json` SHA-256 `0b7e004f535261069a3c2b214c8f67a085f28db930942b7809f05fd1502aa458`.

Next CPU work: connect the authored scene, controller, Native source acquisition, and saved measurement in a complete runner; select the first exact case and pass pinned-runtime offline, positive/negative compatibility, and actual process-saved. Then expand comparison, fallbacks, independent audits, proposals, and manifest. Do not promote until the assignment-scoped strict gate passes.

## 2026-11-26 selected construction checkpoint

`build_selected.py` now binds the two exact frozen tunnel cases to source-owned inline Native bundles, including `runner.py`, `native_capture.py`, `finalize.py`, `measure_tunnel.py`, the exact assignment source, and the authored OpenDRIVE road. The Native runner checks assignment/road hashes, case identity, opposed lanes, 600-frame duration, and pinned four-camera names and sizes before importing CARLA. The capture path requests an installed tunnel prop and occluder, records original map direction, portal bounds, four-corner body, source camera/Core joins, and a saved source inventory. A missing prop or physical mismatch fails the attempt; it is not treated as accepted evidence. The current sight-ray value is explicitly unknown pending an installed Native ray capability and original pixel review. It does not prove the obstructed-view condition.

The selected manifest is `selected-probe-manifest.json`, SHA-256 `050b9d5e91f6842742afb80fe1416184ae5ab68979cf14428a3622d73c225d41`. The canonical `selected-measurement-contract.json` binds the statute to `measure_tunnel_approach`, all ten original source files, and a portal-source removal negative. Both exact cases passed `runtime.py offline` with the pinned CPU Python under `.runtime-work/c313130_offline_probe_1_v3` and `.runtime-work/c313130_offline_probe_2_v3`; these were construction and unittest checks with `simulation_started=false`. The prior eight-negative tunnel meter and six-negative scene tests still pass. `runtime.py verify --runtime runtime` passed.

The strict assignment gate was run while `result.json` is truthfully partial and exited 1 at `Preparation acceptance failed: partial/missing packages remain`. Next: create a source-hashed diagnostic fixture recipe that preserves the tunnel geometry, source rows, Core/graph joins, and four camera streams; prove positive and missing-portal public compatibility and recorded-only processing; then complete semantic, physical/lifecycle, delivery and comparison audits, resolve candidate risk, update case-plan, and rerun exact scoped strict on final bytes. Bridge and viaduct are alternative physical structures outside this frozen tunnel cell. The one-way exclusion requires an actual same-direction road survey; the present opposed-lane construction does not activate it. No legal cutoff for obstruction is inferred from a ray proxy.

## 2026-11-26 selected CPU tunnel checkpoint

Primary and fallback offline/public positive and missing-portal negative proofs passed for both exact selected tunnel cases. Both primary recorded-only saved processing proofs passed. Canonical semantic stage chain validates, and independent delivery audit joins 600 saved frames per case while rejecting original acceptance without Native pixels. Original tunnel identity, obstruction and legal outcome remain unverified. Full branch gate still requires source-backed bridge/viaduct and one-way exclusion cases or another truthful resolution.

## 2026-11-26 branch feasibility and exact gate

Independent comparison diagnostic verifies a fixed portal, direction survey and centerline across the two 600-frame cases, with 0 versus 153 left-and-blocked approach frames; negative swapped contrast rejects. See `comparison-audit-proof.json`. Exact scoped strict on truthful partial exits 1 only at `Preparation acceptance failed: partial/missing packages remain`. The current gate also requires all requirement dispositions selected_required with case IDs for ready packages. This pair covers tunnel only. `branch-feasibility-review.json` records that candidate-cells.json has zero motor_vehicle_driver eligible cells; bridge C31940 is allocated full-test and viaduct C349180 has no eligible actor. Supplemental binding is not authorized from frozen inputs. One-way tunnel exclusion is a separate same-cell variant and still needs its controlled pair and CPU proofs. Keep status partial; do not map bridge, viaduct or one-way to these two-way tunnel cases.
