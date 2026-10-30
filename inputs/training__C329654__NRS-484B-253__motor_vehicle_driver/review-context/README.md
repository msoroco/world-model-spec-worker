# C329654 / NRS-484B-253

## Law

**NRS-484B-253 — Vehicle turning left**

> The driver of a vehicle within an intersection intending to turn to the left shall yield the right-of-way to any vehicle approaching from the opposite direction which is within the intersection or so close thereto as to constitute an immediate hazard, but such driver, having so yielded and having given a signal when and as required, may make such left turn and the drivers of all other vehicles approaching the intersection from the opposite direction shall yield the right-of-way to the vehicle making the left turn.

## Recording comparisons

Settings below are requested or authored, not measured outcomes. Judgment calls remain unresolved unless the saved metadata supplies an expected label. Videos, traces and metadata are editable review copies; demo links share the corresponding full-set recording directories.

### 253 initial opposing position

Comparison: `C329654-253-initial-opposing-position-v1`.

Earlier retained comparison. The new actual yielding comparison below explicitly includes ego yielding to all, yielding to none, and a farther-back second vehicle that brakes after ego has substantially turned. Braking by an opposing vehicle alone does not establish ego priority.

| Case | Video / data | Test setting | Compared against | Judgment call | Recorded label |
| --- | --- | --- | --- | --- | --- |
| 1 | [video](C329654-253-initial-opposing-position-v1-0000--229e5896ffbd/video.webm) · [trace](C329654-253-initial-opposing-position-v1-0000--229e5896ffbd/trace.json) · [metadata](C329654-253-initial-opposing-position-v1-0000--229e5896ffbd/metadata.json) | Opposing position request: 8 | 2, 3 | having so yielded; immediate hazard | Unresolved (no label assigned) |
| 2 | [video](C329654-253-initial-opposing-position-v1-0001--a5bb1653d46e/video.webm) · [trace](C329654-253-initial-opposing-position-v1-0001--a5bb1653d46e/trace.json) · [metadata](C329654-253-initial-opposing-position-v1-0001--a5bb1653d46e/metadata.json) | Opposing position request: 24 | 1, 3 | having so yielded; immediate hazard | Unresolved (no label assigned) |
| 3 | [video](C329654-253-initial-opposing-position-v1-0002--09f3ecf11630/video.webm) · [trace](C329654-253-initial-opposing-position-v1-0002--09f3ecf11630/trace.json) · [metadata](C329654-253-initial-opposing-position-v1-0002--09f3ecf11630/metadata.json) | Opposing position request: 8 | 1, 2 | having so yielded; immediate hazard | Unresolved (no label assigned) |

Case IDs: 1: `C329654-253-initial-opposing-position-v1-0000`; 2: `C329654-253-initial-opposing-position-v1-0001`; 3: `C329654-253-initial-opposing-position-v1-0002`.

### 253 opposing approach speed

Comparison: `C329654-253-opposing_approach_speed-v1`.

| Case | Video / data | Test setting | Compared against | Judgment call | Recorded label |
| --- | --- | --- | --- | --- | --- |
| 1 | [video](C329654-253-opposing_approach_speed-v1-0000--c677a6e76365/video.webm) · [trace](C329654-253-opposing_approach_speed-v1-0000--c677a6e76365/trace.json) · [metadata](C329654-253-opposing_approach_speed-v1-0000--c677a6e76365/metadata.json) | Opposing-vehicle speed request: 3 m/s | 2 | having so yielded; immediate hazard | Unresolved (no label assigned) |
| 2 | [video](C329654-253-opposing_approach_speed-v1-0001--6784204a0ffd/video.webm) · [trace](C329654-253-opposing_approach_speed-v1-0001--6784204a0ffd/trace.json) · [metadata](C329654-253-opposing_approach_speed-v1-0001--6784204a0ffd/metadata.json) | Opposing-vehicle speed request: 6 m/s | 1 | having so yielded; immediate hazard | Unresolved (no label assigned) |

Case IDs: 1: `C329654-253-opposing_approach_speed-v1-0000`; 2: `C329654-253-opposing_approach_speed-v1-0001`.

### 253 subsequent opposing stream

Comparison: `C329654-253-subsequent_opposing_stream-v1`.

| Case | Video / data | Test setting | Compared against | Judgment call | Recorded label |
| --- | --- | --- | --- | --- | --- |
| 1 | [video](C329654-253-subsequent_opposing_stream-v1-0001--7f144ea3d8b2/video.webm) · [trace](C329654-253-subsequent_opposing_stream-v1-0001--7f144ea3d8b2/trace.json) · [metadata](C329654-253-subsequent_opposing_stream-v1-0001--7f144ea3d8b2/metadata.json) | Opposing stream request: 2 | No accepted counterpart | having so yielded; immediate hazard | Unresolved (no label assigned) |

Case IDs: 1: `C329654-253-subsequent_opposing_stream-v1-0001`.

