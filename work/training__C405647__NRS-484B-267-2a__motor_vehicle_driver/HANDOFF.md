# C405647 emergency-vehicle approach CPU checkpoint

Status: **partial**. The selected cases have authored diagnostic requests and exact unselected offline packages. Native source capture, four original cameras, compatibility, actual saved processing and independent audit have not passed.

Selected law branch: NRS 484B.267(2)(a), already-moving authorized emergency vehicle or regulatory-agency vehicle using qualifying flashing lamps. The driver must decrease to a reasonable and proper speed unless a law enforcement officer directs otherwise. The numerical intervention below is a controlled diagnostic difference, not a legal determination of reasonable speed. Preparing-to-move movement and hand-signal alternatives remain unbuilt.

## CPU construction and proofs

- `native/emergency_approach.py` (SHA-256 `6d82095432668f37f7879f7b08e67ce6dca80fea42eb6a43630341753c0e07a0`) generated two exact 600-frame, 20 Hz, 30-second source requests. An already-moving emergency actor with flashing-lamp request and no officer instruction is fixed. Condition A reduces ego speed from 14 to 7 m/s; B retains 14 m/s. The meter measured 7 and 0 m/s reductions respectively and rejected missing lamps, a stationary qualifying actor, officer direction and forged source provenance. `native/emergency-approach-proof.json` SHA-256 `b6dbc9e92b52031edeb1eb985ae85c6e8dd4039f8a67ef0a392e82b96c96fc96`. Request traces under `.runtime-work/` SHA-256: A `35a3d23fe2b4ba00092c5b766fd47801fcdb9b83aa042f4b3eaf72d1705df45a`, B `3c8e5fe59b1de1f7f841d9cffb6d374c8bdd70c85268ce9d5c830e4ec04f9fa6`. These are authored requests, not Native observations.
- `native/build_draft.py` SHA-256 `c2fbc8c3db9f253bcdd7f456c5ee214072f3e1b1361e078a874897c0e9fc5bef` built exact unselected offline packages. Construction hashes: A `d87dec9150f5e1e94e254d3e7b6ab194f2d12f1e035cdc3694170dee9c76b967`, B `4bea773bf338696aec106d5013fb8a384576a5da9fa7d8476ff39ee45d66f2e2`; manifest `a4eea41321960a901b525916dc076c895bef92b67c3226580f10719bf7296fae`.
- `runtime.py offline --manifest work/<assignment>/native/draft-manifest.json --case <exact-case-id> --output .runtime-work/c405647-offline-<condition>` passed for A and B; each returned `simulation_started=false`. Returned log hashes: A `7a931bf97316261e4a8b045d7a17ae8738154dcb512c4d776f998f336d477c0b`, B `87710054ab00a7210b1839e3b35fa5a62612b5fcc79e3d6fcfdb69f6c37df599`.
- `native/measurement-contract.json` (SHA-256 `ffa170fa96c09184b1177c0db7054a5d6802f376f8e3b1c53d07610bc7ce119e`) maps all 13 observation terms to future original actor, lamp, sign, weather and visual evidence.

## Worker-owned remaining work

Build real Native moving emergency actor, flashing lamps, ego speed controllers and all four source-camera captures for both exact cases. Replace authored data with source-joined original readback. Prove qualifying lamps, officer exception state and reasonable-speed context from source. Implement selected primary and three distinct fallbacks through offline and compatibility, process actual saved positive/negative evidence, and audit the comparison plus preparing-to-move alternatives. Keep partial until scoped strict delivery passes.
