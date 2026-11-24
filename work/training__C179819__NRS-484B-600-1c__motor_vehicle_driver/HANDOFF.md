# training__C179819__NRS-484B-600-1c__motor_vehicle_driver

Status: partial. No new selected delivery case, current-runtime accepted recording or legal verdict is claimed.

## Source and scope

NRS 484B.600(1)(c): It is unlawful for any person to drive or operate a vehicle of any kind or character at: A rate of speed greater than that posted by a public authority for the particular portion of highway being traversed.

Cell: paved_road / travel / speed_limit_sign; actor: motor_vehicle_driver. Frozen witness count: 3. Membership rows: {'demo-train': 9, 'full-train': 9}. Membership alone does not prove coverage or reuse. Exact source and topic hashes are in `case-plan.json`.

## Proposed comparison

same authority-posted limit and governed road portion; speed profile only varies Vary only `measured_speed_vs_posted_limit` (mph) across ['below_posted', 'at_posted', 'above_posted']. Record sign, authority and governed extent, actual speed time series and sign passage. The definitions are not selected recordings, and requested settings are not measured results.

## Blockers and resumption

The frozen review context describes three accepted v3 speed recordings in both demo-train and full-train, with one independent three-pair comparison receipt. V1 and v2 are failed or superseded. `evidence-review.json` records each frozen membership row and source hash. These are historical records, not a current-runtime proof. This export has no `inputs/<assignment>/evidence.json`, so the no-new-capture ready path cannot pass its source-inventory contract.

The new `audit_speed_comparison.py` checks saved trace and context hashes, full-frame and duration minima, governed-zone occupancy, measured speed conversion, three distinct traces, and fixed posting/authority/extent context across the planned comparison. The five synthetic CPU tests passed; `speed-comparison-cpu-proof.json` binds the code, log and frozen review hashes. This is diagnostic software proof only. It does not audit the original recordings, source-camera pixels, physical authority, or legal compliance.

Executable Native construction and four candidate offline/compatibility proofs remain absent; saved-only processing and source-bound original comparison proof remain absent. Numeric posted value is world setup, not a judgment standard; the near-at point is intentionally below 30 mph and is not legal equality. Resolve exact statutory branches and authority from frozen sources. Build semantic stages, Native construction, primary plus three truly distinct fallbacks per selected case, synchronized four-camera capture and Core mapping; run exact offline, positive/negative compatibility, saved-only and independent comparison audits. Recheck physical cause and camera evidence in CARLA later. Set `ready` / `delivery_prepared` only after worker CPU proofs and assignment-scoped strict check pass.
