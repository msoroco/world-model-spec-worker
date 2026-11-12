# heldout__C111294__NRS-484D-205-4__motor_vehicle_driver: CPU preparation checkpoint

## 2026-11-11 original lamp and forward-motion measurement

`backup_lamp_measurement.py` now joins original equipment inventory, body
heading/velocity and Native backup-lamp state readbacks with the frame map for
every tick. It reports forward-motion frames and their overlap with the Native
lamp-state bit. It keeps actual emitted pixels and legal outcome unknown until
a separate source-bound rear-view pixel review exists; a state bit alone does
not prove lighting. No transition allowance is inferred from the planning
summary because the exact statute states the forward-motion condition without
one.

Two CPU tests pass for reverse/forward intervals, Native state overlap,
wrong-actor rejection and missing state rejection. Run `.venv-cpu/bin/python
-m unittest discover -s work/heldout__C111294__NRS-484D-205-4__motor_vehicle_driver/tests -v`;
`cpu-tests.log` SHA-256 is
`2ffabec6609e2b2a3ad26ec07878eb1eb7ba6cf97f7709cd2104b6ebd9d49209`.
Scoped complete passes; scoped strict rejects the truthful partial status.
Next, construct the first exact Native forward-motion case and four-camera
source capture, verify actual backup-lamp equipment capability and source
pixels, then prove exact offline, positive/negative compatibility and saved
processing. Preserve the conditional review's pending source and human audits.

## Frozen scope and source

- Law: NRS 484D.205(4) — Any motor vehicle may be equipped with one or more backup lamps either separately or in combination with other lamps. Backup lamps shall not be lighted when the vehicle is in forward motion.
- Cell/actor: C111294 / motor_vehicle_driver; layout `intersection`, maneuver `travel`, control `other_vehicle`.
- Exact input: `inputs/heldout__C111294__NRS-484D-205-4__motor_vehicle_driver/assignment.json` (SHA256 `46b011125b6f55d2eaa0ba343af53f19b8fe307e0f44de6dae25b38ff6a0481c`).
- Witness: `inputs/heldout__C111294__NRS-484D-205-4__motor_vehicle_driver/witnesses.json`; conditional witness is a planning lead, not physical or legal acceptance.
- Existing accepted recordings: 0; no source-backed reuse is claimed.
- Source observation terms: sig.reverse_lamp, kin.velocity, drv.backing, kin.heading, kin.speed.

## Required source and construction review

1. Construct the intersection route and a separate other vehicle's position, motion, priority and purpose.
2. Establish qualifying motor-vehicle classification and installed backup-lamp inventory.
3. Retain actual forward-motion intervals with synchronized heading, velocity, speed and lamp illumination.

## Current result and exact next CPU actions

Status is **partial**. No executable case, fallback, source measurement, or saved-processing receipt exists yet, and no physical outcome is asserted. Read `inputs/heldout__C111294__NRS-484D-205-4__motor_vehicle_driver/assignment.json`, `evidence.json`, `witnesses.json` and the exact law in `inputs/coverage/branch-sources.json`. Decompose alternatives and exceptions; map them to controlled exact cases and comparisons, using an additional compatible cell only if the fixed cell cannot carry a branch. Build one primary exact case end-to-end using the pinned runtime, then build every other case and three distinct tested fallback constructions per selected case. Test finalizers against retained raw sources (including all four named cameras), exact offline and positive/negative compatibility, saved-only processing, and independent delivery/comparison audits. Add canonical semantic proposals and hash all current receipts. Do not treat fixture media as physical evidence.

Resume gate: `.venv-cpu/bin/python worker_check.py --assignment heldout__C111294__NRS-484D-205-4__motor_vehicle_driver --complete --require-delivery-ready`.

The external CARLA run is a later operator action; remaining CPU omissions above are not external blockers. No GPU command has been executed.

## Conditional review and planned comparisons

