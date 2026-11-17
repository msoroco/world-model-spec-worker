"""Assemble every C150142 exact case from its current diagnostic construction.

This is a draft integration artifact.  It is deliberately not marked ready:
selected compatibility, delivery audits and independent review remain required.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_for(slug):
    if slug in ('reference', 'contrast', 'ordinary_red_signed'):
        return 'execution-manifest-diagnostic-' + slug + '.json'
    for family in ('tour_bus', 'shuttle_bus', 'rtc_bus'):
        if slug.startswith(family + '_'):
            return 'execution-manifest-diagnostic-' + family + '_below-draft.json'
    if slug.startswith('limo_'):
        return 'execution-manifest-diagnostic-limo_below-draft-v2.json'
    emergency = {
        'emergency_vehicle_unsigned_business': 'emergency-business',
        'emergency_vehicle_unsigned_no_business': 'emergency-no-business',
        'emergency_vehicle_signed_business': 'emergency-signed-business',
        'emergency_vehicle_signed_no_business': 'emergency-signed-no-business',
    }
    if slug in emergency:
        return 'execution-manifest-diagnostic-' + emergency[slug] + '-draft.json'
    if slug.startswith('armored_car_'):
        return 'execution-manifest-diagnostic-' + slug + '-draft.json'
    if slug.startswith('mail_'):
        return 'execution-manifest-diagnostic-' + slug.replace('_', '-') + '-draft.json'
    raise ValueError('No exact source manifest for ' + slug)


def assemble():
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    proposal = json.loads((ROOT / 'proposals/cases.json').read_text())
    planned = [case['case_id'] for case in plan['cases']]
    proposed = [case['case_id'] for case in proposal['cases']]
    if len(planned) != 30 or len(set(planned)) != 30 or set(planned) != set(proposed):
        raise ValueError('Exact plan/proposal coverage differs')
    runtime_hash = sha(REPO / 'runtime/pipeline/SOURCE-MANIFEST.json')
    cases = []
    sources = {}
    for case_id in planned:
        slug = case_id.removeprefix(ROOT.name + '__')
        name = source_for(slug)
        path = ROOT / name
        source = json.loads(path.read_text())
        if source['runtime_manifest_sha256'] != runtime_hash:
            raise ValueError('Stale pinned runtime in ' + name)
        entries = [row for row in source['cases'] if row['case_id'] == case_id]
        if len(entries) != 1:
            raise ValueError('Missing or duplicate exact entry: ' + case_id)
        entry = entries[0]
        if entry.get('kind') != 'delivery' or \
           entry.get('candidate_risk', {}).get('status') != 'physical' or \
           len(entry.get('candidates', [])) != 3:
            raise ValueError('Missing exact delivery or fallback construction: ' + slug)
        for candidate in [{'id': 'primary', 'construction': entry['construction'],
                           'construction_sha256': entry['construction_sha256']},
                          *entry['candidates']]:
            construction = ROOT / candidate['construction']
            if candidate['construction_sha256'] != sha(construction):
                raise ValueError('Stale exact construction: ' + slug + '/' + candidate['id'])
            package = json.loads(construction.read_text())
            if package['case_id'] != case_id or \
               not {'config.json', 'runner.py', 'finalize_selected.py'} <= \
                   {f['path'] for f in package['files']}:
                raise ValueError('Incomplete exact construction: ' + slug)
        if [candidate['id'] for candidate in entry['candidates']] != [
                'fallback1', 'fallback2', 'fallback3']:
            raise ValueError('Fallback order differs: ' + slug)
        cases.append(entry)
        sources[name] = sha(path)
    document = {'format': 'worker-execution-manifest',
                'assignment_id': ROOT.name,
                'status': 'draft_all_exact_cases_unselected',
                'runtime_manifest_sha256': runtime_hash,
                'cases': cases,
                'source_manifests': [{'path': name, 'sha256': digest}
                                     for name, digest in sorted(sources.items())],
                'original_native_observed': False,
                'delivery_ready': False}
    target = ROOT / 'execution-manifest-draft-all.json'
    target.write_text(json.dumps(document, indent=2, ensure_ascii=False,
                                 allow_nan=False) + '\n')
    return {'case_count': len(cases), 'candidate_count': 4 * len(cases),
            'source_manifest_count': len(sources),
            'merged_manifest': str(target.relative_to(REPO)),
            'sha256': sha(target), 'delivery_ready': False}


if __name__ == '__main__':
    print(json.dumps(assemble(), indent=2))
