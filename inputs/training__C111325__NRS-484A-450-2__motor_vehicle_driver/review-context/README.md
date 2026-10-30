# C111325 / NRS-484A-450-2

## Law

**NRS-484A-450-2 — Designation of through highways and intersections requiring stop or yield (2)**

> Every driver of a vehicle approaching a stop intersection indicated by a stop sign shall stop before entering the crosswalk on the near side of the intersection or, if there is no crosswalk, shall stop at a clearly marked stop line, or if none, then at the point nearest the intersecting highway where the driver has a view of approaching traffic on the intersecting highway before entering the intersection.

## Recording comparisons

Settings below are requested or authored, not measured outcomes. Judgment calls remain unresolved unless the saved metadata supplies an expected label. Videos, traces and metadata are editable review copies; demo links share the corresponding full-set recording directories.

### Halt pair

Comparison: `C111325-450-2-halt-pair`.

| Case | Video / data | Test setting | Compared against | Judgment call | Recorded label |
| --- | --- | --- | --- | --- | --- |
| 1 | [video](C111325-450-2-halt-compliant-attempt--8b66dc711065/video.webm) · [trace](C111325-450-2-halt-compliant-attempt--8b66dc711065/trace.json) · [metadata](C111325-450-2-halt-compliant-attempt--8b66dc711065/metadata.json) | Commanded turn path.stop request: halt at applicable reference | 2 | clearly marked stop line; where the driver has a view of approaching traffic on the intersecting highway | compliant |
| 2 | [video](C111325-450-2-halt-violating-attempt--f82eb9859f57/video.webm) · [trace](C111325-450-2-halt-violating-attempt--f82eb9859f57/trace.json) · [metadata](C111325-450-2-halt-violating-attempt--f82eb9859f57/metadata.json) | Commanded turn path.stop request: omit approach halt | 1 | clearly marked stop line; where the driver has a view of approaching traffic on the intersecting highway | violation |

Case IDs: 1: `C111325-450-2-halt-compliant-attempt`; 2: `C111325-450-2-halt-violating-attempt`.

### Crosswalk

Comparison: `C111325-crosswalk-v1-stop-pair`.

| Case | Video / data | Test setting | Compared against | Judgment call | Recorded label |
| --- | --- | --- | --- | --- | --- |
| 1 | [video](C111325-crosswalk-v1-450-2-no-stop--cc58ed7ec5ab/video.webm) · [trace](C111325-crosswalk-v1-450-2-no-stop--cc58ed7ec5ab/trace.json) · [metadata](C111325-crosswalk-v1-450-2-no-stop--cc58ed7ec5ab/metadata.json) | Commanded turn path.stop before crosswalk: false | 2 | clearly marked stop line; where the driver has a view of approaching traffic on the intersecting highway | violation |
| 2 | [video](C111325-crosswalk-v1-450-2-stop--1d44f472c13b/video.webm) · [trace](C111325-crosswalk-v1-450-2-stop--1d44f472c13b/trace.json) · [metadata](C111325-crosswalk-v1-450-2-stop--1d44f472c13b/metadata.json) | Commanded turn path.stop before crosswalk: true | 1 | clearly marked stop line; where the driver has a view of approaching traffic on the intersecting highway | compliant |

Case IDs: 1: `C111325-crosswalk-v1-450-2-no-stop`; 2: `C111325-crosswalk-v1-450-2-stop`.

## Trace compatibility update

Versioned offline traces now pass full Core decoding. Retired source classifications and capabilities remain in typed provenance fields; unsupported legal class membership remains unknown. Original videos, labels and acceptance traces are retained. Unknown entrance associations remain omitted. See the [validation report](../../maintenance/demo-core-compatibility-v2/README.md).

| Case | Updated data | Validation |
| --- | --- | --- |
| C111325-450-2-halt-compliant-attempt | [trace](../../maintenance/demo-core-compatibility-v2/recordings/8b66dc7110651355664b44be213e621f4447b0bea996732725d583ecf47f284e/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/8b66dc7110651355664b44be213e621f4447b0bea996732725d583ecf47f284e/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/8b66dc7110651355664b44be213e621f4447b0bea996732725d583ecf47f284e/receipt.json) | Full Core decoding passes; source facts retained |
| C111325-450-2-halt-violating-attempt | [trace](../../maintenance/demo-core-compatibility-v2/recordings/f82eb9859f5705429c4cdf17b2872854069ff4692a20870cba4010e5e7e26530/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/f82eb9859f5705429c4cdf17b2872854069ff4692a20870cba4010e5e7e26530/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/f82eb9859f5705429c4cdf17b2872854069ff4692a20870cba4010e5e7e26530/receipt.json) | Full Core decoding passes; source facts retained |
| C111325-crosswalk-v1-450-2-no-stop | [trace](../../maintenance/demo-core-compatibility-v2/recordings/cc58ed7ec5ab3e21578eab4293638d2a2aa23cc90b3e46b38b026d61991846e7/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/cc58ed7ec5ab3e21578eab4293638d2a2aa23cc90b3e46b38b026d61991846e7/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/cc58ed7ec5ab3e21578eab4293638d2a2aa23cc90b3e46b38b026d61991846e7/receipt.json) | Full Core decoding passes; source facts retained |
| C111325-crosswalk-v1-450-2-stop | [trace](../../maintenance/demo-core-compatibility-v2/recordings/1d44f472c13b303e2b4691b2e7348e3a20ce0c53fefbc704f95d064c5984f78e/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/1d44f472c13b303e2b4691b2e7348e3a20ce0c53fefbc704f95d064c5984f78e/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/1d44f472c13b303e2b4691b2e7348e3a20ce0c53fefbc704f95d064c5984f78e/receipt.json) | Full Core decoding passes; source facts retained |

## Remaining requirements

Accepted videos are retained even when additional requirements remain unfinished. Set scope and coverage dispositions remain authoritative; this migration does not mark an assignment complete.
