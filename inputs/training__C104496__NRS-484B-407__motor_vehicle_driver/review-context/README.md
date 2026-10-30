# C104496 / NRS-484B-407

## Law

**NRS-484B-407 — Turning on curve or crest of grade prohibited in certain circumstances**

> A vehicle shall not be turned so as to proceed in the opposite direction upon any curve, or upon the approach to or near the crest of a grade, where such vehicle cannot be seen by the driver of any other vehicle approaching from either direction within 500 feet.

## Recording comparisons

Settings below are requested or authored, not measured outcomes. Judgment calls remain unresolved unless the saved metadata supplies an expected label. Videos, traces and metadata are editable review copies; demo links share the corresponding full-set recording directories.

### Labeling convention

For these three crest cases, the crest context is established by the surveyed geometry and the completed audit; no numerical “near the crest” cutoff is applied. During the recorded reversal, a direction is geometrically visible at 500 ft (152.4 m along its incoming lane) when any of nine actual body samples has a clear ray. A blocked approach during the reversal supports the expected violation label under this convention. These are sampled evidence-backed scenario labels, not an independently executed legal formalization.

### 407 crest placement

Comparison: `C104496-407-crest-placement-v1`.

| Case | Video / data | Test setting | Compared against | Judgment call | Recorded label |
| --- | --- | --- | --- | --- | --- |
| 1 | [video](C104496-407-crest-placement-v1-0000--2f54584cf7d8/video.webm) · [trace](C104496-407-crest-placement-v1-0000--2f54584cf7d8/trace.json) · [metadata](C104496-407-crest-placement-v1-0000--2f54584cf7d8/metadata.json) | Maneuver station: 700 | 2, 3 | Crest context established; full-turn visibility evaluated | violation |
| 2 | [video](C104496-407-crest-placement-v1-0001--239be3041c40/video.webm) · [trace](C104496-407-crest-placement-v1-0001--239be3041c40/trace.json) · [metadata](C104496-407-crest-placement-v1-0001--239be3041c40/metadata.json) | Maneuver station: 800 | 1, 3 | Crest context established; full-turn visibility evaluated | violation |
| 3 | [video](C104496-407-crest-placement-v1-0002--fe7841a28ace/video.webm) · [trace](C104496-407-crest-placement-v1-0002--fe7841a28ace/trace.json) · [metadata](C104496-407-crest-placement-v1-0002--fe7841a28ace/metadata.json) | Maneuver station: 750 | 1, 2 | Crest context established; full-turn visibility evaluated | violation |

Case IDs: 1: `C104496-407-crest-placement-v1-0000`; 2: `C104496-407-crest-placement-v1-0001`; 3: `C104496-407-crest-placement-v1-0002`.

### Compliant crest U-turn: visible from both directions

Comparison: `C104496-review-visible-crest-v1`.

Added compliant crest branch under the declared geometric visibility convention: a genuine grade crest, actual three-point reversal, and positive subject-body visibility from both incoming lane positions beyond 500 ft throughout the maneuver. The two approach views are virtual cameras; there is one physical approaching vehicle. Original pixels and 4× nearest-neighbor magnifiers are retained. The shallower 0.008 grade differs from earlier fixtures, so this is an additional branch rather than a matched one-variable comparison. Human recognition is not established; the unresolved meaning of near is not exercised because the visibility precondition is false.

| Case | Video / data | Test setting | Compared against | Judgment call | Recorded label |
| --- | --- | --- | --- | --- | --- |
| 1 | [video](C104496-review-visible-crest-v1-0000--934d6ab479b4/video.webm) · [trace](C104496-review-visible-crest-v1-0000--934d6ab479b4/trace.json) · [metadata](C104496-review-visible-crest-v1-0000--934d6ab479b4/metadata.json) | Actual three-point U-turn on a genuine crest. Both incoming-lane views identify the subject beyond 500 ft throughout the completed maneuver; original body-ray evidence retained. Grade0.008,35 s/700 frames. | No accepted counterpart | None listed | compliant |

Case IDs: 1: `C104496-review-visible-crest-v1-0000`.

## Trace compatibility update

Versioned offline traces now pass full Core decoding. Retired source classifications and capabilities remain in typed provenance fields; unsupported legal class membership remains unknown. Original videos, labels and acceptance traces are retained. Unknown entrance associations remain omitted. See the [validation report](../../maintenance/demo-core-compatibility-v2/README.md).

| Case | Updated data | Validation |
| --- | --- | --- |
| C104496-407-crest-placement-v1-0000 | [trace](../../maintenance/demo-core-compatibility-v2/recordings/2f54584cf7d8d3b1c14af61ce0a9b45118c7a3d88cfe0d68b62824e2f15ecd84/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/2f54584cf7d8d3b1c14af61ce0a9b45118c7a3d88cfe0d68b62824e2f15ecd84/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/2f54584cf7d8d3b1c14af61ce0a9b45118c7a3d88cfe0d68b62824e2f15ecd84/receipt.json) | Full Core decoding passes; source facts retained |
| C104496-407-crest-placement-v1-0001 | [trace](../../maintenance/demo-core-compatibility-v2/recordings/239be3041c40523964a01b64665843c15ca988906507330d750e91882045ce47/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/239be3041c40523964a01b64665843c15ca988906507330d750e91882045ce47/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/239be3041c40523964a01b64665843c15ca988906507330d750e91882045ce47/receipt.json) | Full Core decoding passes; source facts retained |
| C104496-407-crest-placement-v1-0002 | [trace](../../maintenance/demo-core-compatibility-v2/recordings/fe7841a28ace1414610d7aab0ea5fa68d0f76336944363f39b837dd601071741/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/fe7841a28ace1414610d7aab0ea5fa68d0f76336944363f39b837dd601071741/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/fe7841a28ace1414610d7aab0ea5fa68d0f76336944363f39b837dd601071741/receipt.json) | Full Core decoding passes; source facts retained |
| C104496-review-visible-crest-v1-0000 | [trace](../../maintenance/demo-core-compatibility-v2/recordings/934d6ab479b41fbd4220394c03bf72e94bb406bd77bd9604ca512dea93c4e3f5/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/934d6ab479b41fbd4220394c03bf72e94bb406bd77bd9604ca512dea93c4e3f5/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/934d6ab479b41fbd4220394c03bf72e94bb406bd77bd9604ca512dea93c4e3f5/receipt.json) | Full Core decoding passes; source facts retained |

## Remaining requirements

The three selected crest-placement cases are complete for the reviewed recording assignment, as established by the completion audit. Under the stated visibility convention all three are expected violations; this group has no compliant contrast. Broader curve-branch coverage and additional unselected definitions are separate from this completed assignment.
