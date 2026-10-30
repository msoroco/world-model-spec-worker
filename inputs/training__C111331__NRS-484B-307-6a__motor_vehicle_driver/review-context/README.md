# C111331 / NRS-484B-307-6a

## Law

**NRS-484B-307-6a — Traffic controlled by official traffic-control devices (6)(a)**

> Where the signal is a steady yellow signal alone: Vehicular traffic facing the signal is thereby warned that the related green movement is being terminated or that a steady red indication will be exhibited immediately thereafter, and such vehicular traffic must not enter the intersection when the red signal is exhibited.

## Recording comparisons

Settings below are requested or authored, not measured outcomes. Judgment calls remain unresolved unless the saved metadata supplies an expected label. Videos, traces and metadata are editable review copies; demo links share the corresponding full-set recording directories.

### 307 6a

Comparison: `C111331-307-6a`.

| Case | Video / data | Test setting | Compared against | Judgment call | Recorded label |
| --- | --- | --- | --- | --- | --- |
| 1 | [video](C111331-307-6a-compliant-attempt--448b9e51002d/video.webm) · [trace](C111331-307-6a-compliant-attempt--448b9e51002d/trace.json) · [metadata](C111331-307-6a-compliant-attempt--448b9e51002d/metadata.json) | Commanded turn path.signal response: Stop upstream of both the physical junction surface and any verified stop line, hold through red, then resume the same route on green | 2 | None listed | compliant |
| 2 | [video](C111331-307-6a-violating-attempt--fdc101fc9070/video.webm) · [trace](C111331-307-6a-violating-attempt--fdc101fc9070/trace.json) · [metadata](C111331-307-6a-violating-attempt--fdc101fc9070/metadata.json) | Commanded turn path.signal response: Continue tracking the shared route at commanded approach speed through yellow and red without the upstream signal stop | 1 | None listed | violation |

Case IDs: 1: `C111331-307-6a-compliant-attempt`; 2: `C111331-307-6a-violating-attempt`.

### Yellow

Comparison: `C111331-yellow-v1-entry-pair`.

| Case | Video / data | Test setting | Compared against | Judgment call | Recorded label |
| --- | --- | --- | --- | --- | --- |
| 1 | [video](C111331-yellow-v1-307-6a-entry-before-red--9ea666feb170/video.webm) · [trace](C111331-yellow-v1-307-6a-entry-before-red--9ea666feb170/trace.json) · [metadata](C111331-yellow-v1-307-6a-entry-before-red--9ea666feb170/metadata.json) | Traffic signal state.requested entry offset s: 1; Traffic signal state.requested front clearance trigger m: null; Traffic signal state.transition trigger: entry plus 1s | 2 | None listed | compliant |
| 2 | [video](C111331-yellow-v1-307-6a-entry-on-red--58ba79a576b9/video.webm) · [trace](C111331-yellow-v1-307-6a-entry-on-red--58ba79a576b9/trace.json) · [metadata](C111331-yellow-v1-307-6a-entry-on-red--58ba79a576b9/metadata.json) | Traffic signal state.requested entry offset s: null; Traffic signal state.requested front clearance trigger m: 5; Traffic signal state.transition trigger: front 5m before entry | 1 | None listed | violation |

Case IDs: 1: `C111331-yellow-v1-307-6a-entry-before-red`; 2: `C111331-yellow-v1-307-6a-entry-on-red`.

## Trace compatibility update

Versioned offline traces now pass full Core decoding. Retired source classifications and capabilities remain in typed provenance fields; unsupported legal class membership remains unknown. Original videos, labels and acceptance traces are retained. Unknown entrance associations remain omitted. See the [validation report](../../maintenance/demo-core-compatibility-v2/README.md).

| Case | Updated data | Validation |
| --- | --- | --- |
| C111331-307-6a-compliant-attempt | [trace](../../maintenance/demo-core-compatibility-v2/recordings/448b9e51002ded1cd2272962b997fb81b2b695273fa3daf43b34e60f3a5631c5/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/448b9e51002ded1cd2272962b997fb81b2b695273fa3daf43b34e60f3a5631c5/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/448b9e51002ded1cd2272962b997fb81b2b695273fa3daf43b34e60f3a5631c5/receipt.json) | Full Core decoding passes; source facts retained |
| C111331-307-6a-violating-attempt | [trace](../../maintenance/demo-core-compatibility-v2/recordings/fdc101fc90707ec0f7ad2bf1707b1a1c7051b42c1b25bcd04164be21155adac2/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/fdc101fc90707ec0f7ad2bf1707b1a1c7051b42c1b25bcd04164be21155adac2/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/fdc101fc90707ec0f7ad2bf1707b1a1c7051b42c1b25bcd04164be21155adac2/receipt.json) | Full Core decoding passes; source facts retained |
| C111331-yellow-v1-307-6a-entry-before-red | [trace](../../maintenance/demo-core-compatibility-v2/recordings/9ea666feb170d93d84f815f2d8aa8e5c5a899ca24685a7a3c8e51d8102982785/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/9ea666feb170d93d84f815f2d8aa8e5c5a899ca24685a7a3c8e51d8102982785/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/9ea666feb170d93d84f815f2d8aa8e5c5a899ca24685a7a3c8e51d8102982785/receipt.json) | Full Core decoding passes; source facts retained |
| C111331-yellow-v1-307-6a-entry-on-red | [trace](../../maintenance/demo-core-compatibility-v2/recordings/58ba79a576b9c90f39c70f5a7d8aa904dca6c89fcd08e8b27876cb5211ad4267/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/58ba79a576b9c90f39c70f5a7d8aa904dca6c89fcd08e8b27876cb5211ad4267/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/58ba79a576b9c90f39c70f5a7d8aa904dca6c89fcd08e8b27876cb5211ad4267/receipt.json) | Full Core decoding passes; source facts retained |

## Remaining requirements

Accepted videos are retained even when additional requirements remain unfinished. Set scope and coverage dispositions remain authoritative; this migration does not mark an assignment complete.
