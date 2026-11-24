# testing__C227749__LVMC-11-30-050__pedestrian

Status: **partial**. Exact law LVMC 11.30.050; frozen accepted evidence is empty. Conditional witness and authored geometry do not establish a physical crossing or legal verdict.

## Built exact CPU package

Five case scenes and constructions cover outside right angle, outside shortest endpoint, outside neither, outside endpoint detour, and inside crosswalk oblique. Three controlled comparisons are in `case-plan.json`. The source-hashed `candidate-crossing.xodr` is a straight authored road; it has no verified curb or crosswalk physical surface and does not establish jurisdiction. `proposals/cases.json` contains draft case semantics.

The Native runner is bundled for every case. It has a lazy walker controller and readback, 400 planned 20 Hz frames, original walker bounding-box history, four synchronized RGB cameras encoded losslessly, a pipeline graph/trace recorder, frame joins, source hashes, capture seal and world restoration. `runner.py --check` is CPU only. The saved-only `analysis.py`, `saved_measurement.py`, `delivery_audit.py`, and `comparison_audit.py` preserve source identity, reject missing source/frames/joins, and report route geometry without a legal classification. Native CARLA execution has not been observed.

## Proof receipts

`proof-index.json` binds all five current construction and fixture recipe hashes to retained logs and compatibility receipts. All five current bundles passed pinned exact `runtime.py offline` and pinned `runtime.py compatibility`, including positive analysis and `negative_case_source`, final video decode, Lean decoder, four camera sources and Native result validation. The compatibility source is explicitly a **synthetic diagnostic fixture** and proves software shape only. The five `cases/*/primary-compatibility.json` receipts are retained.

- `proof-index.json` SHA256 `1d3f7149590ba6e1a8ff25726dc28b22430725e73fa19817656d7881695f7fb0`.
- `cpu-tests.log`: 23 tests passed; SHA256 `741603f82362c489e79b6e1b397bb17c004458697a12c354ceb5a6bab3fecda2`.
- `geometry-proof.log`: five authored geometry targets passed; SHA256 `586843cf048d190719b70cfdd5830694557a624877563396566afae931719393`.
- `saved-measurement-proof.log`: five 201-frame synthetic positive and missing-source negative cases passed; SHA256 `d2b812a344060e8b7c4fb1f1646f781d440e70e1f0c8f320450f6c9e909ddf4c`.
- Exact assignment `worker_check.py --complete` passed; SHA256 `09d44601237b8b7333c5b6848edb441b03b12cbcca3962a82873a211db607cf1`.
- Exact assignment `worker_check.py --complete --require-delivery-ready` failed because status remains partial; SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`.


## 2026-11-23 independent saved media decode

`saved_media_audit.py` now rechecks source hashes and exact frame joins, probes each named camera against the 20 Hz four-camera capture profile, and fully decodes each frame with FFmpeg frame hashes. Original Native sources additionally require lossless FFV1. `prove_saved_media.py` ran this audit on all five retained exact synthetic compatibility attempts: four named cameras and five decoded frames per case. A source-hashed shortened overview video was rejected against the original join count. This is software media integrity only; physical visibility remains unconfirmed. `saved-media-proof.log` SHA256 `71b9e91cb05c66184e4d79349490f16607fbbdf7e0fd5704eddc807a331efaf5`.

## Remaining worker CPU construction and source proof

1. Obtain and hash source packets for actual curb endpoints, roadway, crosswalk presence/bounds, public-way jurisdiction and relevant control context. Reconcile all five case scenes with those facts; authored OpenDRIVE and diagnostic fixture do not supply them.
2. Build physical crosswalk surface/metadata where needed and add explicit source/readback checks to the Native runner. Exercise walker spawn/control, map reserialization, original graph capture, four-camera visibility and world restoration against a real caller-owned CARLA endpoint. Retain a failed attempt when any readback or capture check fails.
3. Complete canonical semantic stage proposals, at most two tested engineering fallbacks per risk, exact execution manifest, and independent full saved video/body/context/comparison audits against actual Native attempts. Promote only after exact strict delivery gate passes.

Remaining GPU/Native checks are actual route realization, pedestrian body/curb crossing, camera visibility and full physical completion. No present result claims them.

## 2026-11-23 Native body and crosswalk geometry checkpoint

- `physical_geometry_audit.py` independently requires 400 consecutive original Native walker body frames at 20 Hz, stable actor identity, four actual body corners, bounded center and full body polygon/crosswalk intersection. An outside-crosswalk attempt is rejected if its body overlaps a sourced crosswalk even when the centerline stays outside. Inside requires observed body overlap. It reports measured frames without a legal classification or visibility claim. SHA-256 `132639442c8a1a2ee36fd70df427027dae0bd873c3e9549a4300a2c2d7272228`.
- `saved_measurement.py` now invokes the body audit for original Native attempts; synthetic fixtures retain their existing diagnostic report shape and do not count as physical proof. SHA-256 `e53dcc20c8dadad8169ffec2d9000535d06397be95e59d8ad1dd30196a770a53`.
- Pinned preflight passed. Focused suite passed 27 tests (`cpu-tests.log` SHA-256 `2b658fea6a9e637e1a0c99ca47963714f45a59f2d198b37642cd4ab587f37e84`); five saved synthetic positive/negative proofs passed (`saved-measurement-proof.log` SHA-256 `d2b812a344060e8b7c4fb1f1646f781d440e70e1f0c8f320450f6c9e909ddf4c`). Scoped static complete passed (`assignment-check.log` SHA-256 `09d44601237b8b7333c5b6848edb441b03b12cbcca3962a82873a211db607cf1`).
- Exact scoped strict gate exited 1 on truthful partial status; `assignment-strict-check.log` SHA-256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`. Next CPU work: hash/source-review actual curb, crosswalk, roadway and jurisdiction; add physical surface/readback to the Native runner; complete semantic proposals, risk-triggered fallbacks, execution manifest and independent full saved delivery/comparison receipts.

