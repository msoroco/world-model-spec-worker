"""Validate worker Core requirements against the pinned runtime, before fixtures.

Law-summary observation names are planning terms. Only ontology IDs with a
supported acquisition path belong in ``config.required_atoms``.
"""
from pathlib import Path

# These paths are implemented by convert(), but require additional original
# packets. A static preflight establishes a possible path, not that a packet or
# a value exists in the eventual recording.
PACKET_PATHS = {
    'env.visibility': {'environment_calibration', 'surface_provenance'},
    'env.ice_or_snow': {'environment_calibration', 'surface_provenance'},
    'st.one_way_roadway': {'scenario_geometry'},
    'st.median_or_divider': {'scenario_geometry'},
    'dev.regulatory_sign': {'scenario_geometry', 'scenario_rule_evidence'},
}


def check_required_atoms(runtime, required, source_packets=(), case_config=None):
    from traffic_spec_adapter.adapter import atom_ids, manifest

    library = Path(runtime) / 'library'
    ids = set(atom_ids(library))
    capability = manifest(library)['atoms']
    if not isinstance(required, list) or any(not isinstance(atom, str) for atom in required):
        raise ValueError('Core required_atoms must be a list of ontology IDs')
    if len(required) != len(set(required)):
        raise ValueError('Duplicate Core required atom')
    packets = set(source_packets)
    if any(not isinstance(packet, str) for packet in packets):
        raise ValueError('source_packets must contain packet names')
    for atom in required:
        if atom not in ids:
            raise ValueError('Unknown Core required atom: ' + atom)
        if atom in PACKET_PATHS or capability.get(atom, 'absent') == 'absent':
            needed = PACKET_PATHS.get(atom)
            if needed is None:
                raise ValueError('Core atom lacks a supported adapter path: ' + atom)
            if not needed <= packets:
                raise ValueError('Core atom needs source packets: '+atom+' '+','.join(sorted(needed-packets)))
    if 'st.entrance_of' in required:
        references = (case_config or {}).get('required_entrance_references')
        if not isinstance(references, list) or not references:
            raise ValueError('Required entrance atom needs declared native object references')
        if any(not isinstance(ref, dict) or set(ref) != {'road_id','object_id','start_frame','end_frame'}
               for ref in references):
            raise ValueError('Malformed required entrance reference')
    return True


def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--config', required=True, type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    check_required_atoms(args.runtime, config.get('required_atoms', []), config.get('source_packets', []), config)
    print(json.dumps({'config': str(args.config), 'core_atom_preflight': 'passed'}))


if __name__ == '__main__':
    main()
