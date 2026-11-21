"""Compare C183370 delivery pairs against retained sources and reviewed context."""
import argparse
import json
from pathlib import Path

from delivery_audit import HERE, CORE_SOURCES, read, require, sha

FIXED_CONFIG = ('assignment_id', 'actor', 'cell_id', 'law_id', 'cameras',
                'duration_s', 'rate_hz', 'frames', 'controller_knobs',
                'recording_description')
FIXED_READBACK = ('pavement_road_id', 'control_type_id', 'warning_person_type_id')


def validate_fixed_context(left_config, right_config,
                           left_readback, right_readback):
    require(all(left_config.get(key) == right_config.get(key)
                for key in FIXED_CONFIG),
            'Comparison fixed capture config changed')
    require(left_readback['plan'] == right_readback['plan'] and
            all(left_readback.get(key) == right_readback.get(key)
                for key in FIXED_READBACK),
            'Comparison surveyed pavement or control context changed')


def compare(comparison_id, left_audit_path, right_audit_path,
            left_attempt, right_attempt, diagnostic, manifest_path=None):
    left_attempt, right_attempt = Path(left_attempt), Path(right_attempt)
    plan = read(HERE / 'case-plan.json')
    comparison = next((row for row in plan['comparisons']
                       if row['comparison_id'] == comparison_id), None)
    require(comparison is not None and len(comparison['case_ids']) == 2,
            'Unknown exact comparison')
    audits = [read(left_audit_path), read(right_audit_path)]
    attempts = [left_attempt, right_attempt]
    manifest = (Path(manifest_path) if manifest_path else
                HERE / ('draft-combined-capture-manifest.json' if diagnostic
                        else 'execution-manifest.json'))
    require(manifest.is_file(), 'Exact comparison manifest missing')
    require(manifest.resolve() in (
                (HERE / 'execution-manifest.json').resolve(),
                (HERE / 'draft-combined-capture-manifest.json').resolve(),
                (HERE / 'update153-integrated-all-text1-manifest.json').resolve())
            and (diagnostic or manifest.resolve() ==
                 (HERE / 'execution-manifest.json').resolve()),
            'Comparison manifest is not an approved selection')
    analyses = []
    contexts = []
    for index, (audit, attempt) in enumerate(zip(audits, attempts)):
        require(audit.get('case_id') == comparison['case_ids'][index] and
                audit.get('candidate_id') == 'primary' and
                audit.get('manifest_sha256') == sha(manifest) and
                audit.get('diagnostic_only') is diagnostic and
                audit.get('accepted') is (not diagnostic),
                'Comparison delivery audit identity or acceptance differs')
        hashes = audit.get('original_source_sha256', {})
        require(set(CORE_SOURCES) <= set(hashes) and
                all(sha(attempt / name) == hashes[name] for name in CORE_SOURCES),
                'Comparison original source changed')
        analysis_path = attempt / 'source-analysis.json'
        analysis = read(analysis_path)
        expected_kind = ('synthetic_diagnostic_capture' if diagnostic else
                         'original_carla_capture')
        require(analysis['source_kind'] == expected_kind and
                (diagnostic or audit['source_review']['analysis_sha256'] ==
                 sha(analysis_path)),
                'Comparison source analysis differs')
        for name, expected in analysis['source_hashes'].items():
            require(sha(attempt / name) == expected,
                    'Comparison analyzed source changed: ' + name)
        for camera in analysis['camera_sources']:
            require(sha(attempt / (camera['name'] + '.mkv')) ==
                    camera['source_sha256'] and
                    camera['decoded_frames'] >= 600,
                    'Comparison camera source or duration differs')
        config, readback = read(attempt / 'config.json'), read(attempt / 'live-readback.json')
        require(config['case_id'] == audit['case_id'] and
                config['frames'] >= 600 and config['rate_hz'] == 20,
                'Comparison capture config differs')
        analyses.append(analysis)
        contexts.append((config, readback))
    left_config, left_readback = contexts[0]
    right_config, right_readback = contexts[1]
    validate_fixed_context(left_config, right_config,
                           left_readback, right_readback)
    route = comparison_id.rsplit('__comparison_', 1)[-1]
    contacts = [bool(row['observations']['pavement_footprint_contact_frames'])
                for row in analyses]
    require(contacts == ([True, True] if route == 'employee_exception'
                         else [True, False]),
            'Comparison observed route difference missing')
    reviewed = []
    if not diagnostic:
        for audit, attempt in zip(audits, attempts):
            annotations_path = attempt / 'source-review-annotations.json'
            require(sha(annotations_path) ==
                    audit['source_review']['annotations_sha256'],
                    'Comparison source annotation changed')
            annotations = read(annotations_path)['annotations']
            condition = annotations['newly_repaired_pavement']['condition']
            reviewed.append((condition,
                             audit['source_review']['fixed_flagger_conduct_status']))
        require(reviewed[0] == reviewed[1],
                'Comparison pavement condition or flagger conduct changed')
        activities = [audit['source_review']['employee_exception_status']
                      for audit in audits]
        require(activities == (['actually_engaged', 'not_actually_engaged']
                if route == 'employee_exception' else
                ['not_actually_engaged', 'not_actually_engaged']),
                'Comparison employee activity difference or control changed')
    return {'format': 'c183370-delivery-comparison-audit-v1',
            'comparison_id': comparison_id,
            'case_ids': comparison['case_ids'],
            'manifest_sha256': sha(manifest),
            'diagnostic_only': diagnostic,
            'accepted': not diagnostic,
            'fixed_context_checked': True,
            'observed_contact': contacts,
            'reviewed_pavement_and_flagger': reviewed,
            'source_audit_sha256': [sha(left_audit_path), sha(right_audit_path)],
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for key in ('comparison', 'left-audit', 'right-audit', 'left-attempt',
                'right-attempt', 'output'):
        parser.add_argument('--' + key, required=True)
    parser.add_argument('--manifest')
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    value = compare(args.comparison, args.left_audit, args.right_audit,
                    args.left_attempt, args.right_attempt, args.diagnostic,
                    args.manifest)
    output = Path(args.output)
    require(not output.exists(), 'Preserve prior comparison audit')
    output.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'comparison_id': args.comparison,
                      'diagnostic_only': args.diagnostic,
                      'accepted': value['accepted']}, sort_keys=True))
