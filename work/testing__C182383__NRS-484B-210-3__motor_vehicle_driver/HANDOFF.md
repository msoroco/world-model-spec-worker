# C182383 paved-edge right-pass handoff

Status: CPU delivery prepared. Four exact cases and three independent comparisons. The scoped strict delivery gate passed on 2026-11-26.

NRS 484B.210(3) prohibits overtaking and passing on the right when the movement requires driving off the paved portion of the highway. The package measures completed pass, actual body travel beyond the independently classified paved edge, and a zero-clearance geometric fit lower bound separately. It leaves the legal safe-alternative and operative “requires” judgment unresolved; pavement width alone cannot resolve either.

The source-gated Native runner requires reviewed map, pavement classification, paved boundary, connected corridor, actor poses, and road-frame packets. It captures 900 original 20 Hz two-actor body frames and four camera videos. The saved finalizer recomputes body envelopes and sealed measurements from original rows; source hashes and frame joins reject substitution. Eight source/probe tests pass.

All four selected constructions passed pinned offline, positive and negative compatibility, and saved-only processing. Four controller fallbacks adjust only lateral gain for a concrete right-pass route and paved-edge risk; each passed pinned offline and positive/negative compatibility. Four physical/lifecycle diagnostic sets and four independent delivery diagnostic checks passed. Three comparison protocols passed positive and changed-classification negative checks. These are CPU diagnostics; original Native capture, full pixel review, physical completion, and legal review remain for GPU delivery.

Exact command: `.venv-cpu/bin/python worker_check.py --assignment testing__C182383__NRS-484B-210-3__motor_vehicle_driver --complete --require-delivery-ready` (exit 0).

Review anchors: `execution-manifest.json` SHA256 665c143a2f610fe6898b0e9f4b61b2e103d9a424038cf47691655dea9d958c25; `gpu-queue-proposal.json` SHA256 efab550abbddb4980bc60fcd77016e3b8ef842b52e719b3e295c31d2c8496501; `comparison-proposal.json` SHA256 dd7f6ac241aabe32cc0ccbdaefc39e22fe7684d4d4242c22758043e5d7292316; `cpu-tests.log` SHA256 52d4b185b22d882d75becc485abfe2ed0a74efef86843dc94bfce63a7eb47c08.
