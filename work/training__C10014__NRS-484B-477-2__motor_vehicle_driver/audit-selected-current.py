"""Independent audit of current exact C10014 synthetic compatibility paths."""
import hashlib
import json
import os
from pathlib import Path
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def paths(suffix, candidate):
    compat = ROOT/'.runtime-work'/f'c10014-update017-{suffix}-{candidate}-compat'
    saved = ROOT/'.runtime-work'/f'c10014-update017-{suffix}-{candidate}-saved'
    return compat, saved/'v0001'


def audit_attempt(folder, saved, selected, entry, candidate):
    receipt = read(folder/'compatibility.json')
    processing = read(saved/'processing.json')
    result = read(folder/'result.json')
    report = read(folder/'analysis-report.json')
    config = read(folder/'config.json')
    selected_cases = [case for case in read(HERE/'proposals/cases.json')['cases']
                      if case['case_id'] == entry['case_id'] and
                      case['target_type'] != 'baseline']
    require(len(selected_cases) == 1 and
            config['case'].get('case_id') == entry['case_id'] and
            config['case'].get('recording_description') == config['recording_description'] and
            config['recording_description'] == selected_cases[0]['recording_description'],
            'selected case recording contract differs from source proposal')
    require(receipt['format'] == 'worker-package-compatibility' and receipt['passed'] is True,
            'compatibility did not pass')
    require(receipt['construction_sha256'] == selected['construction_sha256'] ==
            sha(HERE/selected['construction']), 'construction binding differs')
    require(receipt['case_id'] == entry['case_id'] and receipt['candidate_id'] == candidate,
            'compatibility identity differs')
    require({'selected_measurements', 'negative_case_source', 'lean_decoder',
             'final_decode', 'derived_outputs_rebuilt', 'four_camera_sources'} <=
            set(receipt['checks']), 'required compatibility stages absent')
    require(receipt['negative_removed'] == 'native_samples.jsonl' and
            receipt['negative_log_sha256'] == sha(folder/'negative-analysis.log') and
            receipt['log_sha256'] == sha(folder/'compatibility-analysis.log'),
            'missing-source negative or analysis log differs')
    require(processing['passed'] is True and processing['recorded_only'] is True and
            processing['originals_preserved'] is True and
            processing['missing_evidence'] is False and
            processing['candidate_id'] == candidate and
            processing['case_id'] == entry['case_id'] and
            processing['native_revision']['construction_sha256'] == selected['construction_sha256'],
            'saved processing proof incomplete')
    require(result['accepted'] is False and result['legal_verdict_claimed'] is False and
            result['maneuver_completed'] is False and
            result['provenance_kind'] == 'synthetic_local_diagnostic',
            'synthetic result claimed physical or legal acceptance')
    require(tuple(camera['name'] for camera in config['cameras']) == CAMERAS and
            set(result['video_references']) == {name+'.mkv' for name in CAMERAS},
            'four source camera contract differs')
    require(all(name+'.mkv' in receipt['fixture_manifest'] and
                sha(folder/(name+'.mkv')) == receipt['fixture_manifest'][name+'.mkv']
                for name in CAMERAS), 'source video hash differs')
    sample = rows(folder/'native_samples.jsonl')
    mapping = rows(folder/'video_frames.jsonl')
    trace = rows(folder/'trace.jsonl')
    evidence = rows(folder/'capture/evidence.jsonl')
    body = rows(folder/'body_history.jsonl')
    require(all(len(source) == 480 for source in (sample, mapping, trace, evidence, body)),
            '480 raw rows required')
    for index, (s, m, t, e, b) in enumerate(zip(sample, mapping, trace, evidence, body)):
        frame = 100+index
        require(s['native_frame'] == m['native_frame'] == m['carla_frame'] ==
                t['frame'] == e['original_frame'] == b['frame'] == frame,
                'raw original frame join differs')
        require(m['video_frame'] == index and abs(s['time_s']-m['time_s']) < 1e-4 and
                abs(t['time_s']-m['time_s']) < 1e-4 and
                abs(e['recording_time_s']-m['time_s']) < 1e-4 and
                abs(b['time_s']-m['time_s']) < 1e-4,
                'raw original time join differs')
        require(s['speed_provenance'] == t['speed_provenance'] ==
                e['ego']['speed_provenance'] == 'synthetic_native_sample' and
                s['synthetic_diagnostic'] is True and
                t['synthetic_diagnostic'] is True and
                e['synthetic_diagnostic'] is True,
                'invented speed lacks synthetic provenance')
        require(s['native_center_xy_m'] == t['position_m'][:2] ==
                e['ego']['position_m'][:2], 'raw center differs')
        original = {(round(v[0], 5), round(v[1], 5))
                    for v in e['ego']['body_vertices_m']}
        source = {(round(v[0], 5), round(v[1], 5))
                  for v in s['native_body_xy_m']}
        require(len(source) == 4 and source == original ==
                {(round(v[0], 5), round(v[1], 5)) for v in b['body_vertices_m']},
                'raw vehicle footprint differs')
    geometry = read(folder/'road_geometry.json')
    xmin, ymin, xmax, ymax = geometry['driveway_entrance_native_xy_bounds_m']
    stop = [s for s in sample if
            s['native_road_id'] == geometry['alley_native_road_id'] and
            s['native_lane_id'] == geometry['alley_native_lane_id'] and
            s['speed_mps'] <= .1]
    require(len(stop) >= 40, 'stationary alley interval absent')
    suffix = entry['case_id'].rsplit('__', 1)[-1]
    expected = 0.0 if suffix == 'reference' else 5.2
    def body_overlap(row):
        body = row['native_body_xy_m']
        width = max(0., min(max(v[0] for v in body), xmax)-
                    max(min(v[0] for v in body), xmin))
        height = max(0., min(max(v[1] for v in body), ymax)-
                     max(min(v[1] for v in body), ymin))
        return width if height > 0 else 0.
    overlap = max(body_overlap(s) for s in stop)
    require(abs(overlap-expected) < 1e-6 and
            result['measured_values']['max_entrance_overlap_m'] == expected and
            report['measurements']['entrance_overlap_observation']['value']
            ['max_entrance_overlap_m'] == expected, 'independent entrance overlap differs')
    require(all(sha(folder/name) == digest for name, digest in
                report['original_joins']['source_hashes'].items()),
            'analysis original source hash differs')
    require(all(sha(folder/name) == digest for name, digest in
                processing['original_source_hashes'].items() if name in
                ('native_samples.jsonl', 'trace.jsonl', 'video_frames.jsonl',
                 'body_history.jsonl', 'capture/evidence.jsonl')),
            'saved processing source hash differs')
    core = read(folder/'converted/trace.json')['scenes']
    require(len(core) == 480 and read(folder/'final-decode.json')['passed'] is True,
            'Core or final video decode incomplete')
    return {'case_id': entry['case_id'], 'candidate_id': candidate,
            'construction_sha256': selected['construction_sha256'],
            'compatibility_sha256': sha(folder/'compatibility.json'),
            'processing_sha256': sha(saved/'processing.json'),
            'analysis_sha256': sha(folder/'analysis-report.json'),
            'result_sha256': sha(folder/'result.json'),
            'overlap_m': expected, 'raw_rows': len(sample)}, sample, core


