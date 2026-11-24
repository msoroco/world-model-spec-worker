"""Exercise the original-review exception decision before Native capture."""
import hashlib
import json
from pathlib import Path

from physical_audit import (CROSSREFS, validate_cross_reference_evidence,
                            validate_cross_reference_review, validate_native_road_source,
                            validate_road_context)

HERE = Path(__file__).resolve().parent


def rejected(review):
    try:
        validate_cross_reference_review(review)
    except ValueError:
        return True
    return False


def evidence_rejected(evidence, frames):
    try:
        validate_cross_reference_evidence(evidence, frames)
    except ValueError:
        return True
    return False


def road_rejected(context, road_sha):
    try:
        validate_road_context(context, road_sha)
    except ValueError:
        return True
    return False


def main():
    template_path = HERE / 'original-review-template.json'
    template = json.loads(template_path.read_text())
    assert rejected(template['cross_reference_applicability'])
    assert evidence_rejected(template['cross_reference_evidence'], [])
    resolved = {key: 'inapplicable' for key in CROSSREFS}
    assert validate_cross_reference_review(resolved) == resolved
    mixed = dict(resolved)
    mixed['LVMC-11-30-060-A'] = 'applicable'
    assert validate_cross_reference_review(mixed) == mixed
    unresolved = dict(resolved)
    unresolved['NRS-484B-287-1c'] = 'unresolved'
    assert rejected(unresolved)
    omitted = dict(resolved)
    del omitted['NRS-484B-287-1d']
    assert rejected(omitted)
    extra = dict(resolved)
    extra['unreviewed-topic'] = 'inapplicable'
    assert rejected(extra)
    assert rejected(None)
    evidence = {key: {'frames': [100], 'cameras': ['overview'],
                      'observation': 'Source frame reviewed for this topic'}
                for key in CROSSREFS}
    assert validate_cross_reference_evidence(evidence, [100, 101]) == evidence
    bad_frame = {key: dict(value) for key, value in evidence.items()}
    bad_frame['NRS-484B-287-1c']['frames'] = [102]
    assert evidence_rejected(bad_frame, [100, 101])
    bad_camera = {key: dict(value) for key, value in evidence.items()}
    bad_camera['NRS-484B-287-1d']['cameras'] = ['synthetic_trace']
    assert evidence_rejected(bad_camera, [100, 101])
    missing = dict(evidence)
    del missing['NRS-484B-287-1e']
    assert evidence_rejected(missing, [100, 101])
    blank = {key: dict(value) for key, value in evidence.items()}
    blank['LVMC-11-30-060-A']['observation'] = '  '
    assert evidence_rejected(blank, [100, 101])
    road_sha = 'a' * 64
    road = {'source_kind': 'native_observation',
            'frozen_cell': {'layout': 'road', 'maneuver': 'travel', 'control': 'curb'},
            'authored_road_sha256': road_sha, 'native_road_sha256': 'b' * 64}
    assert validate_road_context(road, road_sha) == 'b' * 64
    for changed in ({**road, 'source_kind': 'synthetic_scene_request'},
                    {**road, 'authored_road_sha256': 'c' * 64},
                    {**road, 'native_road_sha256': ''},
                    {**road, 'frozen_cell': {'layout': 'intersection', 'maneuver': 'travel',
                                            'control': 'curb'}}):
        assert road_rejected(changed, road_sha)
    native_xml=b'<OpenDRIVE><road id="1"><objects /></road></OpenDRIVE>'
    native_hash=hashlib.sha256(native_xml).hexdigest()
    assert validate_native_road_source(native_xml,native_hash)['road_count']==1
    for changed in (native_xml.replace(b'<objects />',b'<objects><object type="crosswalk" /></objects>'),
                    native_xml.replace(b'</OpenDRIVE>',b'<junction id="2" /></OpenDRIVE>'),
                    native_xml.replace(b'<objects />',b'<signals><signal id="3" /></signals>')):
        try:
            validate_native_road_source(changed,hashlib.sha256(changed).hexdigest())
        except ValueError:
            pass
        else:
            raise AssertionError('Unexpected Native map context accepted')
    try:
        validate_native_road_source(native_xml,'0'*64)
    except ValueError:
        pass
    else:
        raise AssertionError('Changed Native map hash accepted')
    receipt = {
        'format': 'c230222-physical-crossref-gate-proof-v1',
        'physical_audit_sha256': hashlib.sha256((HERE / 'physical_audit.py').read_bytes()).hexdigest(),
        'delivery_audit_sha256': hashlib.sha256((HERE / 'delivery_audit.py').read_bytes()).hexdigest(),
        'pending_original_review_template_sha256': hashlib.sha256(template_path.read_bytes()).hexdigest(),
        'exact_crossref_count': len(CROSSREFS),
        'resolved_review_controls_accepted': 2,
        'unresolved_or_incomplete_review_controls_rejected': 4,
        'source_bound_evidence_control_accepted': 1,
        'wrong_frame_camera_missing_or_blank_evidence_controls_rejected': 4,
        'pending_review_template_rejected': True,
        'original_road_context_control_accepted': 1,
        'wrong_provenance_road_hash_native_hash_or_cell_controls_rejected': 4,
        'generated_native_map_source_control_accepted': 1,
        'native_map_crosswalk_junction_signal_or_hash_controls_rejected': 4,
        'original_native_capture_observed': False,
        'legal_verdict_claimed': False,
    }
    target = HERE / 'physical-crossref-gate-proof.json'
    target.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'receipt_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
