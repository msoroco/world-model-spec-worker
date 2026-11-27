"""Source-gated electric cycle and scooter construction for C230207.

An ordinary cycle with a changed label is not evidence of an electric device.
This module checks the proposed asset before spawning it. Original device and
rider pixels still need independent review after a Native recording.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


ELECTRIC_CLASSES = frozenset({'electric_bicycle', 'electric_scooter'})
ORDINARY_BICYCLES = frozenset({
    'vehicle.bh.crossbike', 'vehicle.diamondback.century',
    'vehicle.gazelle.omafiets',
})


def bind_asset(library, machine_class: str, review: dict, source_root: Path) -> dict:
    """Bind class review, source bytes and exact live Native blueprint identity."""
    if machine_class not in ELECTRIC_CLASSES:
        raise ValueError('Unknown electric device class')
    if not isinstance(review, dict) or review.get('machine_class') != machine_class:
        raise ValueError('Exact electric device class review required')
    blueprint_id = review.get('blueprint_id')
    if (not isinstance(blueprint_id, str) or not blueprint_id.startswith('vehicle.')
            or blueprint_id in ORDINARY_BICYCLES):
        raise ValueError('Ordinary bicycle or unspecified electric blueprint rejected')
    if (review.get('source_kind') != 'reviewed_native_asset'
            or not review.get('reviewer') or not review.get('review_date')
            or review.get('classification_conclusion') != machine_class):
        raise ValueError('Independent class-specific asset review required')
    if not review.get('power_source_evidence') or not review.get('device_geometry_evidence'):
        raise ValueError('Electric power and device geometry source review required')
    refs = review.get('source_refs')
    if not isinstance(refs, list) or not refs:
        raise ValueError('Source-hashed asset references required')
    source_root = Path(source_root).resolve()
    bound = {}
    for ref in refs:
        relative = ref.get('path') if isinstance(ref, dict) else None
        if not isinstance(relative, str) or not relative:
            raise ValueError('Asset source path required')
        source = (source_root / relative).resolve()
        if source_root not in source.parents or not source.is_file():
            raise ValueError('Asset source outside source root or missing')
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != ref.get('sha256') or relative in bound:
            raise ValueError('Asset source hash changed or duplicated')
        bound[relative] = digest
    matches = [item for item in library.filter(blueprint_id)
               if item.id == blueprint_id]
    if len(matches) != 1:
        raise ValueError('Exact reviewed electric blueprint unavailable in Native library')
    return {'machine_class': machine_class, 'blueprint_id': blueprint_id,
            'review_source_sha256': bound, 'classification_review_bound': True,
            'original_class_pixels_verified': False,
            'original_rider_posture_verified': False,
            'legal_verdict_claimed': False}


def spawn_asset(world, machine_class: str, review: dict, source_root: Path, transform):
    bound = bind_asset(world.get_blueprint_library(), machine_class, review, source_root)
    blueprint = world.get_blueprint_library().find(bound['blueprint_id'])
    if blueprint.id != bound['blueprint_id']:
        raise ValueError('Live blueprint identity changed')
    actor = world.spawn_actor(blueprint, transform)
    if actor is None or actor.type_id != bound['blueprint_id']:
        if actor is not None:
            actor.destroy()
        raise ValueError('Spawned device differs from reviewed electric blueprint')
    return actor, {**bound, 'native_actor_id': actor.id}