def main():
    manifest = read(HERE/'execution-manifest.json')
    plan = read(HERE/'case-plan.json')
    require(len(manifest['cases']) == 2 and len(plan['comparisons']) == 1,
            'expected one exact controlled pair')
    require(plan['comparisons'][0]['deliberate_differences'] ==
            ['stopped_footprint_at_abutting_entrance'], 'comparison variable differs')
    audited = []
    for candidate in CANDIDATES:
        pair = []
        for suffix, entry in zip(('reference', 'contrast'), manifest['cases']):
            require(entry['case_id'].endswith('__'+suffix), 'case order differs')
            selected = entry if candidate == 'primary' else next(
                item for item in entry['candidates'] if item['id'] == candidate)
            folder, saved = paths(suffix, candidate)
            proof, sample, core = audit_attempt(folder, saved, selected, entry, candidate)
            audited.append(proof)
            pair.append((sample, core, read(folder/'config.json')))
        reference, contrast = pair
        for a, b in zip(reference[0][:132], contrast[0][:132]):
            require(a == b, 'controlled raw approach prefix differs')
        for a, b in zip(reference[1], contrast[1]):
            require(a['t'] == b['t'] and a['structures'] == b['structures'] and
                    a['env'] == b['env'], 'controlled Core context differs')
        require(reference[1][-1]['users'][0]['kin']['position'][0] == -12.0 and
                contrast[1][-1]['users'][0]['kin']['position'][0] == 0.0,
                'controlled stop stations differ')
        config_a, config_b = (dict(reference[2]), dict(contrast[2]))
        for config in (config_a, config_b):
            for key in ('case_id', 'selected_case_id', 'case_suffix',
                        'candidate_id', 'supported_case_ids', 'case'):
                config.pop(key, None)
        require(config_a == config_b, 'controlled construction config differs')
    first_entry = manifest['cases'][0]
    first_folder, first_saved = paths('reference', 'primary')
    negatives = []
    for name in ('missing_samples', 'changed_frame', 'false_acceptance',
                 'missing_case_contract'):
        with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',
                                         prefix='c10014-audit-negative-') as temporary:
            target = Path(temporary)
            for item in first_folder.iterdir():
                os.symlink(item, target/item.name, target_is_directory=item.is_dir())
            if name == 'missing_samples':
                (target/'native_samples.jsonl').unlink()
            elif name == 'changed_frame':
                source = rows(first_folder/'native_samples.jsonl')
                source[8]['native_frame'] = 999
                (target/'native_samples.jsonl').unlink()
                (target/'native_samples.jsonl').write_text(
                    ''.join(json.dumps(row)+'\n' for row in source))
            elif name == 'false_acceptance':
                result = read(first_folder/'result.json')
                result['accepted'] = True
                (target/'result.json').unlink()
                (target/'result.json').write_text(json.dumps(result)+'\n')
            else:
                config = read(first_folder/'config.json')
                config['case'].pop('recording_description')
                (target/'config.json').unlink()
                (target/'config.json').write_text(json.dumps(config)+'\n')
            try:
                audit_attempt(target, first_saved, first_entry, first_entry, 'primary')
            except (ValueError, FileNotFoundError):
                negatives.append(name)
            else:
                raise ValueError('Independent negative was accepted: '+name)
    report = {'format': 'c10014-update017-independent-selected-cpu-audit',
              'execution_manifest_sha256': sha(HERE/'execution-manifest.json'),
              'attempts': audited, 'controlled_pairs': len(CANDIDATES),
              'rejected_mutations': negatives,
              'scope': 'selected construction software proof; synthetic sources; no Native or legal acceptance'}
    (HERE/'update017-selected-exact-audit.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'passed': True, 'attempts': len(audited),
                      'controlled_pairs': len(CANDIDATES),
                      'rejected_mutations': negatives}))


if __name__ == '__main__':
    main()