The witness in `inputs/heldout__C111294__NRS-484D-205-4__motor_vehicle_driver/witnesses.json` cites `inputs/planning/law-split-demo-overlap-v2/reviews/NRS-484D-205-4.json` with source SHA256 `9bfc9ded14ad3093469812fd1a6a49acc63f5585df51153c665684cbb9efebe2`. Its verdict is `accept_conditional`; `source_audit_status` is `pending`, `human_review_status` is `unreviewed`, and `physical_feasibility` is `unverified`. The review says the separate other vehicle's mere presence supplies no activation evidence. These conditions are retained, and no physical fact or statutory outcome is claimed from this review.

`case-plan.json` now plans the exact cases `heldout__C111294__NRS-484D-205-4__motor_vehicle_driver__no_backup_lamp_installed`, `heldout__C111294__NRS-484D-205-4__motor_vehicle_driver__forward_backup_lamp_off`, and `heldout__C111294__NRS-484D-205-4__motor_vehicle_driver__forward_backup_lamp_on`. The first comparison varies optional equipment presence; the second varies lamp illumination while holding the forward route and other-vehicle context fixed. Every case requires actual blueprint equipment inventory, Native light state, synchronized forward heading/velocity, and full-decoded rear-facing pixels. These are planned only; no CARLA illumination capability or original footage has been verified.

## 2026-11-11 source-bound pixel audit continuation

`lamp_pixel_audit.py` binds an independent per-forward-frame rear-lamp pixel review to all four retained original camera SHA-256 values and a full-decode receipt with exact frame counts. It rejects stale camera bytes, omitted forward frames, incomplete decode, absent rear-detail view and visible emission conflicting with an empty equipment inventory. This is a CPU audit implementation; tests use small placeholder camera bytes and do not establish actual emitted pixels, Native visibility, physical completion or a legal result. The review must be filled from actual original footage after capture. Six tests pass in `cpu-tests.log` (SHA-256 `aed3df723b14e85d32af1842bd436fc76a20438dd0e1f5a9542dfdf71c40e50b`).

The current `.venv-cpu/bin/python runtime.py preflight` passes with the pinned environment. Exact next CPU work is a CARLA-lazy intersection runner retaining equipment, motion, lamp state and four cameras, then an exact first-case offline/positive-negative compatibility/saved-processing proof. Expand the other two exact cases, three distinct fallbacks each, semantic proposals and independent comparison/delivery audits. Keep the conditional source-hashed review pending. Scoped strict gate must pass before changing `partial`.

## 2026-11-11 original Native recorder continuation

`lamp_source_capture.py` now retains equipment identity and synchronized original-tick heading, velocity, full Native light-state integer and reverse-light-mask readback. Its CPU fake exercises a state transition and rejects missing/unordered frames and wrong equipment actor. It does not infer installed hardware from the Native state; the equipment inventory remains a separately sourced requirement. Eight unit tests pass in `cpu-tests.log` (SHA-256 `253556d25a873cb6669dd0b532d81241607414acde581ddf08fc9cc0a11a2964`). Scoped complete passed; scoped strict still rejects partial in `strict-gate.log` (SHA-256 `89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292`). Next CPU action is integrating the recorder with the exact CARLA-lazy intersection runner and four-camera capture, then the selected saved-only finalizer and first exact offline/compatibility/saved proofs.

The source-recorder test now passes its generated original motion, equipment and canonical frame map directly into `backup_lamp_measurement.measure`, preserving the forward/lamp-state frame join. Current eight-test log SHA-256 is `b952e50d61616e175c97345fbccf93f9f5611c97db3879eefb8ae27719f4f4ae`.

## 2026-11-12 restored CPU environment and executable construction checkpoint

Pinned `.venv-cpu/bin/python runtime.py preflight` passes; `worker_check.py --updates` reports update version 0 with no paused assignments. `lamp_scene.py` now discovers one source-map junction with perpendicular through lanes, spawns the subject and a separately controlled other vehicle, requires an independently inspected blueprint backup-lamp inventory, and sets/reads the Native reverse-light bit without discarding other bits. `runner.py` uses it for 160 original ticks at 20 Hz; `lamp_camera_capture.py` configures four named unscaled RGB streams including rear quarter and rear-detail views. It retains original equipment, subject heading/velocity/light-state, separate other-vehicle identity and motion, frame map, context and provenance. `lamp_finalizer.py` rebuilds channels from those originals and rejects missing, changed or unjoined sources. `lamp_comparison_audit.py` checks the fixed intersection/camera/controller context and the planned equipment or Native-light-state difference. The existing `lamp_pixel_audit.py` remains a separate original-camera/full-decode review; a Native state bit still does not establish emitted pixels.

