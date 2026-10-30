# C111277 / NRS-484B-250-4

## Law

**NRS-484B-250-4 — Vehicle approaching or entering intersection (4)**

> When a vehicle enters an intersection controlled by a traffic-control signal which is installed and has its vehicular signals uncovered, but is inoperative at the time the vehicle enters the intersection, the driver of the vehicle shall proceed as if a stop sign had been erected at each entrance to the intersection and shall stop at a clearly marked stop line or, if there is none, before entering the crosswalk on the near side of the intersection or, if there is none, at the point nearest the intersection where the driver has a view of approaching traffic on the through highway. After making such a stop, the driver shall proceed cautiously, yielding to vehicles which have previously completed a stop or are within the intersection.

## Recording comparisons

Settings below are requested or authored, not measured outcomes. Judgment calls remain unresolved unless the saved metadata supplies an expected label. Videos, traces and metadata are editable review copies; demo links share the corresponding full-set recording directories.

### Halt pair

Comparison: `C111277-250-4-halt-pair`.

| Case | Video / data | Test setting | Compared against | Judgment call | Recorded label |
| --- | --- | --- | --- | --- | --- |
| 1 | [video](C111277-250-4-halt--71e2a17317ca/video.webm) · [trace](C111277-250-4-halt--71e2a17317ca/trace.json) · [metadata](C111277-250-4-halt--71e2a17317ca/metadata.json) | Commanded turn path.halt duration rationale: Controller construction setting only; no statutory minimum duration.; Commanded turn path.halt request: Full halt with entire ego footprint before the applicable stop line, then resume the requested scalar speed.; Commanded turn path.verification: Controller support, stopping attainment and route completion remain unverified. | 2 | proceed cautiously | compliant |
| 2 | [video](C111277-250-4-no-halt--bf5ba06672dc/video.webm) · [trace](C111277-250-4-no-halt--bf5ba06672dc/trace.json) · [metadata](C111277-250-4-no-halt--bf5ba06672dc/metadata.json) | Commanded turn path.halt duration rationale: Controller construction setting only; inactive when no halt is requested.; Commanded turn path.halt request: No halt; track the requested scalar speed through the applicable stop line and intersection.; Commanded turn path.verification: Controller support, absence of a realized halt and route completion remain unverified. | 1 | proceed cautiously | violation |

Case IDs: 1: `C111277-250-4-halt`; 2: `C111277-250-4-no-halt`.

## Trace compatibility update

Versioned offline traces now pass full Core decoding. Retired source classifications and capabilities remain in typed provenance fields; unsupported legal class membership remains unknown. Original videos, labels and acceptance traces are retained. Unknown entrance associations remain omitted. See the [validation report](../../maintenance/demo-core-compatibility-v2/README.md).

| Case | Updated data | Validation |
| --- | --- | --- |
| C111277-250-4-halt | [trace](../../maintenance/demo-core-compatibility-v2/recordings/71e2a17317ca3939443478c3b1ad45428c384ce7b7abfe13c3725d2082e19ef0/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/71e2a17317ca3939443478c3b1ad45428c384ce7b7abfe13c3725d2082e19ef0/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/71e2a17317ca3939443478c3b1ad45428c384ce7b7abfe13c3725d2082e19ef0/receipt.json) | Full Core decoding passes; source facts retained |
| C111277-250-4-no-halt | [trace](../../maintenance/demo-core-compatibility-v2/recordings/bf5ba06672dcf57a53cafeddaeb2a88af996036ca014b35c66178a7a612d0d99/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/bf5ba06672dcf57a53cafeddaeb2a88af996036ca014b35c66178a7a612d0d99/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/bf5ba06672dcf57a53cafeddaeb2a88af996036ca014b35c66178a7a612d0d99/receipt.json) | Full Core decoding passes; source facts retained |

## Remaining requirements

Accepted videos are retained even when additional requirements remain unfinished. Set scope and coverage dispositions remain authoritative; this migration does not mark an assignment complete.
