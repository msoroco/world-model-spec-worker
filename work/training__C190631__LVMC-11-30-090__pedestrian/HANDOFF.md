# training__C190631__LVMC-11-30-090__pedestrian

Status: **ready / delivery_prepared**. Exact assignment-scoped strict CPU check passed on 2026-11-26. Original Native physical capture and independent local acceptance remain pending.

## Source and scope

LVMC 11.30.090: “Where sidewalks are provided it shall be unlawful for any pedestrian to walk along and upon an adjacent roadway.” C190631 fixes a pedestrian overpass and travel. Accepted recording membership is empty. Probe_01 targets sidewalk walking and probe_02 the adjacent roadway on the same upper road, pedestrian route, 20 Hz / 30 s timing, and four synchronized cameras. The lower crossing road is grade separated. No legal numeric threshold or verdict was invented.

## Selected package

- `execution-manifest.json` SHA-256 `d35d3d0fc6be38519ef1aec1370dbd26dc832070c1351c942a23e54546b5232e`; runtime manifest `5e2dd81ac49dd2d9814a10b71ee30cf85323868a8369116020b06a69cbfcc5e3`.
- `proposals/semantic-index.json` SHA-256 `a66bd54598aad8cd906cbf7cf2c77f8d1bd61197423402c382f3ab9a19bf9a4c`; seven canonical semantic stages passed. The qualitative judgment sweep stays explicitly incomplete pending original provision and adjacency evidence.
- `delivery_audit.py` SHA-256 `3e7a2005c5436e1eddf4dc4a530d2b79215344805b443da0e3a831415917264e`; each synthetic positive decodes all 600 frames of all four cameras and checks source joins; each ordinary-mode negative rejects the synthetic source. This proves audit software behavior, not original capture.
- `comparison_audit.py` SHA-256 `1f9fdc89b93817a223fb5719309827a1c414438a362b74434781e64ed4c567b6`; synthetic pair passes fixed-road, identity, time and footprint contrast, while ordinary mode rejects absent original Native provenance.

### probe_01

- Primary construction `b8be73d2929a088c0c66dc7f903887c06ad124fece1f1eb6ba7831d69c994b0c`; fallback construction `ff407389e97670cec55758ba0a45926f95bb3de36afda1da0ae3dd719007218f` (same surface, source-triggered x=-28 spawn).
- Primary offline log `51386b4902fad306336cf24a951d8800c900d88895f2ed30eea37172e9ef6678`, public compatibility receipt `1e8378f46a081d1b8376cae1ef3a00746ac167a6858782975964ebe842086fec`, saved-only receipt `c1142172982062118ee4625f32446f5c4a96bb5dcd415de4216e92d24790a225`.
- Fallback offline log `13f07ec64d5e3590be1cac59262832b8640e433ea1b0aea86cd3dbe527a3f88c` and public compatibility receipt `43ffefd55bdbe0ec35f13abd3c3cbb2352b40b4048de14f347508cc6c6b918f6`; positive and missing-source negative passed.
- Physical CPU fixture and lifecycle receipt `5f90b49cbb5fb8728e857e955bc7b67642d8f62eb1ed5f58b386b74d5486aded`; outcomes met, not_met and unverified are source-labeled synthetic fixtures.
- Delivery audit positive log `065e0c4a11b85688d432c86ea92e931717912d509901c83eeecdee4e1faf196c` and original-source rejection log `67acf715dded8dab777d9492287299eb19824926988d1723b7961b9a776d2809`.

### probe_02

- Primary construction `bad86b07f93117325edc15aa7f9ea6eafd74b4603e6272ec91efb7a7dc7265c5`; fallback construction `1cfbf53052ad825fc0d9634d9e6eb500fe81aebd86fcb82ef6758c615da828f7` (same surface, source-triggered x=-28 spawn).
- Primary offline log `f3d185aa94f1b733060760e707423f185e7eb709f15d0f36a5d69c5cf02c5a98`, public compatibility receipt `91e3a87153644900edec078ed3757a1b5cb45f06b05c3f87221da4ed42a4187f`, saved-only receipt `14194800d4aa58f5e30d473a5fc6bb5052d1d4683d36ac83b44290c9167f5155`.
- Fallback offline log `b42ebb2db2f690667f46ae370d48ea4aed7b629883cfdf9c5180463190c4b888` and public compatibility receipt `75a1a947315bbbe6d54042d188e7b66bc88f3799a032c40b8b3603ecfe8b41db`; positive and missing-source negative passed.
- Physical CPU fixture and lifecycle receipt `b306e433981a55e82ef3c7d0bef663d7e4b5370bdf683667bc118ccfd535a48b`; outcomes met, not_met and unverified are source-labeled synthetic fixtures.
- Delivery audit positive log `d1a2093ac49c3c49565e393d836c5721a0bca2e06805eecd0f0b67279a6451e5` and original-source rejection log `67acf715dded8dab777d9492287299eb19824926988d1723b7961b9a776d2809`.

## Exact check and local handoff

`TMPDIR=$PWD/.runtime-work/c190631-tmp SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c190631-strict .venv-cpu/bin/python -B worker_check.py --assignment training__C190631__LVMC-11-30-090__pedestrian --complete --require-delivery-ready` exited 0. The test log is `.runtime-work/c190631-exact-strict.log` and is intentionally outside `work/`.

Local delivery must run the original Native case with the current runtime, survey real sidewalk provision, pedestrian use, adjacency, grade separation, physical movement and original pixels, then process the saved attempt after Native exit and owner release. The physical result, qualitative law assessment and independent acceptance must be based on those original sources. The synthetic diagnostics are marked as such throughout.