`cpu-tests.log` has 17 passing tests (SHA-256 to be read from `result.json`). `execution-manifest.json` contains inline constructions for exact cases `__no_backup_lamp_installed`, `__forward_backup_lamp_off`, and `__forward_backup_lamp_on`, each with fallback1 (approach predecessor at 40 m), fallback2 (through exit successor at 30 m), and fallback3 (speed controller gain 0.16). All 12 exact `runtime.py offline` invocations pass; their commands, construction hashes and log hashes are bound in the manifest. These are CPU checks only. They do not show that CARLA assets have removable or emissive backup lamps, that the map yields one unambiguous pair, that camera views show the lamps, or that vehicles complete the route. The asset-inspection source named in config is intentionally not fabricated; the local capture must supply a source-backed inventory for the selected asset.

The first positive/negative compatibility command (`.venv-cpu/bin/python runtime.py compatibility --manifest work/heldout__C111294__NRS-484D-205-4__motor_vehicle_driver/execution-manifest.json --case heldout__C111294__NRS-484D-205-4__motor_vehicle_driver__forward_backup_lamp_off --output .runtime-work/c111294-off-primary-compat-v1 --library runtime/library --validator .runtime-work/fire-decoder/.lake/build/bin/adapterCheck`) failed at `package_compatibility.py:76` with `KeyError: 'measurement_contract'`; retained in `primary-compatibility.log`. The pinned dependency/tool preflight is no longer a blocker. Next CPU action: author case-plan requirement dispositions and a measurement contract whose source inputs match `lamp_finalizer.analyze`, bind that contract to the first manifest case, and rerun positive/negative compatibility followed by saved processing. Then adapt the diagnostic recipe and those proofs for the other exact cases and all fallbacks, author canonical proposals and independent delivery audit, and run the scoped strict gate. Review separate versus combined lamp equipment against the exact statutory permission and add any missing controlled case before claiming full branch coverage. The source-hashed conditional review remains source-audit pending, human-unreviewed and physically unverified. Current status stays **partial**.

Checkpoint log bindings: `cpu-tests.log` SHA-256 `2d33fe4edbe36a7fb8a7a83b2fbbdc9b1e766e93eb4cec32ec4c7bc9e0a78fae`; `primary-compatibility.log` SHA-256 `8b1fd8178f0be651e2dad2ebb7ce0a3ad07b1471324550a8426f8cd10d826500`; `worker-check.log` SHA-256 `e6d799a26c3255e3f3bd4c32c5a54e63f672b7c123d39cbb28fdc110b40ab679`. Scoped strict command `.venv-cpu/bin/python worker_check.py --assignment heldout__C111294__NRS-484D-205-4__motor_vehicle_driver --complete --require-delivery-ready` rejects the truthful partial result with `Preparation acceptance failed: partial/missing packages remain`; `strict-gate.log` SHA-256 `89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292`.

## 2026-11-12 first selected case proof continuation

The previous first compatibility failure is resolved. `case-plan.json` now binds the exact selected requirement and source disposition; `first-measurement-contract.json` measures `backup_lamp_forward` from the six original motion, equipment, other-vehicle, context, trace and frame-map files and negatively removes `equipment.json`. A draft `proposals/cases.json` supplies the three exact selected recording descriptions needed for compatibility. All 12 inline constructions and root config have valid empty `context_inputs` arrays in their recording descriptions; the equipment and intersection originals remain required analysis sources and are hash-bound in the measurement contract. Construction hashes and all 12 exact offline checks were refreshed. The 17 assignment unit tests pass.

