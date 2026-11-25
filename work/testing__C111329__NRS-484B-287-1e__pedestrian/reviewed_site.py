"""Cross-check an original intersection survey and diagonal-device records.

This validates provenance joins and required review fields. It cannot decide
whether a document is truly official; an independent source review must do so.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree

from diagonal_crossing import validate_site


def _read(root, ref, name):
    if not isinstance(ref, dict) or not isinstance(ref.get('path'), str):
        raise ValueError(name + ' source reference missing')
    original = Path(root) / ref['path'] if root else Path(ref['path'])
    path = original.resolve()
    if root and (not path.is_relative_to(Path(root).resolve()) or original.is_symlink()):
        raise ValueError(name + ' source escapes reviewed packet')
    if not path.is_file():
        raise ValueError(name + ' original source missing')
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != ref.get('sha256'):
        raise ValueError(name + ' original source hash mismatch')
    return data


def _json(root, refs, name):
    try:
        return json.loads(_read(root, refs[name], name))
    except (KeyError, json.JSONDecodeError) as exc:
        raise ValueError(name + ' reviewed JSON source missing or invalid') from exc


def validate_reviewed_site(site, root=None):
    plan = validate_site(site, root)
    refs = site['sources']
    map_bytes = _read(root, refs['map'], 'map')
    try:
        road = ElementTree.fromstring(map_bytes)
    except ElementTree.ParseError as exc:
        raise ValueError('original map OpenDRIVE invalid') from exc
    if road.tag != 'OpenDRIVE' or not road.findall('./road/planView/geometry'):
        raise ValueError('original intersection map geometry missing')
    survey = _json(root, refs, 'corner_survey')
    authority = _json(root, refs, 'authorization')
    inventory = _json(root, refs, 'device_inventory')
    exception = _json(root, refs, 'exception_review')
    map_hash = refs['map']['sha256']
    device = site['governing_device']
    if (survey.get('cell_id') != 'C111329' or survey.get('map_sha256') != map_hash or
            survey.get('corners_clockwise') != site['corners_clockwise'] or
            survey.get('route_xy') != site['pedestrian_route'] or
            not survey.get('survey_method') or not survey.get('reviewer')):
        raise ValueError('original four-corner pedestrian survey unbound')
    if (authority.get('cell_id') != 'C111329' or
            authority.get('record_id') != device['authority_record_id'] or
            authority.get('movement') != 'pedestrian_diagonal' or
            authority.get('device_id') != device['id'] or
            authority.get('authorized') is not True or
            not authority.get('issuing_authority') or
            not authority.get('original_document_ref') or
            not authority.get('reviewer')):
        raise ValueError('official diagonal authorization source unbound')
    if (inventory.get('cell_id') != 'C111329' or
            inventory.get('device_id') != device['id'] or
            inventory.get('movement') != 'pedestrian_diagonal' or
            inventory.get('instruction_record_id') != device['instruction_record_id'] or
            inventory.get('placement_record_id') != device['placement_record_id'] or
            inventory.get('authorization_record_id') != device['authority_record_id'] or
            not inventory.get('original_device_observation_ref') or
            not inventory.get('reviewer')):
        raise ValueError('original pedestrian device inventory unbound')
    if (exception.get('statute') != 'NRS 484B.290' or
            exception.get('review_state') != site['exception_484b_290_review'] or
            not exception.get('source_ref') or not exception.get('reviewer')):
        raise ValueError('NRS 484B.290 exception review source unbound')
    return {'site_source_sha256': plan['source_sha256'],
            'device_id': device['id'], 'movement': 'pedestrian_diagonal',
            'exception_review_state': exception['review_state'],
            'official_status': 'source_review_required',
            'physical_realization': 'unconfirmed'}
