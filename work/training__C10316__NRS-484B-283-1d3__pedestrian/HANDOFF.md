# NRS-484B-283-1d3 at C10316

Actor: `pedestrian`. Frozen cell: `alley` / `travel` / `crosswalk`.

Exact source: NRS 484B.283(1)(d)(3). The full text and source hash are retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branch: Proceeding to cross during flashing indication without countdown.

Controlled variable: `signal state at first highway entry`. Requested pair: enter highway while Walk still shows; enter highway after no-countdown flashing Dont Walk begins. These are construction requests, not measurements or legal verdicts. The baseline is unselected.

Statutory branch dispositions: 2. Review each exception and dependency against the exact text before physical selection. Accepted membership rows: 0; no source-hashed equivalence receipt is available, so reuse is unclaimed.

Blocker: Synthetic timing and contract CPU proofs pass, but executable Native construction, four distinct candidates, offline and compatibility, saved delivery processing and physical realization remain unverified.

Resume: build Native geometry, actor control, cameras and mandatory capture for each runnable branch; prepare four distinct source-preserving constructions per selected case; run exact pinned-runtime offline and compatibility checks, saved positive/negative fixtures and an independent audit. Set `ready` only after those CPU proofs pass.

Source-context review: Signal history must distinguish new entry from lawful Walk entry followed by continuation; deadline is steady indication. Introductory exceptions refer to other statutes and cannot be decided from this clause alone.

## No-countdown timing continuation

`native/no_countdown.py` measures a full 240-frame source trace with Walk, flashing Don't Walk without any countdown, and steady Don't Walk. The authored 7 m crossing road is shared as an exact work-owned geometry proposal; it has not been loaded in Native. Two unselected synthetic sources hold pedestrian position, four-vertex footprint and time identical. They shift the requested start of no-countdown flashing from 2 s to 0.5 s, placing first highway entry at 0.9 s during Walk versus flashing. Full-body clearance is before the common steady transition at 9 s. This measures timing only. It does not prove lawful prior entry, a physical governing display, exception applicability or a legal result.

Six adversarial sources reject missing samples, an unexpected countdown and wrong signal-facing governance. An independent audit recomputes the entry, flashing, clearance and steady events directly from saved rows, checks exact source hashes and confirms identical pedestrian motion. Two case-specific contracts pass the pinned contract validator and saved-value verifier with exact source hashes; their missing-source negatives reject. Source and contract summaries are `no-countdown-summary.json` and `no-countdown-contract-summary.json`. Both cases remain unselected and this assignment remains blocked.

## Exact offline construction continuation

`native/engineering.py` now saves a primary and three distinct unselected alternatives for each controlled case. Fallback1 changes spawn position and pre-roll when an original Native footprint starts too close to the near road edge; fallback2 changes the phase clock source when original display pixels and Native timestamps show more than 25 ms skew; fallback3 moves the display camera closer when independent original-pixel legibility falls below 0.95. The authored synthetic starting footprint has 0.88 m near-edge clearance, but no physical trigger event is measured. The independent engineering audit confirms four distinct knob sets per case, fixed cell/law/actor/12 s/20 Hz/crosswalk/camera contract and only the requested 2 s versus 0.5 s flash-start difference across the controlled pair.

`native/runner.py` now proposes an explicitly invoked, unexecuted Native map/walker/camera capture path with lossless four-camera video, source-frame joins, cleanup and world restoration. It renders Walk/Don't Walk as Native debug text and writes context with signal governance and independent pixel audit explicitly unverified; that debug text cannot establish a qualifying pedestrian signal. Eight exact source-bound bundles were built against the current frozen runtime manifest. All eight pass pinned `runtime.py offline` with four CPU tests each; `audit-draft-offline.py` independently checks source-exact contents, construction and command hashes, fixed capture contract and controlled pairing. Positive/negative package compatibility, saved Core/video processing, statutory exception closure and independent delivery acceptance remain worker-owned. Both cases stay unselected and blocked.

## Current runtime checkpoint (2026-11-15)

Rebuilt `draft-execution-manifest.json` and eight exact unselected construction bundles against batch runtime manifest `ae635d487ae988b67925bacd5ba13210f31224fc6a1ae131d1836a5557ba8714`. `.venv-cpu/bin/python work/training__C10316__NRS-484B-283-1d3__pedestrian/run-draft-offline.py` passed 8/8 primary/fallback offline checks. `.venv-cpu/bin/python work/training__C10316__NRS-484B-283-1d3__pedestrian/audit-draft-offline.py` passed independent source/hash and fixed-contract review. These receipts prove only CPU construction and remain unselected.