For `__forward_backup_lamp_off`, primary, fallback1 and fallback2 pass positive/negative compatibility and saved-only diagnostic processing. Their current receipts and logs are bound in `execution-manifest.json` and `result.json`. Fallback3 passes both checks in ignored `.runtime-work` staging, pending four returned proof slots. The other two exact cases still require case-specific diagnostic recipes and measurement contracts, then compatibility and saved processing. The semantic stage chain, physical preparation, independent delivery acceptance and comparison proofs remain worker-owned CPU work. No original Native lamp pixels or legal result is claimed. Current status is **partial**; scoped complete passes, while scoped strict readiness must still reject it.

Both remaining exact branches now have source-shaped diagnostic specifications staged under ignored `.runtime-work`: `c111294-no_backup_lamp_installed-diagnostic-spec.json` removes installed backup lamps while preserving forward motion and an off Native state; `c111294-forward_backup_lamp_on-diagnostic-spec.json` sets the Native lamp readback during the same forward interval. Their generated sources and materialized exact constructions both pass `lamp_finalizer.analyze` over all nine diagnostic frames. They are labelled diagnostic staging, have no returned recipe or proof binding yet, and do not establish physical equipment or emitted pixels.

### Shared-contract full software sweep

The two branch-specific diagnostic specifications and recipes are now returned under `cases/no_backup_lamp_installed/` and `cases/forward_backup_lamp_on/`. One shared `backup-lamp-measurement-contract.json` binds the same exact statutory measurement and six original sources for all three selected cases; case-specific config and `lamp_finalizer.analyze` enforce each branch's equipment and Native-state condition. All 12 positive/negative compatibility runs and all 12 saved-only diagnostic processing runs pass. The first selected case's four compatibility receipts and four saved logs are current and returned. The other two cases' eight compatibility outputs and eight saved-only outputs remain ignored staging because the shared return tree reached its 10,200-file cap; `execution-manifest.json` does not claim bindings for them. Their ignored paths use the `c111294-<branch>-<candidate>-compat-shared-v1` and `c111294-<branch>-<candidate>-saved-proof-v1` prefixes. Status remains **partial**. No physical lamp emission, equipment authority or legal result is inferred from these fixtures.

## 2026-11-12 restored preflight and returned no-equipment proofs

The updated pinned environment passes `.venv-cpu/bin/python runtime.py preflight`; `worker_check.py --updates` reports version 0 and no pauses. The batch nonstrict `worker_check.py` passes its static checks. The strict batch result remains partial because 18 assignments are not ready. This is unfinished CPU preparation, not a dependency failure.

For `heldout__C111294__NRS-484D-205-4__motor_vehicle_driver__no_backup_lamp_installed`, the returned `execution-manifest.json` now binds current primary and fallback1 positive/negative compatibility receipts and saved-processing logs. Their exact construction hashes remain `dce46283bcbda6363d6d0baba65d4aa3236ad3ef5f6c1764c04096bf3e719948` (primary) and the manifest-bound fallback1 hash. Run the saved commands in those two manifest entries to reproduce the source-preserving diagnostic processing. The negative analyses reject removed `equipment.json`; the fixtures establish software behavior only. No original Native rear-lamp pixels, equipment authority or legal judgment is claimed.

Nine nonempty logs with no JSON binding were source-hash archived in `work/_shared/prune-history-consolidated-08.json` to open return slots. The restore script `work/_shared/restore_compacted_zero_logs.py --assignment ID --skip-existing-verified` verifies and restores their exact bytes if historical diagnostics are needed. Current return count is 10,199 against the frozen 10,200 cap. Next, make room by archiving only obsolete unbound history, then return/bind the other six C111294 candidate receipts from `.runtime-work/c111294-<branch>-<candidate>-compat-shared-v1/` and matching `-saved-v1.log`. Finish semantic, delivery and comparison audits and rerun scoped strict before changing `partial`. The conditional review remains source-audit pending, human-unreviewed and physically unverified.

### Returned complete no-equipment candidate sweep

`execution-manifest.json` now binds positive/negative compatibility receipts and saved-only proof logs for primary, fallback1, fallback2 and fallback3 of `__no_backup_lamp_installed`. The source-shaped diagnostic is shared within that exact case; each receipt binds its own construction hash. The 17 assignment tests and six repository tests pass after the tool update. The assignment-scoped nonstrict gate passes. Result remains **partial** because `__forward_backup_lamp_on` candidate receipts, semantic stage chain, independent delivery acceptance, comparison proof bindings, and original pixel/equipment review are incomplete. The latter physical reviews are future local execution; the CPU deliverables remain worker-owned.

