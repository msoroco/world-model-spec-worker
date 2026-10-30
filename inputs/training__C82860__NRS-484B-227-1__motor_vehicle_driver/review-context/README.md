# C82860 / NRS-484B-227-1

## Law

**NRS-484B-227-1 — Driving on divided highway (1)**

> Every vehicle driven upon a divided highway must be driven only upon the right-hand roadway and must not be driven over, across or within any dividing space, barrier or section or make any left turn, semicircular turn or U-turn, except through an opening in the barrier or dividing section or space or at a crossover or intersection established by a public authority.

## Recording comparisons

Settings below are requested or authored, not measured outcomes. Judgment calls remain unresolved unless the saved metadata supplies an expected label. Videos, traces and metadata are editable review copies; demo links share the corresponding full-set recording directories.

### Turn path pair

Comparison: `C82860-227-1-turn-path-pair`.

| Case | Video / data | Test setting | Compared against | Judgment call | Recorded label |
| --- | --- | --- | --- | --- | --- |
| 1 | [video](C82860-227-1-opening-compliant-attempt--18c683a10cc2/video.webm) · [trace](C82860-227-1-opening-compliant-attempt--18c683a10cc2/trace.json) · [metadata](C82860-227-1-opening-compliant-attempt--18c683a10cc2/metadata.json) | Commanded turn path.departure.end m: [-6, 30, 0]; Commanded turn path.departure.start m: [0, 30, 0]; Commanded turn path.u turn.x m: 25*sin(theta); Commanded turn path.u turn.y m: 20 + 25*(1 cos(theta)) | 2 | established by a public authority | compliant |
| 2 | [video](C82860-227-1-same-roadway-violating-attempt--a25b4cf24472/video.webm) · [trace](C82860-227-1-same-roadway-violating-attempt--a25b4cf24472/trace.json) · [metadata](C82860-227-1-same-roadway-violating-attempt--a25b4cf24472/metadata.json) | Commanded turn path.departure.end m: [-6, -6, 0]; Commanded turn path.departure.start m: [0, -6, 0]; Commanded turn path.u turn.x m: 7*sin(theta); Commanded turn path.u turn.y m: 20 + 7*(1 cos(theta)) | 1 | established by a public authority | violation |

Case IDs: 1: `C82860-227-1-opening-compliant-attempt`; 2: `C82860-227-1-same-roadway-violating-attempt`.

## Trace compatibility update

Versioned offline traces now pass full Core decoding. Retired source classifications and capabilities remain in typed provenance fields; unsupported legal class membership remains unknown. Original videos, labels and acceptance traces are retained. Unknown entrance associations remain omitted. See the [validation report](../../maintenance/demo-core-compatibility-v2/README.md).

| Case | Updated data | Validation |
| --- | --- | --- |
| C82860-227-1-opening-compliant-attempt | [trace](../../maintenance/demo-core-compatibility-v2/recordings/18c683a10cc245d0b78d53e50fc20028ead9ff9026ce9b17f587f6811d0e17c7/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/18c683a10cc245d0b78d53e50fc20028ead9ff9026ce9b17f587f6811d0e17c7/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/18c683a10cc245d0b78d53e50fc20028ead9ff9026ce9b17f587f6811d0e17c7/receipt.json) | Full Core decoding passes; source facts retained |
| C82860-227-1-same-roadway-violating-attempt | [trace](../../maintenance/demo-core-compatibility-v2/recordings/a25b4cf2447249057c1be84da7eb428f11766ad6efadbdff85828b09ddca2f76/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/a25b4cf2447249057c1be84da7eb428f11766ad6efadbdff85828b09ddca2f76/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/a25b4cf2447249057c1be84da7eb428f11766ad6efadbdff85828b09ddca2f76/receipt.json) | Full Core decoding passes; source facts retained |

## Remaining requirements

Accepted videos are retained even when additional requirements remain unfinished. Set scope and coverage dispositions remain authoritative; this migration does not mark an assignment complete.
