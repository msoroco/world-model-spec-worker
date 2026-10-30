# C124163 / NRS-484B-227-1

## Law

**NRS-484B-227-1 — Driving on divided highway (1)**

> Every vehicle driven upon a divided highway must be driven only upon the right-hand roadway and must not be driven over, across or within any dividing space, barrier or section or make any left turn, semicircular turn or U-turn, except through an opening in the barrier or dividing section or space or at a crossover or intersection established by a public authority.

## Recording comparisons

Settings below are requested or authored, not measured outcomes. Judgment calls remain unresolved unless the saved metadata supplies an expected label. Videos, traces and metadata are editable review copies; demo links share the corresponding full-set recording directories.

### Left turn crossing pair

Comparison: `C124163-227-1-left-turn-crossing-pair`.

| Case | Video / data | Test setting | Compared against | Judgment call | Recorded label |
| --- | --- | --- | --- | --- | --- |
| 1 | [video](C124163-227-1-left-turn-permitted-crossing--0819c0dc3305/video.webm) · [trace](C124163-227-1-left-turn-permitted-crossing--0819c0dc3305/trace.json) · [metadata](C124163-227-1-left-turn-permitted-crossing--0819c0dc3305/metadata.json) | Commanded turn path.crossing station m: 12 | 2 | established by a public authority | compliant |
| 2 | [video](C124163-227-1-left-turn-prohibited-section--7ba1ab4a7268/video.webm) · [trace](C124163-227-1-left-turn-prohibited-section--7ba1ab4a7268/trace.json) · [metadata](C124163-227-1-left-turn-prohibited-section--7ba1ab4a7268/metadata.json) | Commanded turn path.crossing station m: 20 | 1 | established by a public authority | violation |

Case IDs: 1: `C124163-227-1-left-turn-permitted-crossing`; 2: `C124163-227-1-left-turn-prohibited-section`.

### Median

Comparison: `C124163-median-v1-opening-pair`.

| Case | Video / data | Test setting | Compared against | Judgment call | Recorded label |
| --- | --- | --- | --- | --- | --- |
| 1 | [video](C124163-median-v1-227-1-through-opening--e251930ca4dd/video.webm) · [trace](C124163-median-v1-227-1-through-opening--e251930ca4dd/trace.json) · [metadata](C124163-median-v1-227-1-through-opening--e251930ca4dd/metadata.json) | Commanded turn path.left turn anchor x m: 14 | 2 | established by a public authority | compliant |
| 2 | [video](C124163-median-v1-227-1-within-divider--c36e1b502857/video.webm) · [trace](C124163-median-v1-227-1-within-divider--c36e1b502857/trace.json) · [metadata](C124163-median-v1-227-1-within-divider--c36e1b502857/metadata.json) | Commanded turn path.left turn anchor x m: 32 | 1 | established by a public authority | violation |

Case IDs: 1: `C124163-median-v1-227-1-through-opening`; 2: `C124163-median-v1-227-1-within-divider`.

## Trace compatibility update

Versioned offline traces now pass full Core decoding. Retired source classifications and capabilities remain in typed provenance fields; unsupported legal class membership remains unknown. Original videos, labels and acceptance traces are retained. Unknown entrance associations remain omitted. See the [validation report](../../maintenance/demo-core-compatibility-v2/README.md).

| Case | Updated data | Validation |
| --- | --- | --- |
| C124163-227-1-left-turn-permitted-crossing | [trace](../../maintenance/demo-core-compatibility-v2/recordings/0819c0dc3305d9f0ce7010fdc279a2375e24bde9fb722fa8e3370f2353181314/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/0819c0dc3305d9f0ce7010fdc279a2375e24bde9fb722fa8e3370f2353181314/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/0819c0dc3305d9f0ce7010fdc279a2375e24bde9fb722fa8e3370f2353181314/receipt.json) | Full Core decoding passes; source facts retained |
| C124163-227-1-left-turn-prohibited-section | [trace](../../maintenance/demo-core-compatibility-v2/recordings/7ba1ab4a7268ef149ff00d8fd63eb0d32ba63cc6801f9613084f82cc052ada54/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/7ba1ab4a7268ef149ff00d8fd63eb0d32ba63cc6801f9613084f82cc052ada54/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/7ba1ab4a7268ef149ff00d8fd63eb0d32ba63cc6801f9613084f82cc052ada54/receipt.json) | Full Core decoding passes; source facts retained |
| C124163-median-v1-227-1-through-opening | [trace](../../maintenance/demo-core-compatibility-v2/recordings/e251930ca4dd928e72c50e8033d25dcedf03956932c82816fe75ea2c8c46b240/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/e251930ca4dd928e72c50e8033d25dcedf03956932c82816fe75ea2c8c46b240/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/e251930ca4dd928e72c50e8033d25dcedf03956932c82816fe75ea2c8c46b240/receipt.json) | Full Core decoding passes; source facts retained |
| C124163-median-v1-227-1-within-divider | [trace](../../maintenance/demo-core-compatibility-v2/recordings/c36e1b5028570eb2390af59a44abe48491963c8ab9a1ea17966e997c17c774da/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/c36e1b5028570eb2390af59a44abe48491963c8ab9a1ea17966e997c17c774da/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/c36e1b5028570eb2390af59a44abe48491963c8ab9a1ea17966e997c17c774da/receipt.json) | Full Core decoding passes; source facts retained |

## Remaining requirements

Accepted videos are retained even when additional requirements remain unfinished. Set scope and coverage dispositions remain authoritative; this migration does not mark an assignment complete.
