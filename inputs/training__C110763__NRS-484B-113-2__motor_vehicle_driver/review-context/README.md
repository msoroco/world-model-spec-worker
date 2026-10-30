# C110763 / NRS-484B-113-2

## Law

**NRS-484B-113-2 — Limitations on backing (2)**

> The driver of a vehicle: Shall not back into an intersection, on or over a crosswalk, or around a street corner.

## Recording comparisons

Settings below are requested or authored, not measured outcomes. Judgment calls remain unresolved unless the saved metadata supplies an expected label. Videos, traces and metadata are editable review copies; demo links share the corresponding full-set recording directories.

### Intersection entry

Comparison: `C110763-113-2-intersection-entry`.

| Case | Video / data | Test setting | Compared against | Judgment call | Recorded label |
| --- | --- | --- | --- | --- | --- |
| 1 | [video](C110763-113-2-inside--9dcfc5d68325/video.webm) · [trace](C110763-113-2-inside--9dcfc5d68325/trace.json) · [metadata](C110763-113-2-inside--9dcfc5d68325/metadata.json) | Commanded turn path.requested path: [[-20, -1.75, 0], [0, -1.75, 0]] | 2 | None listed | violation |
| 2 | [video](C110763-113-2-outside--dd99054966ed/video.webm) · [trace](C110763-113-2-outside--dd99054966ed/trace.json) · [metadata](C110763-113-2-outside--dd99054966ed/metadata.json) | Commanded turn path.requested path: [[-20, -1.75, 0], [-10, -1.75, 0]] | 1 | None listed | compliant |

Case IDs: 1: `C110763-113-2-inside`; 2: `C110763-113-2-outside`.

### Intersection entry pair

Comparison: `C110763-113-2-intersection-entry-pair`.

| Case | Video / data | Test setting | Compared against | Judgment call | Recorded label |
| --- | --- | --- | --- | --- | --- |
| 1 | [video](C110763-113-2-inside--64594c77e2ae/video.webm) · [trace](C110763-113-2-inside--64594c77e2ae/trace.json) · [metadata](C110763-113-2-inside--64594c77e2ae/metadata.json) | Commanded turn path.requested endpoint xy m: [0, -3] | 2 | None listed | violation |
| 2 | [video](C110763-113-2-outside--ac561ad43d05/video.webm) · [trace](C110763-113-2-outside--ac561ad43d05/trace.json) · [metadata](C110763-113-2-outside--ac561ad43d05/metadata.json) | Commanded turn path.requested endpoint xy m: [12, -3] | 1 | None listed | compliant |

Case IDs: 1: `C110763-113-2-inside`; 2: `C110763-113-2-outside`.

## Trace compatibility update

Versioned offline traces now pass full Core decoding. Retired source classifications and capabilities remain in typed provenance fields; unsupported legal class membership remains unknown. Original videos, labels and acceptance traces are retained. Unknown entrance associations remain omitted. See the [validation report](../../maintenance/demo-core-compatibility-v2/README.md).

| Case | Updated data | Validation |
| --- | --- | --- |
| C110763-113-2-inside | [trace](../../maintenance/demo-core-compatibility-v2/recordings/64594c77e2ae2f29aace8cc4ddff4b30d15e2d5ee057c9ad44998d0368053ba6/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/64594c77e2ae2f29aace8cc4ddff4b30d15e2d5ee057c9ad44998d0368053ba6/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/64594c77e2ae2f29aace8cc4ddff4b30d15e2d5ee057c9ad44998d0368053ba6/receipt.json) | Full Core decoding passes; source facts retained |
| C110763-113-2-outside | [trace](../../maintenance/demo-core-compatibility-v2/recordings/ac561ad43d05a007af4373826bb0de9ee44d5a129822fa5a41f8c790ebc75cfd/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/ac561ad43d05a007af4373826bb0de9ee44d5a129822fa5a41f8c790ebc75cfd/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/ac561ad43d05a007af4373826bb0de9ee44d5a129822fa5a41f8c790ebc75cfd/receipt.json) | Full Core decoding passes; source facts retained |
| C110763-113-2-inside | [trace](../../maintenance/demo-core-compatibility-v2/recordings/9dcfc5d68325113cf851e5e7f40d68b46f7df9f3dc940117c75c59072fd93112/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/9dcfc5d68325113cf851e5e7f40d68b46f7df9f3dc940117c75c59072fd93112/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/9dcfc5d68325113cf851e5e7f40d68b46f7df9f3dc940117c75c59072fd93112/receipt.json) | Full Core decoding passes; source facts retained |
| C110763-113-2-outside | [trace](../../maintenance/demo-core-compatibility-v2/recordings/dd99054966ed89b2c03784d76e6be23af6bf91d463cb7e2e09ca0921eb59834a/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/dd99054966ed89b2c03784d76e6be23af6bf91d463cb7e2e09ca0921eb59834a/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/dd99054966ed89b2c03784d76e6be23af6bf91d463cb7e2e09ca0921eb59834a/receipt.json) | Full Core decoding passes; source facts retained |

## Remaining requirements

Accepted videos are retained even when additional requirements remain unfinished. Set scope and coverage dispositions remain authoritative; this migration does not mark an assignment complete.