### Actual yielding sequence and a distant subsequent stream

Comparison: `C329654-review-yield-v3`.

Accepted none/all reference originals retained. The earlier138 m second-vehicle attempt 1005 failed to show braking before ego cleared and is excluded; see the revised comparison below and retained-attempt diagnosis.

| Case | Video / data | Test setting | Compared against | Judgment call | Recorded label |
| --- | --- | --- | --- | --- | --- |
| 1 | [video](C329654-review-yield-v3-0000--62e4c5c46f14/video.webm) · [trace](C329654-review-yield-v3-0000--62e4c5c46f14/trace.json) · [metadata](C329654-review-yield-v3-0000--62e4c5c46f14/metadata.json) | Ego policy: yield_none. Three opposing vehicles; actual commitment, distance, speed and response histories shown. Further initial x positions: [102.672782135, 120.672782135]m.45 s/900 frames. | 2 | immediate hazard; having so yielded | Unresolved (no label assigned) |
| 2 | [video](C329654-review-yield-v3-0001--39dc5cb8f0b2/video.webm) · [trace](C329654-review-yield-v3-0001--39dc5cb8f0b2/trace.json) · [metadata](C329654-review-yield-v3-0001--39dc5cb8f0b2/metadata.json) | Ego policy: yield_all. Three opposing vehicles; actual commitment, distance, speed and response histories shown. Further initial x positions: [102.672782135, 120.672782135]m.45 s/900 frames. | 1 | immediate hazard; having so yielded | Unresolved (no label assigned) |

Case IDs: 1: `C329654-review-yield-v3-0000`; 2: `C329654-review-yield-v3-0001`.

### Actual yielding sequence and a distant subsequent stream

Comparison: `C329654-review-yield-v4`.

Compare ego yielding to no opposing vehicle, yielding until all three opposing vehicles have cleared, and yielding to the initial vehicle with the later stream deliberately farther back. The first two use identical starting positions; the third changes the later positions to132 m/156 m. Actual commitment, every opposing vehicle’s distance and speed, and subsequent braking are annotated and retained. In the far-stream case the second vehicle brakes only after ego is in the latter part of its actual turn. Counterpart accommodation is not proof of ego entitlement. Immediate hazard and having so yielded remain unresolved judgments. All originals 45 s / 900 frames. Version4 explicitly reuses the accepted none/all originals from input revision830d304e; only the changed far original is freshly captured. The failed138 m attempt remains retained, with the late-yield engineering gate unchanged.

| Case | Video / data | Test setting | Compared against | Judgment call | Recorded label |
| --- | --- | --- | --- | --- | --- |
| 1 | [video](C329654-review-yield-v3-0000--62e4c5c46f14/video.webm) · [trace](C329654-review-yield-v3-0000--62e4c5c46f14/trace.json) · [metadata](C329654-review-yield-v3-0000--62e4c5c46f14/metadata.json) | Ego policy: yield none; actual opponents fully clear at commitment: 0 of 3; later initial centers: [102.672782135, 120.672782135]m (reused reference) | 2, 3 | immediate hazard; having so yielded | Unresolved (no label assigned) |
| 2 | [video](C329654-review-yield-v3-0001--39dc5cb8f0b2/video.webm) · [trace](C329654-review-yield-v3-0001--39dc5cb8f0b2/trace.json) · [metadata](C329654-review-yield-v3-0001--39dc5cb8f0b2/metadata.json) | Ego policy: yield all; actual opponents fully clear at commitment: 3 of 3; later initial centers: [102.672782135, 120.672782135]m (reused reference) | 1, 3 | immediate hazard; having so yielded | Unresolved (no label assigned) |
| 3 | [video](C329654-review-yield-v4-0002--8340d3605c28/video.webm) · [trace](C329654-review-yield-v4-0002--8340d3605c28/trace.json) · [metadata](C329654-review-yield-v4-0002--8340d3605c28/metadata.json) | Ego policy: yield initial; actual opponents fully clear at commitment: 1 of 3; later initial centers: [132.0, 156.0]m | 1, 2 | immediate hazard; having so yielded | Unresolved (no label assigned) |

Case IDs: 1: `C329654-review-yield-v3-0000`; 2: `C329654-review-yield-v3-0001`; 3: `C329654-review-yield-v4-0002`.

## Trace compatibility update

Versioned offline traces now pass full Core decoding. Retired source classifications and capabilities remain in typed provenance fields; unsupported legal class membership remains unknown. Original videos, labels and acceptance traces are retained. Unknown entrance associations remain omitted. See the [validation report](../../maintenance/demo-core-compatibility-v2/README.md).

