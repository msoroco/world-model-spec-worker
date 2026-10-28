"""Validate worker Core requirements against the pinned runtime, before fixtures.

Law-summary observation names are planning terms. Only ontology IDs with a
supported acquisition path belong in ``config.required_atoms``.
"""
from pathlib import Path


def check_required_atoms(runtime, required):
    from traffic_spec_adapter.adapter import atom_ids, manifest

    library = Path(runtime) / 'library'
    ids = set(atom_ids(library))
    capability = manifest(
        library, original_live=True, visibility_observed=True,
        extended_observations=True, road_user_visibility=True,
        wheel_angles=True,
    )['atoms']
    if not isinstance(required, list) or any(not isinstance(atom, str) for atom in required):
        raise ValueError('Core required_atoms must be a list of ontology IDs')
    if len(required) != len(set(required)):
        raise ValueError('Duplicate Core required atom')
    for atom in required:
        if atom not in ids:
            raise ValueError('Unknown Core required atom: ' + atom)
        if capability[atom] == 'absent':
            raise ValueError('Core atom lacks a supported adapter path: ' + atom)
    return True


def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--config', required=True, type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    check_required_atoms(args.runtime, config.get('required_atoms', []))
    print(json.dumps({'config': str(args.config), 'core_atom_preflight': 'passed'}))


if __name__ == '__main__':
    main()
