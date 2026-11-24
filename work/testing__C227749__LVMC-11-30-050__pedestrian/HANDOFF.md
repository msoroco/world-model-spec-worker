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
