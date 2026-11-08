"""Run the controlled pair against all four exact embedded exception bundles."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile

HERE = Path(__file__).resolve().parent
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bundle(suffix, candidate, expected_sha, output):
    path = HERE / 'draft-candidates' / suffix / candidate / 'construction.json'
    if digest(path) != expected_sha:
        raise ValueError('Exact candidate construction hash differs: ' + suffix + '/' + candidate)
    construction = json.loads(path.read_text())
    if construction.get('case_id') != HERE.name + '__' + suffix or construction.get('status') != 'unselected_cpu_draft':
        raise ValueError('Exact candidate identity or status differs')
    for item in construction['files']:
        destination = output / item['path']
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(item['content'])
    return construction


def load(module_path):
    spec = importlib.util.spec_from_file_location('exact_traffic_counterfactual', module_path)
    if spec is None or spec.loader is None:
        raise ValueError('Exact candidate saved processor cannot load')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expect_rejected(module, absent, present, expected):
    try:
        module.inspect(absent, present)
    except ValueError as error:
        if expected not in str(error):
            raise
        return str(error)
    raise ValueError('Exact candidate missing-source negative passed')


def main():
    manifest_path = HERE / 'draft-exception-execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entries = {entry['case_id'].split('__')[-1]: entry for entry in manifest['cases']}
    source = HERE / 'exception-counterfactual-sources'
    expected_source = digest(HERE / 'native' / 'traffic_counterfactual.py')
    outcomes = []
    with tempfile.TemporaryDirectory(prefix='c110454-exact-pair-') as temp:
        root = Path(temp)
        for candidate in CANDIDATES:
            pair = root / candidate
            absent_bundle, present_bundle = pair / 'absent-bundle', pair / 'present-bundle'
            absent_bundle.mkdir(parents=True); present_bundle.mkdir(parents=True)
            refs = []
            for suffix, destination in (('exception_1_1', absent_bundle), ('exception_1_2', present_bundle)):
                entry = entries[suffix]
                ref = entry if candidate == 'primary' else next(
                    item for item in entry['candidates'] if item['id'] == candidate)
                construction = bundle(suffix, candidate, ref['construction_sha256'], destination)
                config = json.loads((destination / 'config.json').read_text())
                if config['candidate_id'] != candidate or config['case_suffix'] != suffix or \
                   construction['requested_polarity'] != ('absent' if suffix.endswith('_1') else 'present'):
                    raise ValueError('Materialized pair candidate or polarity differs')
                refs.append(ref['construction_sha256'])
            for directory in (absent_bundle, present_bundle):
                if digest(directory / 'traffic_counterfactual.py') != expected_source:
                    raise ValueError('Exact candidate saved processor source differs')
            pair_source = pair / 'source'
            shutil.copytree(source, pair_source)
            absent, present = pair_source / 'absent', pair_source / 'present'
            for directory in (absent, present):
                identity_path = directory / 'capture_identity.json'
                identity = json.loads(identity_path.read_text())
                identity['candidate_id'] = candidate
                identity_path.write_text(json.dumps(identity, sort_keys=True) + '\n')
            module = load(present_bundle / 'traffic_counterfactual.py')
            result = module.inspect(absent, present)
            if result['common_identity']['candidate_id'] != candidate or \
               result['brake_onset_video_frame'] != 120 or \
               len(result['absent_ego_present_actor_overlap_frames']) != 41 or \
               result['present_ego_present_actor_overlap_frames']:
                raise ValueError('Exact candidate controlled pair result differs')
            (present / 'other_actor_history.jsonl').unlink()
            negative = expect_rejected(module, absent, present,
                                       'Missing saved motion source: other_actor_history.jsonl')
            outcomes.append({'candidate': candidate, 'construction_sha256': refs,
                             'processor_sha256': expected_source,
                             'hypothetical_overlap_frames': 41,
                             'observed_overlap_frames': 0,
                             'missing_actor_negative': negative})
    return {'format': 'lvmc-exact-traffic-pair-package-proof-v1',
            'passed': True, 'manifest_sha256': digest(manifest_path),
            'candidate_pairs': outcomes, 'selected': False,
            'physical_or_legal_necessity_claimed': False}


if __name__ == '__main__':
    result = main()
    (HERE / 'traffic-pair-package-proof.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'passed': True, 'candidate_pairs': len(result['candidate_pairs']),
                      'manifest_sha256': result['manifest_sha256']}, indent=2))
