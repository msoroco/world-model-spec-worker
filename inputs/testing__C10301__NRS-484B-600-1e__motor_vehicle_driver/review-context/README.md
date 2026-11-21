# C10301 / NRS-484B-600-1e

## Law

**NRS-484B-600-1e — Absolute speed threshold**

> Source text retained in the imported delivery package; legal judgment remains unresolved.

## Recording comparisons

Settings below are requested or authored, not measured outcomes. Judgment calls remain unresolved unless the saved metadata supplies an expected label. Videos, traces and metadata are editable review copies; demo links share the corresponding full-set recording directories.

### Imported delivery cases

Comparison: `strict_rate_boundary`.

| Case | Video / data | Test setting | Compared against | Judgment call | Recorded label |
| --- | --- | --- | --- | --- | --- |
| 1 | [video](testing__C10301__NRS-484B-600-1e__motor_vehicle_driver__below--d40367aa09c6/video.webm) · [trace](testing__C10301__NRS-484B-600-1e__motor_vehicle_driver__below--d40367aa09c6/trace.json) · [metadata](testing__C10301__NRS-484B-600-1e__motor_vehicle_driver__below--d40367aa09c6/metadata.json) · [manifest](testing__C10301__NRS-484B-600-1e__motor_vehicle_driver__below--d40367aa09c6/manifest.json) | Below threshold; Native 45-second recording, 900 samples, maximum sampled speed 74.95 mph. | 2, 3 | Synthetic road public-way status and between-sample speed peaks remain unresolved | Unresolved (no label assigned) |
| 2 | [video](testing__C10301__NRS-484B-600-1e__motor_vehicle_driver__equal--c76134bfaae4/video.webm) · [trace](testing__C10301__NRS-484B-600-1e__motor_vehicle_driver__equal--c76134bfaae4/trace.json) · [metadata](testing__C10301__NRS-484B-600-1e__motor_vehicle_driver__equal--c76134bfaae4/metadata.json) · [manifest](testing__C10301__NRS-484B-600-1e__motor_vehicle_driver__equal--c76134bfaae4/manifest.json) | Requested 80 mph equality probe; Native 45-second recording, 900 samples, maximum sampled speed 79.73 mph. Controller repair after a 75.92 mph physical mismatch. | 1, 3 | Exact equality at 80 mph, between-sample peaks, and synthetic road public-way status remain unresolved | Unresolved (no label assigned) |
| 3 | [video](testing__C10301__NRS-484B-600-1e__motor_vehicle_driver__above--94949cafef78/video.webm) · [trace](testing__C10301__NRS-484B-600-1e__motor_vehicle_driver__above--94949cafef78/trace.json) · [metadata](testing__C10301__NRS-484B-600-1e__motor_vehicle_driver__above--94949cafef78/metadata.json) · [manifest](testing__C10301__NRS-484B-600-1e__motor_vehicle_driver__above--94949cafef78/manifest.json) | Above 80 mph probe; Native 45-second recording, 900 samples, maximum sampled speed 80.70 mph. Controller repair after a 76.89 mph physical mismatch. | 1, 2 | Between-sample speed peaks and synthetic road public-way status remain unresolved; no final legal violation judgment is claimed | Unresolved (no label assigned) |

Case IDs: 1: `testing__C10301__NRS-484B-600-1e__motor_vehicle_driver__below`; 2: `testing__C10301__NRS-484B-600-1e__motor_vehicle_driver__equal`; 3: `testing__C10301__NRS-484B-600-1e__motor_vehicle_driver__above`.

## Remaining requirements

Imported strict-rate physical comparison passed (74.95 < 79.73 < 80.70 mph). Exact 80 mph legal equality, synthetic public-way status, and full law coverage remain unresolved.