## 2026-11-23 Native crosswalk readback guard

`native_crosswalk_readback.py` compares the authored polygon vertices with `Map.get_crosswalks()` vertices from the loaded Native map and binds the serialized loaded OpenDRIVE hash to the exact scene. It rejects absent/shifted vertices, a different loaded map, malformed coordinates and an engineering tolerance outside 0–1 m. The returned packet explicitly leaves curb identity, paint visibility, municipal jurisdiction and legal route classification unresolved. This guard is currently independent and must be integrated into rebuilt exact runner bundles before Native execution; the five existing offline/compatibility receipts remain bound to their previous construction hashes. The present candidate map has not supplied a positive physical crosswalk readback.

Pinned preflight exit 0: `cpu-preflight-nov23.log` SHA256 b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63. Focused suite exit 0, 30 tests: `cpu-tests-nov23.log` SHA256 ee6dee04675677e21c07c79323f3f4cbf6c819471af99b5784e23b4ffccd1bf7. The new map tests use an injected fake Native map; they prove rejection behavior, not the candidate map's physical crosswalk.

Next CPU steps: integrate this guard in runner, regenerate five construction hashes and affected offline/compatibility receipts, then source-review curb and municipal-context packets and finish semantic proposals, risk-triggered fallbacks and delivery manifest.
Scoped static check exit 0: `cpu-static-nov23.log` SHA256 09d44601237b8b7333c5b6848edb441b03b12cbcca3962a82873a211db607cf1.
Scoped strict check exit 1: `cpu-strict-nov23.log` SHA256 3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a.

## 2026-11-23 regenerated exact bundles and compatibility

Integrated `audit_crosswalk_map` in `runner.py` immediately after loaded Native world creation, before walker spawn. Its result is retained as `native-crosswalk-readback.json` in the original acquisition seal. `build_offline.py` now bundles the guard and `physical_geometry_audit.py`; the latter repaired a missing import discovered during the first regenerated compatibility run. The earlier receipts are superseded by the new five construction hashes in `proof-index.json` SHA256 b8fb543d0083fc5a93e15c7c5ec92609343abb1e1ddd197ff4bfc963dfcc6faf.

All five new exact bundles passed `.venv-cpu/bin/python runtime.py offline --manifest work/testing__C227749__LVMC-11-30-050__pedestrian/draft-offline-manifest.json --case CASE --output .runtime-work/p08-c227749-nov23/offline-v3-NAME --python $PWD/.venv-cpu/bin/python`. All five also passed `.venv-cpu/bin/python runtime.py compatibility --manifest work/testing__C227749__LVMC-11-30-050__pedestrian/draft-offline-manifest.json --case CASE --output .runtime-work/p08-c227749-nov23/compat-v4-NAME --library runtime/library --validator .runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck`. Each positive/negative receipt and analysis/negative log was copied into its exact `cases/NAME/` directory. `proof-index.json` binds current construction, recipe and receipt hashes. These are synthetic software proofs; the current authored candidate has no verified Native crosswalk or curb physical source.

Focused suite passed 30 tests, `cpu-tests-nov23.log` SHA256 583a724a90bbccb6ddd8640c8ecfae1ef0a35b23904feffc2a897315714972fe. Pinned preflight passed, `cpu-preflight-nov23.log` SHA256 b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63.
After bundle regeneration, exact scoped static gate exited 0 (`cpu-static-nov23.log` SHA256 09d44601237b8b7333c5b6848edb441b03b12cbcca3962a82873a211db607cf1); exact scoped strict gate exited 1 on truthful partial (`cpu-strict-nov23.log` SHA256 3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a). Current remaining CPU work is source-confirmed actual curb/crosswalk/jurisdiction/control context, canonical semantic proposals, justified fallbacks and full delivery manifest/audits.

