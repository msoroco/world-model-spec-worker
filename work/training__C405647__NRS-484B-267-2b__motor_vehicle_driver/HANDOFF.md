# NRS-484B-267-2b at C405647

Actor: `motor_vehicle_driver`. Frozen cell: `road` / `travel` / `emergency_vehicle`. Exact statutory source and selected already-moving witness are in `case-plan.json`.

Built a 30-second, 600-frame, 20-Hz, four-camera source-bound approach meter (`measure_emergency.py`) and authored road/emergency actor/controller requests (`emergency_scene.py`) for the two planned probes. The meter requires original map, vehicle, legal role, lamp, visibility and officer-direction source hashes, Native frame/time/camera joins, and observed approach to a moving flashing vehicle. It returns speed, passing surface gap, TTC and deceleration diagnostics. `emergency-measurement-contract.json` maps every mandatory observation. CPU positive/negative proofs are `emergency-proof.json` and `emergency-scene-proof.json`. Fixture motion and hashes are invented for unit testing.

The statute says “proceed with caution” without a numeric threshold. The meter therefore makes no legal compliance judgment. The authored scene has not executed in Native, and authorization, lamp qualification, original visibility, compatibility, process-saved video and independent audit are unverified. Official regulatory vehicle, preparing-to-move and law-enforcement direction remain separate alternatives. Both selected probes remain planned only; no accepted recording ID or reuse is claimed.

Next: realize four distinct source-preserving Native candidates per selected case, run pinned CPU offline and compatibility, join all four original camera streams to 600 Native frames, measure original source terms and inspect pixels/actor status, then run actual process-saved positive/negative fixtures and independent audit. Keep partial until scoped strict check passes.
