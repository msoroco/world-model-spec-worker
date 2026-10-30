# C111325 / NRS-484B-257-1

## Law

**NRS-484B-257-1 — Vehicle entering intersection marked stop or yield (1)**

> Except when traffic is being controlled by a police officer or a traffic-control signal: When proper signs have been erected, the driver of a vehicle shall stop or yield at a clearly marked stop line or, if there is none, before entering the crosswalk on the near side of the intersection or, if there is none, then at the point nearest the intersection where the driver has a view of approaching traffic on the through highway. After having stopped or, in the event of a yield sign, slowed or stopped, the driver shall yield the right-of-way to other vehicles which have entered the intersection from such through highway or which are approaching so closely on such through highway as to constitute an immediate hazard during the time such driver is moving across or within the intersection.

## Recording comparisons

Settings below are requested or authored, not measured outcomes. Judgment calls remain unresolved unless the saved metadata supplies an expected label. Videos, traces and metadata are editable review copies; demo links share the corresponding full-set recording directories.

### Labeling convention

Only the four Stopping reference cases are relabeled here. Each is Compliant under the frozen synthetic public-highway, properly authorized sign and through-highway assumptions: measured zero velocity before the applicable reference, followed by waiting for the initial through vehicle to clear. The further vehicle remains outside the intersection during the subject crossing. Its programmed braking is not, by itself, evidence that the subject yielded; the annotation also checks measured separation and a constant-current-speed arrival projection throughout the crossing. This projection is explanatory evidence, not a statutory numerical immediate-hazard threshold. For case 4, the review judgment treats the last safe approach boundary, with the vehicle front approximately 0.044 m upstream and sampled modeled visibility of at least 200 m on the incoming approaches, as the nearest practical stopping point with a view. This is an explicit scenario judgment; the source geometry identifies a candidate and does not independently establish a legal nearest point or human perception. Original automated inconclusive assessments remain in review_label_history. The other comparisons are unchanged.

### Stop action

Comparison: `C111325-257-1-stop-action-v1`.

| Case | Video / data | Test setting | Compared against | Judgment call | Recorded label |
| --- | --- | --- | --- | --- | --- |
| 1 | [video](C111325-257-1-stop-action-v1-0000--21692e9139d1/video.webm) · [trace](C111325-257-1-stop-action-v1-0000--21692e9139d1/trace.json) · [metadata](C111325-257-1-stop-action-v1-0000--21692e9139d1/metadata.json) | Stop action speed request: 0 | 2 | immediate hazard; yield the right-of-way | Unresolved (no label assigned) |
| 2 | [video](C111325-257-1-stop-action-v1-0001--52bf0dfd7ff0/video.webm) · [trace](C111325-257-1-stop-action-v1-0001--52bf0dfd7ff0/trace.json) · [metadata](C111325-257-1-stop-action-v1-0001--52bf0dfd7ff0/metadata.json) | Stop action speed request: 0.5 | 1 | Objective STOP failure establishes violation; other hazard/yield judgments unresolved | violation |

Case IDs: 1: `C111325-257-1-stop-action-v1-0000`; 2: `C111325-257-1-stop-action-v1-0001`.

### Stopping reference

Comparison: `C111325-257-1-stopping-reference-v1`.

