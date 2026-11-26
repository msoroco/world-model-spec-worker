# C24751 flashing-red heavy-vehicle handoff

Four exact stop-reference cases and two controlled comparisons are selected. Primary and fallback constructions preserve the official flashing-red device, physical occluder, surveyed crosswalk/limit-line/intersection references, heavy vehicle and four synchronized camera views. Stop-reference alternatives and incorporated post-stop rules remain explicit; there is no invented legal cutoff.

CPU proof: 15 unit tests passed; eight primary/fallback offline runs passed; eight current-hash positive/negative compatibility checks passed; four current-hash recorded-only saved replays passed; four synthetic complete/incomplete/missing physical and lifecycle checks passed. Independent delivery audit rejects missing original capture in all four cases. Semantic validation and assignment static check passed. These synthetic CPU proofs do not claim an original CARLA recording.

The source-gated Native runner and packet seal are ready for reviewed official device, occluder, map, vehicle, cameras and original capture. The assignment-local `gpu-queue-proposal.json` gives exact four case commands and `comparison-audit-plan.json` gives two comparison audits. Original physical stopping, four-view pixels, source provenance and post-stop legal judgment still require the GPU delivery and human review.
