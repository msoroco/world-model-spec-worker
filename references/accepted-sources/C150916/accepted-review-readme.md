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
| 1 | [video](C150916-220-1-compliant--968996df2771/video.webm) · [trace](C150916-220-1-compliant--968996df2771/trace.json) · [metadata](C150916-220-1-compliant--968996df2771/metadata.json) | Commanded turn path.initial position xy m: [62, 28.356]; Commanded turn path.route xy m: [[62, 28.356], [77, 28.398]] | 2 | None listed | Compliant (`compliant`) |
| 2 | [video](C150916-220-1-violating--46d0a7663615/video.webm) · [trace](C150916-220-1-violating--46d0a7663615/trace.json) · [metadata](C150916-220-1-violating--46d0a7663615/metadata.json) | Commanded turn path.initial position xy m: [77, 28.398]; Commanded turn path.route xy m: [[77, 28.398], [62, 28.356]] | 1 | None listed | Violation (`non_compliant`) |

Case IDs: 1: `C150916-220-1-compliant`; 2: `C150916-220-1-violating`.

### One way

Comparison: `C150916-one-way-v1-direction-pair`.

| Case | Video / data | Test setting | Compared against | Judgment call | Recorded label |
| --- | --- | --- | --- | --- | --- |
| 1 | [video](C150916-one-way-v1-220-1-correct--e3b7092ebb91/video.webm) · [trace](C150916-one-way-v1-220-1-correct--e3b7092ebb91/trace.json) · [metadata](C150916-one-way-v1-220-1-correct--e3b7092ebb91/metadata.json) | Commanded turn path.brake onset x m: 5; Commanded turn path.initial heading deg: 0; Commanded turn path.travel direction native xy: [1, 0] | 2 | None listed | Compliant (`compliant`) |
| 2 | [video](C150916-one-way-v1-220-1-wrong--d58b55994437/video.webm) · [trace](C150916-one-way-v1-220-1-wrong--d58b55994437/trace.json) · [metadata](C150916-one-way-v1-220-1-wrong--d58b55994437/metadata.json) | Commanded turn path.brake onset x m: 45; Commanded turn path.initial heading deg: 180; Commanded turn path.travel direction native xy: [-1, 0] | 1 | None listed | Violation (`violation`) |

Case IDs: 1: `C150916-one-way-v1-220-1-correct`; 2: `C150916-one-way-v1-220-1-wrong`.

## Remaining requirements

Accepted videos are retained even when additional requirements remain unfinished. Set scope and coverage dispositions remain authoritative; this migration does not mark an assignment complete.
