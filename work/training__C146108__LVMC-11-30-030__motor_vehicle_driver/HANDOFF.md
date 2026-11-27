# C146108 / LVMC 11.30.030 CPU handoff

Status: partial. Four exact selected Native construction bundles cover marked and unmarked intersection crossings with hold and pass policies. No original Native event, physical completion, legal verdict or accepted recording is claimed. The frozen full-train membership is empty.

The original law requires a vehicle stopped at either crossing to permit a pedestrian to cross, and another driver approaching from the rear who overtakes and passes. A stop near a crossing is not proof of its purpose. The unmarked crossing requires original intersection geometry and a review separate from the lead stop purpose review.

`crosswalk_pass_scene.py` authors the two crossing kinds and four controlled 600-frame requests. `measure_crosswalk_pass.py` requires original road, crossing, lane, body, motion and four-camera hashes and joins all frames. `crosswalk-pass-proof.json` has four synthetic positive traces and eight missing-source, actor and frame negatives. The four selected bundles in `draft-native-manifest.json` pass current-runtime offline construction tests. `build_diagnostic.py` creates explicitly synthetic source-shaped fixtures for public and recorded-only pipeline diagnostics. These fixtures do not prove original crossing, lead stop purpose, passing or legal compliance.

Next work: complete public compatibility positive and missing-source negative, recorded-only, semantic, physical/lifecycle and independent delivery/comparison proofs; bind final execution manifest and run the exact assignment strict gate. All original camera pixels, crossing geometry, lead stop purpose, pedestrian crossing and ego body sequence remain local review requirements.
