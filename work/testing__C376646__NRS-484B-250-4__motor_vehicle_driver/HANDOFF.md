# C376646 CPU handoff — NRS 484B.250(4)

Status: **ready, delivery_prepared**. Exact scoped strict gate passed on 2026-11-25; see `strict-assignment-check.log`. The frozen accepted-evidence inventory is empty. Exact blind-intersection branch requires installed, uncovered and wholly inoperative vehicular signals, then the marked-line/crosswalk/nearest-view stop hierarchy, cautious motion, and yielding to previously stopped or already present vehicles. No physical or legal outcome is inferred from CPU fixtures.

## Exact cases and comparisons

`case-plan.json` selects five exact suffixes: `stop_line_other_inside`, `crosswalk_other_previously_stopped`, `nearest_view_other_inside`, `stop_line_no_halt` (prohibited rolling-stop attempt), and `stop_line_other_previously_stopped`. `stop_reference_hierarchy` uses the first three; `other_priority_basis` compares the two marked-line cases; `stop_halt_condition` compares the first and no-halt case. All exact IDs include this assignment prefix. The same-reference previously-stopped case was added to prevent a changed stopping reference from confounding the priority comparison.

## CPU construction and proof

`runner.py` is lazy-CARLA Native acquisition. It sources two approaches, complete-body stop-reference distances, all governing entrance heads Off with readback and restoration, and four original cameras. `native_site_contract.py` source-binds the authored OpenDRIVE/site packet and checks the hierarchy. `saved_finalizer.py` and `inoperative_stop_measurements.py` measure original-frame stop, entry, signal and priority observations without making a legal cautiousness cutoff. The authored site packets were adapted from C24757 worker candidates and retain descriptive C24757 map names; they are CPU planning material, not physically reviewed C376646 facts.

All five selected constructions and one delay-ego-release fallback per case pass `runtime.py offline`. All ten candidates pass current-runtime positive and missing-source negative `runtime.py compatibility` through `.runtime-work/c376646-validator/.lake/build/bin/adapterCheck`. All five selected diagnostic attempts pass recorded-only `runtime.py process-saved`. Per-case proof logs and receipts are under `cases/<suffix>/`; `execution-manifest.json` binds their hashes. `prove_physical_fixtures.py` exercises met/not-met/unverified classifier outcomes and capture/owner/saved lifecycle ordering with synthetic sources. `delivery_fixture_proof.py` tests the independent `delivery_audit.py` on full planned duration for all five cases; each negative removes a sealed original and is rejected. `prove_comparisons.py` tests fixed fields, observed differences and same-source rejection. The prior-only priority unit input is explicitly counterfactual; the selected diagnostic itself has both other-priority predicates true and is rejected by `comparison_audit.py`. Actual Native capture must establish other clearance at ego entry for that comparison.

Eight package CPU tests pass in `cpu-tests.log`. Direct current-runtime `execution_manifest.validate`, `semantic_delivery.validate`, `delivery_handoff.validate_case`, and `package_compatibility.check_receipts` pass for the five-case package. The exact strict assignment gate passed. Physical installed/uncovered signal appearance, true blind sight, stop-reference visibility, yielding and camera quality remain later Native checks.

## Resume and limits

The package passed the current-runtime scoped strict assignment check. Preserve its bound sources and proof receipts. Do not use the current synthetic source as physical acceptance. C125751 remains the other unfinished assignment. Retained prior-ready packages have older runtime-bound manifests and are deferred under `AGENT_PROMPT.md` until unfinished packages are complete.

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C376646__NRS-484B-250-4__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C376646__NRS-484B-250-4__motor_vehicle_driver --complete --require-delivery-ready
```

No frozen input, runtime or batch file was edited; no Git command was run.