| Case | Video / data | Test setting | Compared against | Judgment call | Recorded label |
| --- | --- | --- | --- | --- | --- |
| 1 | [video](C111325-257-1-stopping-reference-v1-0000--5d966076438f/video.webm) · [trace](C111325-257-1-stopping-reference-v1-0000--5d966076438f/trace.json) · [metadata](C111325-257-1-stopping-reference-v1-0000--5d966076438f/metadata.json) | Front-to-reference margin request: 0.3 m; Stopping reference geometry: stop sign marked line | 2, 3, 4 | Stop position and yielding evaluated | compliant |
| 2 | [video](C111325-257-1-stopping-reference-v1-0001--31e8b61e5e17/video.webm) · [trace](C111325-257-1-stopping-reference-v1-0001--31e8b61e5e17/trace.json) · [metadata](C111325-257-1-stopping-reference-v1-0001--31e8b61e5e17/metadata.json) | Front-to-reference margin request: 0.3 m; Stopping reference geometry: no line marked near side crosswalk | 1, 3, 4 | Stop position and yielding evaluated | compliant |
| 3 | [video](C111325-257-1-stopping-reference-v1-0002--033688c91578/video.webm) · [trace](C111325-257-1-stopping-reference-v1-0002--033688c91578/trace.json) · [metadata](C111325-257-1-stopping-reference-v1-0002--033688c91578/metadata.json) | Front-to-reference margin request: 0.3 m; Stopping reference geometry: no line unmarked sidewalk connection crosswalk | 1, 2, 4 | Stop position and yielding evaluated | compliant |
| 4 | [video](C111325-257-1-stopping-reference-v1-0003--820a47e943d7/video.webm) · [trace](C111325-257-1-stopping-reference-v1-0003--820a47e943d7/trace.json) · [metadata](C111325-257-1-stopping-reference-v1-0003--820a47e943d7/metadata.json) | Front-to-reference margin request: 0 m; Stopping reference geometry: neither line nor crosswalk nearest viewpoint candidate | 1, 2, 3 | Stop position and yielding evaluated; modeled nearest safe viewpoint accepted | compliant |

Case IDs: 1: `C111325-257-1-stopping-reference-v1-0000`; 2: `C111325-257-1-stopping-reference-v1-0001`; 3: `C111325-257-1-stopping-reference-v1-0002`; 4: `C111325-257-1-stopping-reference-v1-0003`.

### Through traffic phase

Comparison: `C111325-257-1-through-traffic-phase-v1`.

| Case | Video / data | Test setting | Compared against | Judgment call | Recorded label |
| --- | --- | --- | --- | --- | --- |
| 1 | [video](C111325-257-1-through-traffic-phase-v1-0000--03b83a6ce89e/video.webm) · [trace](C111325-257-1-through-traffic-phase-v1-0000--03b83a6ce89e/trace.json) · [metadata](C111325-257-1-through-traffic-phase-v1-0000--03b83a6ce89e/metadata.json) | Through position request: 0 | 2, 3 | immediate hazard; yield the right-of-way | Unresolved (no label assigned) |
| 2 | [video](C111325-257-1-through-traffic-phase-v1-0001--5e032bf8c9bf/video.webm) · [trace](C111325-257-1-through-traffic-phase-v1-0001--5e032bf8c9bf/trace.json) · [metadata](C111325-257-1-through-traffic-phase-v1-0001--5e032bf8c9bf/metadata.json) | Through position request: 40 | 1, 3 | immediate hazard; yield the right-of-way | Unresolved (no label assigned) |
| 3 | [video](C111325-257-1-through-traffic-phase-v1-0002--d8fcca221385/video.webm) · [trace](C111325-257-1-through-traffic-phase-v1-0002--d8fcca221385/trace.json) · [metadata](C111325-257-1-through-traffic-phase-v1-0002--d8fcca221385/metadata.json) | Through position request: 20 | 1, 2 | immediate hazard; yield the right-of-way | Unresolved (no label assigned) |

Case IDs: 1: `C111325-257-1-through-traffic-phase-v1-0000`; 2: `C111325-257-1-through-traffic-phase-v1-0001`; 3: `C111325-257-1-through-traffic-phase-v1-0002`.

## Trace compatibility update

Versioned offline traces now pass full Core decoding. Retired source classifications and capabilities remain in typed provenance fields; unsupported legal class membership remains unknown. Original videos, labels and acceptance traces are retained. Unknown entrance associations remain omitted. See the [validation report](../../maintenance/demo-core-compatibility-v2/README.md).

