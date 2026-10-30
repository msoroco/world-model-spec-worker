# C111294 / NRS-484B-250-1

## Law

**NRS-484B-250-1 — Vehicle approaching or entering intersection (1)**

> The driver of a vehicle approaching an intersection shall yield the right-of-way to a vehicle which has entered the intersection from a different highway. Except as otherwise provided in subsection 4 [NRS-484B-250-4], this section does not apply at intersections controlled by official traffic-control devices or to vehicles approaching each other from opposite directions, when the driver of one of the vehicles is intending to or is making a left turn.

## Recording comparisons

Settings below are requested or authored, not measured outcomes. Judgment calls remain unresolved unless the saved metadata supplies an expected label. Videos, traces and metadata are editable review copies; demo links share the corresponding full-set recording directories.

### Prior entry pair

Comparison: `C111294-250-1-prior-entry-pair`.

| Case | Video / data | Test setting | Compared against | Judgment call | Recorded label |
| --- | --- | --- | --- | --- | --- |
| 1 | [video](C111294-250-1-compliant-attempt--cb6ec1a81f55/video.webm) · [trace](C111294-250-1-compliant-attempt--cb6ec1a81f55/trace.json) · [metadata](C111294-250-1-compliant-attempt--cb6ec1a81f55/metadata.json) | Commanded turn path.ego interaction policy: Hold before footprint entry until the other footprint has exited, then continue straight. | 2 | None listed | compliant |
| 2 | [video](C111294-250-1-violating-attempt--52dfdc83c2a4/video.webm) · [trace](C111294-250-1-violating-attempt--52dfdc83c2a4/trace.json) · [metadata](C111294-250-1-violating-attempt--52dfdc83c2a4/metadata.json) | Commanded turn path.ego interaction policy: Continue straight without the paired pre entry hold. | 1 | None listed | violation |

Case IDs: 1: `C111294-250-1-compliant-attempt`; 2: `C111294-250-1-violating-attempt`.

### Yield

Comparison: `C111294-yield-v1-prior-entry-pair`.

| Case | Video / data | Test setting | Compared against | Judgment call | Recorded label |
| --- | --- | --- | --- | --- | --- |
| 1 | [video](C111294-yield-v1-250-1-no-yield--52d9fa3a2c62/video.webm) · [trace](C111294-yield-v1-250-1-no-yield--52d9fa3a2c62/trace.json) · [metadata](C111294-yield-v1-250-1-no-yield--52d9fa3a2c62/metadata.json) | Commanded turn path.ego yield policy: continue | 2 | None listed | violation |
| 2 | [video](C111294-yield-v1-250-1-yield--be743bdb0584/video.webm) · [trace](C111294-yield-v1-250-1-yield--be743bdb0584/trace.json) · [metadata](C111294-yield-v1-250-1-yield--be743bdb0584/metadata.json) | Commanded turn path.ego yield policy: yield | 1 | None listed | compliant |

Case IDs: 1: `C111294-yield-v1-250-1-no-yield`; 2: `C111294-yield-v1-250-1-yield`.

## Trace compatibility update

Versioned offline traces now pass full Core decoding. Retired source classifications and capabilities remain in typed provenance fields; unsupported legal class membership remains unknown. Original videos, labels and acceptance traces are retained. Unknown entrance associations remain omitted. See the [validation report](../../maintenance/demo-core-compatibility-v2/README.md).

| Case | Updated data | Validation |
| --- | --- | --- |
| C111294-250-1-compliant-attempt | [trace](../../maintenance/demo-core-compatibility-v2/recordings/cb6ec1a81f558d9901da585038e814c5f42d6e882f19eb125ba4c68976ca2b10/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/cb6ec1a81f558d9901da585038e814c5f42d6e882f19eb125ba4c68976ca2b10/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/cb6ec1a81f558d9901da585038e814c5f42d6e882f19eb125ba4c68976ca2b10/receipt.json) | Full Core decoding passes; source facts retained |
| C111294-250-1-violating-attempt | [trace](../../maintenance/demo-core-compatibility-v2/recordings/52dfdc83c2a4856499d70f2be71a6fc606dcf7bf11b5e2f50ab486c832232808/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/52dfdc83c2a4856499d70f2be71a6fc606dcf7bf11b5e2f50ab486c832232808/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/52dfdc83c2a4856499d70f2be71a6fc606dcf7bf11b5e2f50ab486c832232808/receipt.json) | Full Core decoding passes; source facts retained |
| C111294-yield-v1-250-1-no-yield | [trace](../../maintenance/demo-core-compatibility-v2/recordings/52d9fa3a2c625c53e728207161e36b08c9b97c6bf526962466553a64767e0ff9/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/52d9fa3a2c625c53e728207161e36b08c9b97c6bf526962466553a64767e0ff9/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/52d9fa3a2c625c53e728207161e36b08c9b97c6bf526962466553a64767e0ff9/receipt.json) | Full Core decoding passes; source facts retained |
| C111294-yield-v1-250-1-yield | [trace](../../maintenance/demo-core-compatibility-v2/recordings/be743bdb05847f42e41da92b81299d3a4c837f89cb2fcd1e99fadc53f1da66d9/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/be743bdb05847f42e41da92b81299d3a4c837f89cb2fcd1e99fadc53f1da66d9/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/be743bdb05847f42e41da92b81299d3a4c837f89cb2fcd1e99fadc53f1da66d9/receipt.json) | Full Core decoding passes; source facts retained |

## Remaining requirements

Accepted videos are retained even when additional requirements remain unfinished. Set scope and coverage dispositions remain authoritative; this migration does not mark an assignment complete.