Changed the invented fixture velocity label in `probe-package-no-countdown.py` to `synthetic_native_sample`; this label is diagnostic only and must never be used as original Native provenance. Current compatibility command `.venv-cpu/bin/python work/training__C10316__NRS-484B-283-1d3__pedestrian/probe-package-no-countdown.py --suffix controlled_1 --candidate primary` failed with exit 1; `current-compatibility-failure.log` records `TypeError: run() takes from 5 to 6 positional arguments but 7 were given`. The current runtime requires a source-hashed fixture recipe, current measurement contract, all four named source-camera videos, and regeneration of derived channels from retained raw sources. The legacy v1 probe cannot qualify the package.

`.venv-cpu/bin/python worker_check.py --assignment training__C10316__NRS-484B-283-1d3__pedestrian --complete --require-delivery-ready` failed with exit 1; `current-strict-gate.log` records `Preparation acceptance failed: partial/missing packages remain`. Resume CPU work by building the current recipe and selected manifest, proving one primary through current compatibility and process-saved, then testing all fallbacks and the controlled comparison, implementing independent acceptance, and rerunning the strict gate. Original signal governance and physical visibility still require later CARLA acquisition and review.

## Current runtime migration continuation

The earlier API failure was repaired in `probe-package-no-countdown.py`: the unselected diagnostic now invokes the current internal fixture processor, and the decoder was rebuilt from the pinned library at `.runtime-work/c10316-current-decoder`. The two construction bundles now name all four required camera sources: overview, approach, reference_corner and driver_reference. `native/finalize.py` derives five recorded channels from verified trace, evidence, signal samples and frame map after the runtime removes supplied `channels/`. `probe-package-no-countdown.py` labels fixture velocity `synthetic_native_sample` only.

`.venv-cpu/bin/python work/training__C10316__NRS-484B-283-1d3__pedestrian/run-draft-offline.py` passed 8/8; `audit-draft-offline.py` passed. `run-package-no-countdown.py` passed 8/8 current direct fixture positives and missing-source negatives; `audit-package-no-countdown.py` passed. `prove-saved-no-countdown.py` passed two 240-frame synthetic finalizer positives and six corrupt-source negatives; `audit-saved-no-countdown.py` passed. These are retained diagnostics, not public `runtime.py compatibility` or `process-saved` receipts and not selected delivery acceptance. The latter need a source-hashed recipe, selected requirement contract, exact manifest, and independent audits.

The strict assignment gate remains failing while status is partial; `current-strict-gate.log` records the initial readiness failure. Resume the remaining CPU work above before invoking the strict gate. Native pedestrian-signal governance and visible display pixels remain later physical review questions.

## Public compatibility and saved processing checkpoint

`build-diagnostic-recipes.py` inventories two source-hashed textual Native-shaped fixtures (`diagnostic-controlled_1.json` and `diagnostic-controlled_2.json`) with 240 generated graphs and four named source-camera streams each. They retain synthetic provenance. `run-public-compatibility.py` ran `runtime.py compatibility` for both cases and all four candidates: 8/8 pass, each including the public negative missing-source check; receipt paths and hashes are in `public-compatibility-summary.json`. The current decoder was built with `runtime.py build-decoder` from `runtime/pipeline/library`.

`public-saved-controlled-1-primary.log` and `public-saved-controlled-2-primary.log` show successful public `runtime.py process-saved` from the corresponding synthetic compatibility attempts. Their `.runtime-work/c10316-public-saved-controlled-*/v0001/processing.json` receipts report `passed: true`, `missing_evidence: false`, 240 timestamp-joined frames and final decode. The separate `public-saved-negative.log` removes `no-countdown-samples.jsonl`; process-saved exits 1 and writes `.runtime-work/c10316-public-saved-negative-output/v0001/feedback.json` with the missing source and no Native replay requested. This checks software saved processing, not physical acceptance.

The cases remain `draft_not_selected` because the introductory statutory exception/dependency disposition is still pending and the selected delivery manifest, independent delivery and comparison audits, semantic stage proposals, and ordered GPU queue are unfinished. Do not infer readiness from the synthetic receipts. Complete these CPU deliverables and then run `.venv-cpu/bin/python worker_check.py --assignment training__C10316__NRS-484B-283-1d3__pedestrian --complete --require-delivery-ready`.