## 2026-11-23 saved processing and diagnostic delivery audit

All five current synthetic compatibility attempts passed `runtime.py process-saved` with timestamp joins and final video decode. `saved_delivery_gate.py` independently rechecked their exact construction/result hashes, source preservation, 310 original file hashes, joined frame counts, and absence of physical or legal acceptance claims. `prove_saved_delivery.py` wrote `saved-delivery-diagnostic.json` SHA256 ff481eefc30355d861d80e992afcae7479c90a86b36fa244669c8c639a0299f4. Every case is `software_diagnostic_complete` with five frames; physical acceptance remains false and legal verdict unresolved. Focused suite passed 41 tests, `cpu-tests-nov23.log` SHA256 3bb40d9e0e115e3cd77aeec9dc7e9faf052b2c1455dd2163a5f7c4b1f8427673; its new negatives reject source tampering, missing evidence, frame mismatch, stale results and unsupported acceptance claims.

The next CPU work is a canonical semantic proposal and exact source-backed delivery manifest. Original Native crossing, 400-frame body history, curb/crosswalk/jurisdiction readbacks and physical/legal review remain unproved.
Scoped static gate exit 0: `cpu-static-nov23.log` SHA256 09d44601237b8b7333c5b6848edb441b03b12cbcca3962a82873a211db607cf1. Exact scoped strict gate exit 1 on truthful partial: `cpu-strict-nov23.log` SHA256 3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a.

## 2026-11-23 independent saved case comparisons

`saved_comparison_audit.py` checked all three planned comparison pairs against current exact scene/config bytes and saved diagnostic results. It rejected changes to fixed capture conditions and unisolated crosswalk differences in tests. All three comparison pairs retained the same authored curbs, map hash, pedestrian actor, 20 Hz/20 s capture and cameras, while isolating their declared route or crosswalk variable. `saved-comparison-diagnostic.json` SHA256 b336cadc1ed9f8c10fa01c8c321bdd0ac8f8cdc0bf7b53770d3f38f7671083ca; `saved-comparison-proof.log` SHA256 de0421f2bac5f2efc296387e3558e74e9408babe2b191f39866bd600d7204a3e. Focused suite passed 41 tests, `cpu-tests-nov23.log` SHA256 3bb40d9e0e115e3cd77aeec9dc7e9faf052b2c1455dd2163a5f7c4b1f8427673. These are synthetic software comparisons, with no physical acceptance or legal judgment.
Scoped static gate exit 0: `cpu-static-nov23.log` SHA256 09d44601237b8b7333c5b6848edb441b03b12cbcca3962a82873a211db607cf1. Exact scoped strict gate exit 1 on truthful partial: `cpu-strict-nov23.log` SHA256 3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a.

## 2026-11-24 reviewed-site Native source gate and refreshed CPU proofs

`reviewed_site.py` now requires a separately reviewed original site packet and SHA-bound source documents for starting/opposite curbs, crosswalk boundaries, roadway/public use and governing control. The Native runner rejects missing, diagnostic, wrong-map, wrong-case, changed-geometry, escaped-path or changed-hash packets before CARLA acquisition, then seals the packet and documents with the attempt. The four new focused tests use synthetic source records solely to test rejection, not to claim an original site review. Actual original packets remain absent.

All five rebuilt selected primary constructions passed current-runtime `runtime.py offline` and positive/missing-source `runtime.py compatibility` (case-specific logs `cpu-offline-nov24-*.log`, `cpu-compat-nov24-*.log`). Five new `runtime.py process-saved` diagnostic attempts passed, then the independent source-hash delivery and three-pair comparison audits passed against the new exact construction hashes. `proof-index.json` SHA256 5e1c96a2b1a14a3dc8dc198c972038f257acc8b15a35c844650c56198dbb0d69; 45 focused tests passed (`cpu-tests-nov24.log`). Scoped static gate exits 0 (`cpu-static-nov24.log`); exact strict gate exits 1 on truthful partial status (`cpu-strict-nov24.log`).

Next CPU work: source-review a real Native map with a realizable crosswalk and source-backed curb, roadway and municipal jurisdiction facts; replace the unverified candidate/map binding only from those originals; complete canonical semantic stage proposals, risk-triggered fallbacks and a delivery manifest. The current authored OpenDRIVE lacks a verified crosswalk. Actual walker motion and camera coverage remain later Native checks.
