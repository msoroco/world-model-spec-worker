# training__C104393__NRS-484B-413-2__motor_vehicle_driver

Status: partial. No selected delivery case, accepted recording or legal verdict is claimed. Prior blocker text below is historical; the current-runtime checkpoint follows it.

## Source and scope

NRS 484B.413(2): A signal of intention to turn right or left, or otherwise turn a vehicle from a direct course, shall be given continuously during not less than the last 100 feet traveled in a business or residential district and not less than the last 300 feet traveled in any other area prior to changing the course of a vehicle. This rule shall be observed, regardless of the weather.

Cell: hill_crest / turn / other_vehicle; actor: motor_vehicle_driver. Frozen witness count: 3. Membership rows: {'demo-train': 0, 'full-train': 0}. Membership alone does not prove coverage or reuse. Exact source and topic hashes are in `case-plan.json`.

## Proposed comparison

hold district category fixed within each boundary triple; same turn or lane change; weather sampled separately Vary only `continuous_signal_distance_before_course_change` (ft) across [90, 100, 110, 290, 300, 310]. Integrate path distance along actual trajectory while turn indication remains continuous immediately before measured course change. The definitions are not selected recordings, and requested settings are not measured results.

## Blockers and resumption

Executable Native construction and four candidate offline/compatibility proofs absent; saved audit and comparison proof absent. Business/residential 100 ft and other-area 300 ft need separate comparable triples; indicator API and actual course change may diverge. Resolve exact statutory branches and external authority from the frozen law and cited sources. Build semantic stages, Native construction, primary plus three truly distinct fallbacks per selected case, mandatory synchronized capture and Core mapping; run exact offline, positive/negative compatibility, saved-only and independent comparison audits. Recheck physical cause and camera evidence in CARLA later. Set `ready` / `delivery_prepared` only after worker CPU proofs pass.

## Current-runtime CPU checkpoint (update 016)

The frozen assignment text was reread. This C104393 draft covers the six `any_other_area` signal-distance probes (90, 100, 110, 290, 300 and 310 ft); it does not claim the 100-foot business/residential branch. No accepted evidence is listed in this assignment input. `build-draft-candidates.py` now rebuilds 24 exact unselected constructions with the current four named camera sources (`overview`, `approach`, `reference_corner`, `driver_reference`). `native/finalize.py` derives eight adapter channels from retained Native samples, trace speed and frame map; the diagnostic does not supply `channels/`. Synthetic speed uses `synthetic_native_sample`, never original CARLA velocity. The 24 pinned offline checks pass in `current-offline-all.log` and `draft-offline-summary.json`.

The 300-foot primary plus three fallbacks pass current strict recipe compatibility, including selected measurement verification, missing-`native_samples.jsonl` negatives, Native validation, Core/Lean decode, four-camera composition and full video decode. `current-v2-300-summary.json` binds the four exact receipts and `current-v2-300-audit.log` independently verifies their construction, contract, source recipe and negative log hashes. Fallback1 changes the authored turn radius and therefore requires its own matching diagnostic recipe; `diagnostic-fallback1-manifest.json` supplies it for this proof. The earlier primary-map recipe failure is preserved in `current-v2-300-fallback1.log` and was repaired by `current-v2-300-fallback1-specific.log`. These remain unselected synthetic proofs.

The 300-foot primary passes actual `runtime.py process-saved` in `current-saved-processing-receipt.json` with `missing_evidence: false` and no physical/legal acceptance claim. Removing `native_samples.jsonl` yields the exact error in `current-saved-negative-feedback.json`. Generated media and Core remain under ignored `.runtime-work/`.

Resume by authoring current recipe and saved-only proofs for the other five exact cases, then selecting delivery cases with independent delivery acceptance and comparison audits, semantic/queue bindings and the scoped strict gate. Physical CARLA motion, observed indicator, source map classification, actual course-change onset, weather, camera pixels and fallback triggers still require later original capture. Missing CPU implementation and selection are unfinished work, so the assignment is partial, not externally blocked.

## 290-foot current-runtime checkpoint (update 016 continuation)

The 290-foot primary plus three distinct fallbacks now pass current strict recipe compatibility in `current-v2-290-summary.json`. The independent `current-v2-290-audit.log` verifies construction, source recipe, measurement contract, selected 290-foot measurement, positive and missing-native-source logs, and fallback map separation. Fallback1 uses its own matching turn-radius recipe and `diagnostic-290-fallback1-manifest.json`. All 24 exact unselected constructions again pass pinned offline in `current-offline-all.log`. The 300-foot independent audit still passes after the manifest update.

The 290-foot primary also passes actual saved-only processing in `current-290-saved-processing-receipt.json` (`missing_evidence: false`, `physical_acceptance_claimed: false`, `legal_acceptance_claimed: false`). Removing `native_samples.jsonl` produces the expected `Missing required source: native_samples.jsonl` failure in `current-290-saved-negative-feedback.json`. Generated media and Core remain under ignored `.runtime-work/`.

Four other planned distances (90, 100, 110 and 310 ft) still need current strict recipe and saved-only proofs. No selected delivery manifest or accepted recording is claimed; comparison audits and queue bindings remain. The 100-foot business/residential branch is outside the six-case any-other-area draft. Physical CARLA behavior and pixels remain unverified. Status stays `partial`.