Return inventory is 10,199 files. Seventeen unbound historical text files, including old provisional manifests and preview queues, were SHA-256 archived in `work/_shared/prune-history-consolidated-08.json`. The archived files are recoverable with the hash-checking restore script. Before binding more receipts, compact only obsolete unbound history and preserve every current manifest-bound file. Resume with the four staged `c111294-forward_backup_lamp_on-<candidate>-compat-shared-v1` compatibility receipts and their `-saved-v1.log` files, then implement the delivery audit and proposal chain. Do not promote status until the scoped strict gate passes.

Final turn checks: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python worker_check.py --assignment heldout__C111294__NRS-484D-205-4__motor_vehicle_driver --complete` exits 0. `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` exits 1 with `Preparation acceptance failed: partial/missing packages remain` (log SHA-256 `89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292`). This follows the unchanged 18 partial statuses; no ready status is claimed for this assignment. The six repository tests and 17 assignment tests pass. Current `cpu-tests.log` SHA-256 is `71a683abb23fbdf26207cc8231ad3cc0e1ad431c01e534294accc8c1c2c56c60`.

### Independent no-equipment delivery audit implementation

`delivery_audit.py` now independently checks exact case identity, equality of saved analysis and result, hashes of six original measurement sources, participant/frame/time joins and full FFmpeg decode of all four original source-camera streams. Its Native branch additionally requires sealed originals, owner exit, complete frame count, an independently cited equipment inspection and original rear-lamp pixel review. It refuses fixture provenance in Native mode. The fixture branch is explicitly diagnostic and reports no physical or legal acceptance.

The returned `delivery_acceptance` entry for `__no_backup_lamp_installed` binds the script SHA-256 `a573736dbb70f59d2aecec4379451a9500b14eed465b13ac795201d1c7706df6`, positive diagnostic command/log and negative missing-`equipment.json` command/log. Both were executed: positive exits 0; negative exits 1 with `Missing original source: equipment.json`. The scoped nonstrict gate still passes. The other exact cases need their own delivery acceptance bindings, and the full physical/pixel source review remains pending. Three additional unbound historic probe receipts were source-hash archived in `work/_shared/prune-history-consolidated-08.json`; returned file count is 10,199.

Archive correction: the C125714 three-lane delivery receipt was found bound in that assignment's `result.json` and restored byte-for-byte to its recorded SHA-256. An unbound queued comparison history file was archived instead. The current C111294 audit binding and returned count are unchanged.

### All twelve exact software proofs returned

The current `execution-manifest.json` now binds exact offline, positive/negative compatibility and saved-only processing receipts for primary and fallback1/2/3 of all three exact selected cases: `__forward_backup_lamp_off`, `__no_backup_lamp_installed`, and `__forward_backup_lamp_on`. No construction or diagnostic source changed during receipt binding; the staged checks were run after the CPU toolchain update and their current hashes are in the manifest. The no-equipment case also has a positive and missing-equipment independent delivery audit. The other two exact delivery audits, canonical semantic proposals, comparison proof bindings, and physical preparation remain CPU work. Actual equipment authority, rear-lamp emission and statutory outcome remain unverified.

Fourteen unbound historical proof summaries from the separate ready C111294 / NRS-484B-250-3 assignment and one unbound per-assignment GPU queue from ready C111603 were source-hash archived to open return slots; their scoped strict gates still exit 0. `work/` is again exactly at the frozen 10,200-file cap. Archive or consolidate further only with a source-hash restore path and rerun affected strict scoped gates. The C111294 / NRS-484D-205-4 result remains **partial** pending its own strict gate.

### Controlled comparison fixture receipts

`case-plan.json` now binds the independent `lamp_comparison_audit.py` and returned source-hashed proofs `comparison-optional_equipment-proof.json` (SHA-256 `40b8d7148ad9c42a4630e09402c1fcb56c0cf2dc0285890397e81425b38e0895`) and `comparison-forward_illumination-proof.json` (SHA-256 `3116bc6849968765d42a8a0f21bc2f51e6e1f4e5540df4f9e5aaaa9300dbf886`). The proofs compare current saved diagnostic attempts and check fixed intersection, controller, camera and context conditions plus the declared equipment or Native-state difference. `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/heldout__C111294__NRS-484D-205-4__motor_vehicle_driver/tests -p test_lamp_comparison_audit.py -v` passes two tests including changed fixed-context and missing-difference rejection. These are synthetic comparison audits; realized Native motion and pixels remain open. Two unbound historical per-assignment queue/receipt files from ready packages were SHA-256 archived; their scoped strict gates remained passing.

### Canonical semantic proposals returned

`proposals/semantic-index.json` now source-hash binds `relevance_batch.json`, `relevance.json`, `template.json`, `judgment_1.json`, `bindings.json` and the existing exact `cases.json`. The proposal follows the exact statute: optional one-or-more backup lamps, separate or combined, and no lit backup lamps during actual forward motion. It makes no legal transition allowance or numeric cutoff. The proposal preserves the conditional review source SHA-256 `9bfc9ded14ad3093469812fd1a6a49acc63f5585df51153c665684cbb9efebe2`, pending source audit, unreviewed human status and unverified physical feasibility. It treats Native state and emitted pixels separately. The scoped nonstrict gate passes after this update; the separate C111603 ready strict gate also passes after source-hash archiving six unbound historical comparison summaries.

Status remains **partial**. Next CPU actions are the off/on independent delivery acceptance positive/negative bindings, a real Native source/closure audit dry run with falsified evidence rejected, final original-law and optional combined-lamp branch review, any needed physical-preparation CPU tests, then scoped strict readiness. Do not infer physical illumination, equipment authority or legal outcome from these diagnostic fixtures.

### Off/on independent delivery audit bindings

The same returned `delivery_audit.py` was run against the saved diagnostic analysis for `__forward_backup_lamp_off` and `__forward_backup_lamp_on`; both positive audits exit 0 after exact identity, six original source hashes, participant/time joins and full decode of four original cameras. Each separate negative attempt removes `equipment.json` and exits 1 with `Missing original source: equipment.json`. Their commands, exit codes, log hashes and current audit script hash are bound in each exact manifest entry's `delivery_acceptance`. This is software evidence only. Original installed hardware, emitted pixels, Native capture closure and physical completion remain unverified. Four historical unbound probe configs from otherwise ready assignments were source-hash archived; rerun their scoped strict gates after archive when resuming.

The scoped nonstrict C111294 gate still exits 0 with exactly 10,200 returned files. Result is **partial** because the remaining CPU physical-preparation and final semantic/branch review have not been completed or strictly accepted. The conditional review stays pending source audit and human review.

Archive validation correction: the ready C111588 scoped strict gate required its `probe-config.json`; that file was restored byte-for-byte from the SHA-256 archive. An unbound C111294 / NRS-484B-250-3 provisional manifest was archived instead. Both affected ready scoped strict gates now exit 0, as do the C110161, C178038 and C136539 gates after the probe-config compaction. Current returned count remains 10,200.

### Direct ready-validator finding and exact next implementation

A read-only call to `runtime/scenario_pipeline/worker_exchange/execution_manifest.py:validate(repo, assignment_id)` on the current returned manifest fails with `Missing physical preparation proof for case: heldout__C111294__NRS-484D-205-4__motor_vehicle_driver__forward_backup_lamp_off`. This is a worker-owned CPU implementation gap, not a missing external dependency. Next, implement a source-derived forward-motion completion checker and capture lifecycle checker under this assignment. Exercise complete-motion, incomplete-motion and missing-evidence original-shaped fixtures plus rejection when saved processing precedes owner release. Bind the fixture result/log hashes and lifecycle receipt under `physical_preparation` for each exact case. Because this changes the finalizer/construction, rerun all affected 12 exact offline, compatibility, saved-processing, delivery and comparison proofs before scoped strict readiness. Keep Native emitted-pixel and equipment-authority review separate and unclaimed.
