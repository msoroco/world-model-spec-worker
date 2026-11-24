"""Independent CPU delivery audit for one selected exclusion branch."""
import argparse
import hashlib
import json
from pathlib import Path

from audit_sources import audit

HERE = Path(__file__).resolve().parent
BASE = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(value, message):
    if not value:
        raise ValueError(message)


def check(case_id, negative=False):
    suffix = case_id.removeprefix(BASE.name + '__')
    require(suffix in ('device_controlled', 'opposing_no_turn', 'opposing_left_turn') and
            case_id == BASE.name + '__' + suffix, 'wrong exact branch case')
    source = HERE / suffix / 'sources'
    if negative:
        require((source / 'missing-actor-history.json').is_file(), 'missing actor-history source')
        raise ValueError('missing actor-history source')
    audit(suffix)
    construction = HERE / suffix / 'primary/construction.json'
    proof = HERE / suffix / 'primary/proofs'
    public = read(proof / 'compatibility.json')
    saved = read(proof / 'saved-processing.json')
    require(public.get('passed') is True and public.get('case_id') == case_id and
            public.get('candidate_id') == 'primary' and
            public.get('construction_sha256') == sha(construction),
            'public compatibility does not bind selected branch')
    required = {'four_camera_sources', 'actual_analysis', 'native_validation',
                'lean_decoder', 'final_decode', 'render', 'selected_measurements',
                'negative_case_source'}
    require(required <= set(public.get('checks', [])), 'public branch CPU proof omitted checks')
    require(public.get('negative_removed') == 'actor-history.json' and
            public.get('negative_error_contains') in (proof / 'negative-analysis.log').read_text(),
            'missing actor source negative did not reject')
    require(saved.get('passed') is True and saved.get('recorded_only') is True and
            saved.get('originals_preserved') is True and saved.get('missing_evidence') is False and
            saved.get('case_id') == case_id and saved.get('candidate_id') == 'primary',
            'recorded-only branch processing failed')
    physical = read(HERE / 'physical-proofs' / suffix / 'proof.json')
    require(physical.get('construction_sha256') == sha(construction) and
            {x['kind'] for x in physical['fixtures']} ==
            {'complete_motion', 'incomplete_motion', 'missing_evidence'} and
            physical.get('original_native_motion_verified') is False,
            'physical diagnostic proof changed')
    return case_id + ': source join, public decoder/video, saved processing, physical CPU diagnostics pass'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('case_id')
    parser.add_argument('--negative', action='store_true')
    arguments = parser.parse_args()
    print(check(arguments.case_id, arguments.negative))