| Case | Updated data | Validation |
| --- | --- | --- |
| C111325-257-1-through-traffic-phase-v1-0000 | [trace](../../maintenance/demo-core-compatibility-v2/recordings/03b83a6ce89e810c83a12eb7a6ba6fdf8b85242eb65deee6e3699a98494dda22/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/03b83a6ce89e810c83a12eb7a6ba6fdf8b85242eb65deee6e3699a98494dda22/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/03b83a6ce89e810c83a12eb7a6ba6fdf8b85242eb65deee6e3699a98494dda22/receipt.json) | Full Core decoding passes; source facts retained |
| C111325-257-1-through-traffic-phase-v1-0001 | [trace](../../maintenance/demo-core-compatibility-v2/recordings/5e032bf8c9bf21adffe606372d9e3b03f5208129529592f305f402bf30c511ee/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/5e032bf8c9bf21adffe606372d9e3b03f5208129529592f305f402bf30c511ee/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/5e032bf8c9bf21adffe606372d9e3b03f5208129529592f305f402bf30c511ee/receipt.json) | Full Core decoding passes; source facts retained |
| C111325-257-1-through-traffic-phase-v1-0002 | [trace](../../maintenance/demo-core-compatibility-v2/recordings/d8fcca221385aacdabfa0b395398fba76cf3a006693ef62cf72e9ed0f679458b/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/d8fcca221385aacdabfa0b395398fba76cf3a006693ef62cf72e9ed0f679458b/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/d8fcca221385aacdabfa0b395398fba76cf3a006693ef62cf72e9ed0f679458b/receipt.json) | Full Core decoding passes; source facts retained |
| C111325-257-1-stop-action-v1-0000 | [trace](../../maintenance/demo-core-compatibility-v2/recordings/21692e9139d199228875a01ce2b72ce43ec9f2e628cf2036764cd7f887e36be6/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/21692e9139d199228875a01ce2b72ce43ec9f2e628cf2036764cd7f887e36be6/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/21692e9139d199228875a01ce2b72ce43ec9f2e628cf2036764cd7f887e36be6/receipt.json) | Full Core decoding passes; source facts retained |
| C111325-257-1-stop-action-v1-0001 | [trace](../../maintenance/demo-core-compatibility-v2/recordings/52bf0dfd7ff0def949dbdf66715235e33ff79609fe6745cf69706b816b102752/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/52bf0dfd7ff0def949dbdf66715235e33ff79609fe6745cf69706b816b102752/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/52bf0dfd7ff0def949dbdf66715235e33ff79609fe6745cf69706b816b102752/receipt.json) | Full Core decoding passes; source facts retained |
| C111325-257-1-stopping-reference-v1-0000 | [trace](../../maintenance/demo-core-compatibility-v2/recordings/5d966076438ff2b8b4ab3700af49d5f0790b5b3785404744f09a2abc80ffbd59/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/5d966076438ff2b8b4ab3700af49d5f0790b5b3785404744f09a2abc80ffbd59/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/5d966076438ff2b8b4ab3700af49d5f0790b5b3785404744f09a2abc80ffbd59/receipt.json) | Full Core decoding passes; source facts retained |
| C111325-257-1-stopping-reference-v1-0001 | [trace](../../maintenance/demo-core-compatibility-v2/recordings/31e8b61e5e17894d633ecc42ded767f64a3a7a9c33665d6a99cf8312224737db/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/31e8b61e5e17894d633ecc42ded767f64a3a7a9c33665d6a99cf8312224737db/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/31e8b61e5e17894d633ecc42ded767f64a3a7a9c33665d6a99cf8312224737db/receipt.json) | Full Core decoding passes; source facts retained |
| C111325-257-1-stopping-reference-v1-0002 | [trace](../../maintenance/demo-core-compatibility-v2/recordings/033688c91578b0beefb734cb87da1ca186e1a833c1193bc8cb3a7015a74432bb/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/033688c91578b0beefb734cb87da1ca186e1a833c1193bc8cb3a7015a74432bb/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/033688c91578b0beefb734cb87da1ca186e1a833c1193bc8cb3a7015a74432bb/receipt.json) | Full Core decoding passes; source facts retained |
| C111325-257-1-stopping-reference-v1-0003 | [trace](../../maintenance/demo-core-compatibility-v2/recordings/820a47e943d714d83271d9acde43a5bb0ca8d6beb42bb2352c5174a58bdc7b1d/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/820a47e943d714d83271d9acde43a5bb0ca8d6beb42bb2352c5174a58bdc7b1d/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/820a47e943d714d83271d9acde43a5bb0ca8d6beb42bb2352c5174a58bdc7b1d/receipt.json) | Full Core decoding passes; source facts retained |

## Remaining requirements

Accepted videos are retained even when additional requirements remain unfinished. Set scope and coverage dispositions remain authoritative; this migration does not mark an assignment complete.
