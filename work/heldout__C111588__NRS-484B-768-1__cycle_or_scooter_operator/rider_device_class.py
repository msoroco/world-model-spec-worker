"""Source-bound Native electric-device selection and saved identity review."""
from hashlib import sha256
import json
from pathlib import Path


def attributes(blueprint):
    return {name: blueprint.get_attribute(name).as_str() for name in
            ('base_type', 'object_type', 'special_type', 'device_type', 'powertrain')
            if blueprint.has_attribute(name)}


def select(library, device):
    if device not in ('electric_bicycle', 'electric_scooter'):
        raise ValueError('Unsupported electric-device class')
    noun = 'bicycle' if device == 'electric_bicycle' else 'scooter'
    matches = []
    for blueprint in library.filter('vehicle.*'):
        facts = attributes(blueprint)
        source = ' '.join([blueprint.id, *facts.values()]).lower().replace('-', '_')
        if noun in source and 'electric' in source:
            matches.append((blueprint.id, blueprint, facts))
    if not matches:
        raise ValueError('No sourced Native ' + device + ' blueprint')
    _, selected, facts = sorted(matches, key=lambda item: item[0])[0]
    return selected, {'blueprint_id': selected.id, 'attributes': facts,
                      'selection_query': 'vehicle.* with electric and ' + noun + ' tokens',
                      'device_class_candidate': device,
                      'device_class_confirmed': None,
                      'electric_drive_verified': None}


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure(attempt, device):
    root = Path(attempt)
    names = ('device_blueprint_readback.json', 'device_visual_review.jsonl',
             'video_frames.jsonl', 'rider_context.json', 'driver_reference.mkv')
    paths = {name: root / name for name in names}
    for name, path in paths.items():
        if not path.is_file() or not path.read_bytes():
            raise ValueError('Missing required source: ' + name)
    blueprint = json.loads(paths['device_blueprint_readback.json'].read_text())
    context = json.loads(paths['rider_context.json'].read_text())
    if blueprint.get('device_class_candidate') != device or context.get('device_type') != device:
        raise ValueError('Electric device class candidate differs')
    if blueprint.get('device_class_confirmed') is not None or blueprint.get('electric_drive_verified') is not None:
        raise ValueError('Unreviewed electric device claims must remain open')
    mapping = _rows(paths['video_frames.jsonl'])
    reviews = _rows(paths['device_visual_review.jsonl'])
    if not mapping or len(mapping) != len(reviews):
        raise ValueError('Electric device original frame lengths differ')
    video_hash = sha256(paths['driver_reference.mkv'].read_bytes()).hexdigest()
    for index, (frame, review) in enumerate(zip(mapping, reviews)):
        if (frame.get('video_frame') != index or
                (frame.get('carla_frame'), frame.get('time_s')) !=
                (review.get('frame'), review.get('time_s')) or
                review.get('source_video_sha256') != video_hash):
            raise ValueError('Stale or misaligned electric device pixel review')
        if review.get('device_form_visible') not in (None, True, False) or review.get('rider_standing') not in (None, True, False):
            raise ValueError('Invalid electric device visual review')
    return {'device_class_candidate': device, 'device_class_confirmed': None,
            'electric_drive_verified': None, 'visible_device_form_review_complete':
            all(row['device_form_visible'] is not None for row in reviews),
            'standing_rider_review_complete': all(row['rider_standing'] is not None for row in reviews),
            'legal_device_class_judgment': None,
            'sources': {name: sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}}
