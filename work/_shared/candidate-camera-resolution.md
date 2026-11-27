# Focused camera fallback resolution, 2026-11-27

C10307/LVMC-11-40-130: reference fallback construction now retains the complete top-level and embedded camera-plan metadata. The selected-source comparison guard verifies original attempt construction/selection, saved source and camera contract before independent pair audit. Its negative mixed-selection test rejects changed fixed cameras. Owner and lead exact scoped strict gates passed.

C188132/LVMC-11-30-060-B: `camera_comparison_audit.py` verifies each selected, source-hashed Native camera placement from the original attempt and requires the four camera positions to match across the pair before its source-bound overpass audit. Both shared comparison catalog commands now invoke this wrapper. Mixed-selection and stale-source negatives pass. Owner and lead exact scoped strict gates passed.

These are CPU software proofs of comparison isolation. Physical capture and local acceptance remain pending. Other candidate comparison findings remain open.

Evidence hashes:
- `work/testing__C10307__LVMC-11-40-130__cycle_or_scooter_operator/comparison_source_guard.py` SHA-256 `2422ee06560afe0e04e4ffdd4287a45413f418be3ed28689a7767fffdf01045b`
- `work/testing__C10307__LVMC-11-40-130__cycle_or_scooter_operator/cpu-camera-isolation-tests.log` SHA-256 `48d4d6d5d1c360c9a0e55004a75750e5278cca375c39e32b252e86495f1daaaf`
- `work/testing__C188132__LVMC-11-30-060-B__pedestrian/camera_comparison_audit.py` SHA-256 `4393b88a78f11d16e8901c15ecfdb918f090940f1ec5f4b7b9976ee58b0a493e`
- `work/testing__C188132__LVMC-11-30-060-B__pedestrian/cpu-camera-repair-tests.log` SHA-256 `41d0cd4590962ffc1479ae116d0c9834fa366b30f974c25e540dfad4a7f9f1e8`
