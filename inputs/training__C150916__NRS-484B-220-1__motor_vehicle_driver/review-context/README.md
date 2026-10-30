# C150916 / NRS-484B-220-1

## Law

**NRS-484B-220-1 — One-way highway (1)**

> Upon a highway designated and signposted for one-way traffic a vehicle shall be driven only in the direction designated.

## Recording comparisons

Settings below are requested or authored, not measured outcomes. Judgment calls remain unresolved unless the saved metadata supplies an expected label. Videos, traces and metadata are editable review copies; demo links share the corresponding full-set recording directories.

### Direction pair

Comparison: `C150916-220-1-direction-pair`.

| Case | Video / data | Test setting | Compared against | Judgment call | Recorded label |
| --- | --- | --- | --- | --- | --- |
| 1 | [video](C150916-220-1-compliant--968996df2771/video.webm) · [trace](C150916-220-1-compliant--968996df2771/trace.json) · [metadata](C150916-220-1-compliant--968996df2771/metadata.json) | Commanded turn path.initial position xy m: [62, 28.356]; Commanded turn path.route xy m: [[62, 28.356], [77, 28.398]] | 2 | None listed | compliant |
| 2 | [video](C150916-220-1-violating--46d0a7663615/video.webm) · [trace](C150916-220-1-violating--46d0a7663615/trace.json) · [metadata](C150916-220-1-violating--46d0a7663615/metadata.json) | Commanded turn path.initial position xy m: [77, 28.398]; Commanded turn path.route xy m: [[77, 28.398], [62, 28.356]] | 1 | None listed | violation |

Case IDs: 1: `C150916-220-1-compliant`; 2: `C150916-220-1-violating`.

### One way

Comparison: `C150916-one-way-v1-direction-pair`.

| Case | Video / data | Test setting | Compared against | Judgment call | Recorded label |
| --- | --- | --- | --- | --- | --- |
| 1 | [video](C150916-one-way-v1-220-1-correct--e3b7092ebb91/video.webm) · [trace](C150916-one-way-v1-220-1-correct--e3b7092ebb91/trace.json) · [metadata](C150916-one-way-v1-220-1-correct--e3b7092ebb91/metadata.json) | Commanded turn path.brake onset x m: -5; Commanded turn path.initial heading deg: 0; Commanded turn path.travel direction native xy: [1, 0] | 2 | None listed | compliant |
| 2 | [video](C150916-one-way-v1-220-1-wrong--d58b55994437/video.webm) · [trace](C150916-one-way-v1-220-1-wrong--d58b55994437/trace.json) · [metadata](C150916-one-way-v1-220-1-wrong--d58b55994437/metadata.json) | Commanded turn path.brake onset x m: -45; Commanded turn path.initial heading deg: 180; Commanded turn path.travel direction native xy: [-1, 0] | 1 | None listed | violation |

Case IDs: 1: `C150916-one-way-v1-220-1-correct`; 2: `C150916-one-way-v1-220-1-wrong`.

## Trace compatibility update

Versioned offline traces now pass full Core decoding. Retired source classifications and capabilities remain in typed provenance fields; unsupported legal class membership remains unknown. Original videos, labels and acceptance traces are retained. Unknown entrance associations remain omitted. See the [validation report](../../maintenance/demo-core-compatibility-v2/README.md).

| Case | Updated data | Validation |
| --- | --- | --- |
| C150916-220-1-compliant | [trace](../../maintenance/demo-core-compatibility-v2/recordings/968996df2771ab3fec2d055654f963418dde77e05074e51a3c8fe5fcc4fb7c49/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/968996df2771ab3fec2d055654f963418dde77e05074e51a3c8fe5fcc4fb7c49/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/968996df2771ab3fec2d055654f963418dde77e05074e51a3c8fe5fcc4fb7c49/receipt.json) | Full Core decoding passes; source facts retained |
| C150916-220-1-violating | [trace](../../maintenance/demo-core-compatibility-v2/recordings/46d0a7663615b6a98839dcc7fa3fd29591f52a0bd3a21ac7b0c4f61a6f2abc61/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/46d0a7663615b6a98839dcc7fa3fd29591f52a0bd3a21ac7b0c4f61a6f2abc61/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/46d0a7663615b6a98839dcc7fa3fd29591f52a0bd3a21ac7b0c4f61a6f2abc61/receipt.json) | Full Core decoding passes; source facts retained |
| C150916-one-way-v1-220-1-correct | [trace](../../maintenance/demo-core-compatibility-v2/recordings/e3b7092ebb919b565c0faf379093e6eec86c7c3d201b5a76117e78edb142f110/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/e3b7092ebb919b565c0faf379093e6eec86c7c3d201b5a76117e78edb142f110/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/e3b7092ebb919b565c0faf379093e6eec86c7c3d201b5a76117e78edb142f110/receipt.json) | Full Core decoding passes; source facts retained |
| C150916-one-way-v1-220-1-wrong | [trace](../../maintenance/demo-core-compatibility-v2/recordings/d58b559944374154b1b2fcc8cc5c27c9163076e4c4304e431065df2344cf0ad4/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/d58b559944374154b1b2fcc8cc5c27c9163076e4c4304e431065df2344cf0ad4/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/d58b559944374154b1b2fcc8cc5c27c9163076e4c4304e431065df2344cf0ad4/receipt.json) | Full Core decoding passes; source facts retained |

## Remaining requirements

The entire road x=-60..+60 m is designated one-way toward +x. The physical sign at x=-12 m is inside that region, not its start. Wrong-direction travel is assessed only while the vehicle occupies that region. A saved-video governance overlay is pending.
