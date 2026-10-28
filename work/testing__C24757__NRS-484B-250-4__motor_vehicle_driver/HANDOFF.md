# Executable preparation: partial

This package includes exact-scope draft semantic proposals, physical vehicle feedback control, authored map generation or native signal/sign route discovery, four synchronized RGB encoders, original-frame PipelineCapture, required-channel raw packets, observed speed/gap summaries, signal handling and restoration. No simulator was run.

Baseline is a neutral unselected definition. Run `python3.11 runner.py --check`; live use `python3 runner.py --output-dir PATH --host HOST --port PORT --case-id CASE_ID` from this directory. The executor must provide CARLA 0.9.15, Python3.8-compatible dependencies, ffmpeg and a dedicated resource lease. Runtime imports are lazy. The runner preserves failed results and returns nonzero while semantic capability is partial.

- Semantic projection of all required atoms from raw original-frame packets is unfinished; packets are retained rather than fabricated observations.
- Full rendered feature/indicator visibility and per-atom interpretation need a native first-run audit; no legal acceptance claimed.
- Native Off/frozen signal control and halt/no-halt controller implemented. Clear stop-line mesh, blind obstructions, earlier-stopped/occupying separate vehicles and all-entrance history interactions are not implemented; native binding required.
- Nine-point sight capture auto-enables from required atom but incoming-lane 230m coverage is not statically certified on a discovered native route.

The root construction anchors the first active case. Additional canonical proposals (same implementation, case-specific config.json) are:

- constructions/testing__C24757__NRS-484B-250-4__motor_vehicle_driver__omit_required_action.json

Finalization: retain the complete original trace, recorder, road.xodr, native graphs/evidence, raw per-channel packets, four full RGB videos and zero-based frame map. Recompute speed/gap summaries only from saved actual samples in frozen windows. The 0.5mph speed criterion is engineering tracking tolerance. Validate native geometry/device governance, full body entry, all relevant traffic histories, visibility and each required atom; missing semantic capability is a repair requirement, not data to fabricate. Review synchronized full videos before any downstream labeling. Keep judgment phrases unresolved; do not treat capability probes as accepted judgment sweep coverage. Repair the same frozen setting with evidence-backed code changes; never retrospectively change range/targets or silently retry unchanged code.

Tests are CPU-only; result.json records exact commands, exit codes and hashed logs. Sources and existing evidence are retained in case-plan.json. Update 002 applied; no pause was active.
