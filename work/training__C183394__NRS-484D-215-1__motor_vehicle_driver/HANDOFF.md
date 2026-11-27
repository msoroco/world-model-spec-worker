# training__C183394__NRS-484D-215-1__motor_vehicle_driver

Status: partial. A source-shaped oncoming-beam distance proof is present; this is not a deployable delivery package.

## 2026-11-23 CPU construction checkpoint

`native/oncoming_beam.py` requests low beam at a measured oncoming centre distance of 500 feet (152.4 m) or less, and high beam beyond it. It measures a 600-frame, 20 Hz trace with opposed headings, vehicle positions, lamp request state, adjacent-shoulder or roadway source, incorporated NRS 484D.100 lighting trigger and oncoming-driver eye-region source. It does not infer emitted ray aim, eye glare or sufficient forward illumination from the lamp API bit.

`native/prove_oncoming_beam.py` passes a 30-second synthetic actor/source fixture and rejects missing frames, broken time join, headings that are not opposed, missing lamp source and missing lighting-trigger source. The source labels and pixels in that fixture are diagnostic only. Proof log: `native/oncoming-beam-proof.log`, SHA-256 `c7bbfffd8936cb973689f6b2e2bd72d3dcd0063dc57164fcb8a6ea2391f7ded0`. Analyzer SHA-256: `1e0b156bafea2e422369ed351e5c7eb5c6c67b08327305377c4d1b7c70cc2703`; proof SHA-256: `1c9fbc3b9eba37a3e51177ec847ac6fcc679519045f1a5abc1d363e86ce63838`.

Next CPU work: bind the actual night or visibility trigger and roadway/shoulder to Native construction, include an opposed driver and source camera eye-region pixels, and implement the exact beam comparison with four cameras, physical-risk fallbacks, offline, compatibility, saved processing, semantic proposals and independent glare/illumination audits. Leave both planned cases unselected until these pass.

Exact law: Whenever a motor vehicle is being operated on the traveled portion of the highway, or shoulder adjacent thereto, during the times specified in NRS 484D.100 [NRS-484D-100-1], the driver shall use a distribution of light, or composite beam, directed high enough and of sufficient intensity to reveal persons and vehicles at a safe distance in advance of the vehicle, subject to the following requirements and limitations: Whenever a driver of a vehicle approaches an oncoming vehicle within 500 feet, the driver shall use a distribution of light, or composite beam, so aimed that the glaring rays are not projected into the eyes of the oncoming driver. The lowermost distribution of light, or composite beam, specified in subsection 2 of NRS 484D.210 [DEF-NRS-484D-210-1-2] shall be deemed to avoid glare at all times, regardless of road contour and loading.

Selected witness scope: Adjacent-shoulder operation with oncoming vehicle. The case plan inventories 4 source topics and drafts one controlled comparison on `oncoming_driver_glare_and_lamp_beam`. Neither case has a Native realization or legal outcome.

The local snapshot lists 0 accepted membership rows. No source-hashed equivalence receipt was available, so no historical recording is claimed reusable.

Remaining gap: Native physical mechanism, exact constructions, offline/compatibility recipes, measured saved fixtures and independent audits are not yet produced for the selected law branch and source alternatives.

Resume: validate source alternatives and exceptions against the exact law; implement the selected comparison and each additional runnable source branch with semantic proposals, four distinct candidate plans, native and camera configuration, offline and compatibility proofs, saved positive/negative audit, and comparison audit. Reuse a historical original only with an exact source-hashed equivalence receipt. Set ready only after all CPU proofs pass.

Physical prerequisites: Establish the incorporated nighttime/headlamp trigger, oncoming driver, 500-foot approach distance, beam selection and actual light aim/glare evidence.

Legal limit: A headlamp API bit alone does not prove glare at the oncoming driver eyes or sufficient forward illumination.

## 2026-11-27 shoulder/oncoming construction and source join

`native/beam_scene.py` now authors C183394 as a two-way OpenDRIVE road with eastbound driving lane -1, adjacent paved shoulder -2 for ego, and opposed driving lane +1 for the distinct oncoming vehicle. Both draft cases share this road, vehicle starts, nominal 30-second/20 Hz duration and four camera mounts including an oncoming eye viewpoint; the requested beam policy differs. `condition_a` requests low beam at or inside measured centre separation 152.4 m (500 feet), while `condition_b` retains high beam as a diagnostic comparison. This is a request contrast, not a legal or glare outcome. Scene proof exercises both cases, exact threshold, missing shoulder lane, missing camera, non-opposed heading and forbidden physical claims; log `native/beam-scene-proof.log` passes.

`native/beam_native.py` makes lazy CARLA OpenDRIVE world, weather, map lane readback, distinct actor spawn, per-tick vehicle controls, lamp request and `get_light_state` readback calls. The CPU fake-Native proof checks these calls, pre/post threshold modes and rejects absent shoulder lane and mismatched lamp readback; `native/beam-native-proof.log` passes. This is only the setup/control seam: 600 original ticks, four synchronized camera encoders, world restoration and sealed Native output still need an executable runner. ClearNight is an authored simulator request, not evidence of the NRS 484D.100 civil-time condition.

`native/saved_beam.py` joins 600 original-shaped beam rows with a 20 Hz four-view frame map, frozen road/shoulder, timing, oncoming actor and eye-region sources. It rejects stale source hashes, missing eye review and broken frame joins. `native/compare_beam.py` independently requires equal road, location, timing, driver and eye sources and exact 600-frame trajectory equality, then tests low-versus-high beam request inside 500 feet; it rejects changed road source. Passing logs are `native/saved-beam-proof.log` and `native/beam-comparison-proof.log`. The test camera files are explicit diagnostic placeholders; no video decode, original pixels or physical success is claimed.

Next CPU work: implement the complete 600-tick/four-camera Native runner and source-bound finalizer, exact inline constructions and original physical/lifecycle auditors, public offline/positive/missing-source compatibility and saved-only processing, canonical semantic proposals, independent delivery audit and final comparison receipts. Reconcile `text-2`: the frozen sources mention but do not provide NRS 484D.210(2) equipment specifications; do not infer that an API low-beam bit is the statutory lowermost distribution. A direct original beam-to-eye review route remains possible without invoking deeming. Keep both draft cases unselected and result partial until the complete CPU chain and scoped strict gate pass.
