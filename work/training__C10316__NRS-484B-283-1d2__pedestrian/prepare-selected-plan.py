"""Bind selected CPU cases to the exact frozen source observation inventory."""
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name


def main():
    path = HERE / 'case-plan.json'
    plan = json.loads(path.read_text())
    original = json.loads((ROOT / 'inputs' / ASSIGNMENT / 'assignment.json').read_text())
    if plan['source_law_text'] != original['law']['text']:
        raise ValueError('Exact law text changed')
    channels = ('kin.position', 'kin.heading', 'rel.occupies',
                'native_display_program', 'display_camera_frame_join')
    plan['observations'] = [
        {'name': name, 'mandatory': True,
         'reason': 'Retain source-bound original observations for ' + name}
        for name in channels]
    mapping = {
        'dev.pedestrian_signal': ('native_display_program', 'display_camera_frame_join'),
        'dev.governs': ('native_display_program', 'display_camera_frame_join'),
        'ru.subject': ('kin.position', 'rel.occupies'),
        'st.crosswalk': ('rel.occupies', 'display_camera_frame_join'),
        'rel.occupies': ('rel.occupies',),
        'kin.time': ('native_display_program', 'display_camera_frame_join'),
        'st.road_edge': ('rel.occupies', 'display_camera_frame_join'),
        'kin.speed': ('kin.position', 'kin.heading'),
    }
    terms = {item['term']: item['note'] for item in original['source_observation_terms']}
    if set(mapping) != set(terms):
        raise ValueError('Frozen source observation terms differ')
    plan['source_observation_mapping'] = {
        term: {'evidence': note + '; original Native and pixel review pending',
               'channels': list(mapping[term]),
               'source_refs': ['countdown_samples.jsonl', 'trace.jsonl',
                               'capture/evidence.jsonl', 'video_frames.jsonl',
                               'driver_reference.mkv', 'road.xodr']}
        for term, note in terms.items()}
    plan['camera_plan'] = {
        'profile': 'overview1080-capability', 'duration_s': 30,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'entire authored alley crossing, body and signal',
             'interval': 'all 600 frames / 0-30 s'},
            {'view': 'approach', 'subject': 'pedestrian route and full body at highway entry',
             'interval': 'all 600 frames / 0-30 s'},
            {'view': 'reference_corner', 'subject': 'marked crosswalk and both highway edges',
             'interval': 'all 600 frames / 0-30 s'},
            {'view': 'driver_reference', 'subject': 'head, flashing indication and displayed countdown',
             'interval': 'all 600 frames / 0-30 s'}]}
    ids = {item['case_id'] for item in plan['cases']}
    for item in plan['cases']:
        item['kind'] = 'delivery'
        item['selection_status'] = 'selected_cpu_prepared'
        item['construction_status'] = 'source_bound_cpu_prepared'
        item['expected_label'] = None
    for item in plan['requirement_dispositions']:
        if item['status'] == 'selected_required':
            item['case_ids'] = sorted(ids)
            item['evidence_or_gap'] = (
                'Two exact source-shaped countdown cases have current public and '
                'recorded-only CPU proofs; original physical display, route governance '
                'and statutory exception applicability await local capture review.')
    plan['runtime_gaps'] = [
        'Native head and original countdown pixels require independent local review.',
        'Cited statutory exception applicability and legal judgment remain open.',
        'No CARLA execution or accepted recording is claimed by CPU preparation.']
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'selected_case_count': len(ids),
                      'source_terms_mapped': len(terms), 'channels': list(channels)}))


if __name__ == '__main__':
    main()
