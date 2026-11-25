"""Run original capture under exclusive ownership, then audit saved sources.

The owner factory is provided by the local Native operator. It must return a
context manager that restores world settings and releases actors and sensors on
exit. Saved packaging and pixel auditing only begin after that context exits.
"""
from __future__ import annotations

import json
import hashlib
import shutil
from pathlib import Path

from delivery_audit import audit as audit_delivery
from prepare_delivery import prepare
from runner import capture_original
from site_review import verify


def dispatch(*, owner_factory, opendrive: Path, authority: Path,
             review_receipt: Path, property_id: str, case_id: str,
             purpose: dict, actor_source: dict, attempt: Path,
             capture_fn=capture_original, prepare_fn=prepare,
             audit_fn=audit_delivery, expected_frames: int = 900,
             native_export_fn=None) -> dict:
    """Require release readback before any saved-only processing."""
    reviewed = verify(opendrive, authority, review_receipt,
                      property_id=property_id)
    packet = reviewed['packet']
    if attempt.exists():
        raise ValueError('fresh original attempt path required')
    with owner_factory(packet, case_id) as owner:
        native_map = owner.world.get_map()
        original_road = native_map.to_opendrive()
        if (native_map.name != packet['native_map']['map_name'] or
                hashlib.sha256(original_road.encode()).hexdigest() !=
                packet['native_map']['sha256']):
            raise ValueError('live Native map differs from reviewed OpenDRIVE source')
        capture = capture_fn(
            world=owner.world, ego=owner.ego, map_packet=packet,
            property_id=property_id, purpose=purpose,
            actor_source=actor_source,
            signal_observer=owner.signal_observer,
            camera_observer=owner.camera_observer,
            destination_street_id=packet['intersecting_street_id'],
            output_dir=attempt, control_applier=owner.control_applier,
            graph_observer=getattr(owner, 'graph_observer', None))
    release = owner.release_receipt()
    if (release.get('format') != 'native-owner-release-v1' or
            release.get('case_id') != case_id or
            release.get('world_restored') is not True or
            release.get('actors_released') is not True or
            release.get('sensors_released') is not True or
            release.get('readback_passed') is not True):
        raise ValueError('Native owner release and restoration readback required')
    if native_export_fn is not None:
        native_export_fn(owner, attempt, capture)
    if (capture.get('case_id') != case_id or
            capture.get('sample_count') != expected_frames or
            capture.get('physical_acceptance_claimed') is not False):
        raise ValueError('exact original capture receipt required')
    release_path = attempt / 'owner-release-readback.json'
    if not attempt.is_dir() or release_path.exists():
        raise ValueError('fresh Native release receipt destination required')
    release_path.write_text(json.dumps(release, indent=2, sort_keys=True) + '\n')
    release_sha = hashlib.sha256(release_path.read_bytes()).hexdigest()
    retained_review = attempt / 'review-receipt.json'
    if retained_review.exists() or not attempt.is_dir():
        raise ValueError('fresh retained site review destination required')
    shutil.copyfile(review_receipt, retained_review)
    if hashlib.sha256(retained_review.read_bytes()).hexdigest() != reviewed['review_receipt_sha256']:
        raise ValueError('retained site review receipt differs')
    packet_path = attempt / 'source-map-packet.json'
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + '\n')
    prepared = prepare_fn(attempt, packet_path, case_id, property_id,
                          expected_frames=expected_frames)
    retained = verify(attempt / 'road.xodr', attempt / 'authority.json',
                      retained_review, property_id=property_id)
    if retained['review_receipt_sha256'] != reviewed['review_receipt_sha256']:
        raise ValueError('saved site review differs from capture source')
    bundle = json.loads(Path(prepared['bundle_path']).read_text())
    audited = audit_fn(attempt, bundle, expected_frames=expected_frames)
    return {'format': 'original-native-dispatch-v1', 'case_id': case_id,
            'site_review_sha256': reviewed['review_receipt_sha256'],
            'source_record_id': reviewed['source_record_id'],
            'capture': capture, 'release': release,
            'owner_release_readback_sha256': release_sha,
            'bundle_path': prepared['bundle_path'], 'audit': audited,
            'physical_acceptance_claimed': False}