| Case | Updated data | Validation |
| --- | --- | --- |
| C329654-253-initial-opposing-position-v1-0000 | [trace](../../maintenance/demo-core-compatibility-v2/recordings/229e5896ffbd3614cf5abcdedb7286bb515a5fe2c148f7a7f9b8f2c79afcbb4e/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/229e5896ffbd3614cf5abcdedb7286bb515a5fe2c148f7a7f9b8f2c79afcbb4e/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/229e5896ffbd3614cf5abcdedb7286bb515a5fe2c148f7a7f9b8f2c79afcbb4e/receipt.json) | Full Core decoding passes; source facts retained |
| C329654-253-initial-opposing-position-v1-0001 | [trace](../../maintenance/demo-core-compatibility-v2/recordings/a5bb1653d46e3bc3c9e3c032f2222538e7417c8a7955ca2c7fbbbd2643109e37/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/a5bb1653d46e3bc3c9e3c032f2222538e7417c8a7955ca2c7fbbbd2643109e37/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/a5bb1653d46e3bc3c9e3c032f2222538e7417c8a7955ca2c7fbbbd2643109e37/receipt.json) | Full Core decoding passes; source facts retained |
| C329654-253-initial-opposing-position-v1-0002 | [trace](../../maintenance/demo-core-compatibility-v2/recordings/09f3ecf11630f099d116de7b2b32038d0d4ff5ace4e5e22353f9b024da3be0c0/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/09f3ecf11630f099d116de7b2b32038d0d4ff5ace4e5e22353f9b024da3be0c0/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/09f3ecf11630f099d116de7b2b32038d0d4ff5ace4e5e22353f9b024da3be0c0/receipt.json) | Full Core decoding passes; source facts retained |
| C329654-253-subsequent_opposing_stream-v1-0001 | [trace](../../maintenance/demo-core-compatibility-v2/recordings/7f144ea3d8b29882314c30208fef584b13576da80cee1b0aaa7e94852cc1f988/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/7f144ea3d8b29882314c30208fef584b13576da80cee1b0aaa7e94852cc1f988/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/7f144ea3d8b29882314c30208fef584b13576da80cee1b0aaa7e94852cc1f988/receipt.json) | Full Core decoding passes; source facts retained |
| C329654-253-opposing_approach_speed-v1-0000 | [trace](../../maintenance/demo-core-compatibility-v2/recordings/c677a6e76365e14bd8db13c25df527682dc10ac8497869fc16999ff8721f1112/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/c677a6e76365e14bd8db13c25df527682dc10ac8497869fc16999ff8721f1112/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/c677a6e76365e14bd8db13c25df527682dc10ac8497869fc16999ff8721f1112/receipt.json) | Full Core decoding passes; source facts retained |
| C329654-253-opposing_approach_speed-v1-0001 | [trace](../../maintenance/demo-core-compatibility-v2/recordings/6784204a0ffd3ad8aaf4d436cb45c6a7cba5c378f022cf0ce699a1d91d194250/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/6784204a0ffd3ad8aaf4d436cb45c6a7cba5c378f022cf0ce699a1d91d194250/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/6784204a0ffd3ad8aaf4d436cb45c6a7cba5c378f022cf0ce699a1d91d194250/receipt.json) | Full Core decoding passes; source facts retained |
| C329654-review-yield-v3-0000 | [trace](../../maintenance/demo-core-compatibility-v2/recordings/62e4c5c46f14b688226a77ee439954bd84c558e8137c65f14f385a5ff77e8d21/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/62e4c5c46f14b688226a77ee439954bd84c558e8137c65f14f385a5ff77e8d21/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/62e4c5c46f14b688226a77ee439954bd84c558e8137c65f14f385a5ff77e8d21/receipt.json) | Full Core decoding passes; source facts retained |
| C329654-review-yield-v3-0001 | [trace](../../maintenance/demo-core-compatibility-v2/recordings/39dc5cb8f0b25549fbdc61ef21f3f2deea5728e5f31f0cd6d4b510b4a0453c72/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/39dc5cb8f0b25549fbdc61ef21f3f2deea5728e5f31f0cd6d4b510b4a0453c72/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/39dc5cb8f0b25549fbdc61ef21f3f2deea5728e5f31f0cd6d4b510b4a0453c72/receipt.json) | Full Core decoding passes; source facts retained |
| C329654-review-yield-v4-0002 | [trace](../../maintenance/demo-core-compatibility-v2/recordings/8340d3605c2804400d0acd056afb552362d1f1e1ddce3cece3a4222cdb004c1e/trace.json) · [manifest](../../maintenance/demo-core-compatibility-v2/recordings/8340d3605c2804400d0acd056afb552362d1f1e1ddce3cece3a4222cdb004c1e/manifest.json) · [receipt](../../maintenance/demo-core-compatibility-v2/recordings/8340d3605c2804400d0acd056afb552362d1f1e1ddce3cece3a4222cdb004c1e/receipt.json) | Full Core decoding passes; source facts retained |

## Remaining requirements

The requested none/all/revised late-yield comparison is accepted. Failed attempt1005 is retained and excluded from accepted comparison evidence. Immediate hazard and having so yielded remain judgment calls. Broader statutory coverage and inherited pending obligations remain open.
