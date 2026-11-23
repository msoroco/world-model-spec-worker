"""Construct source-bound review packets for all eight selected diagnostic cases.

The retained survey has reference/contrast geometry rows. The other selected
cases reuse the reference geometry, with their own selected actor/video sources.
This produces observations and pending review bindings, never a legal verdict.
"""
import hashlib
import json
from pathlib import Path

from context_review import build as context_build
from event_evidence import build as event_build
from posting_review import build as posting_build

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GROUPS = ('reference', 'contrast', 'conflict', 'clear', 'near_lead',
          'absent_lead', 'device_direction', 'officer_direction')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def packet(group, manifest, manifest_sha, *, selection_override=None):
    require(group in GROUPS, 'Unknown selected case')
    case_id = HERE.name + '__' + group
    entry = next((item for item in manifest['cases']
                  if item['case_id'] == case_id), None)
    require(entry is not None and entry['kind'] == 'delivery',
            'Selected delivery case missing')
    prefix = ROOT / '.runtime-work' / ('c201084-final-' + group + '-primary')
    attempt = Path(str(prefix) + '-compatibility')
    processing = Path(str(prefix) + '-saved/v0001/processing.json')
    selection_path = attempt / 'candidate-selection.json'
    selection = (selection_override if selection_override is not None else
                 json.loads(selection_path.read_text()))
    require(selection.get('case_id') == case_id and
            selection.get('candidate_id') == 'primary' and
            selection.get('construction_sha256') == entry['construction_sha256'] and
            selection.get('manifest_sha256') == manifest_sha,
            'Candidate selection differs from final manifest')
    saved = json.loads(processing.read_text())
    require(saved.get('passed') is True and saved.get('recorded_only') is True and
            saved.get('originals_preserved') is True and
            saved.get('case_id') == case_id and
            saved.get('candidate_id') == 'primary' and
            saved.get('physical_acceptance_claimed') is False and
            saved.get('legal_acceptance_claimed') is False,
            'Saved processing differs')
    survey_case = group if group in ('reference', 'contrast') else 'reference'
    event = event_build(attempt, survey_case, diagnostic=True)
    event['case'] = group
    for relative, digest in event['source_sha256'].items():
        require(saved['original_source_hashes'].get(relative) == digest,
                'Saved original source hash differs: ' + relative)
    require(event['frames'] == 600 and event['diagnostic_fixture'] is True,
            'Selected diagnostic motion incomplete')
    return attempt, event, {
        'case_id': case_id, 'survey_geometry_case': survey_case,
        'candidate_selection_sha256': sha(selection_path),
        'saved_processing_sha256': sha(processing),
        'near_zero_episodes': len(event['near_zero_episodes']),
        'near_zero_zone_overlap_episodes': len(
            event['near_zero_authored_zone_overlap_episodes']),
    }


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest_sha = sha(manifest_path)
    manifest = json.loads(manifest_path.read_text())
    require({item['case_id'] for item in manifest['cases']} ==
            {HERE.name + '__' + group for group in GROUPS},
            'Eight selected cases differ')
    rows = []
    for group in GROUPS:
        attempt, event, row = packet(group, manifest, manifest_sha)
        event_path = HERE / ('selected-' + group + '-source-event.json')
        require(not event_path.exists(), 'Retain prior source event: ' + group)
        event_path.write_text(json.dumps(event, indent=2, sort_keys=True) + '\n')
        context = context_build(attempt, event_path)
        posting = posting_build(attempt, event_path)
        require(context['original_context_review_bound'] is False and
                posting['original_posting_review_bound'] is False,
                'Diagnostic review cannot claim original source')
        context_path = HERE / ('selected-' + group + '-context-pending.json')
        posting_path = HERE / ('selected-' + group + '-posting-pending.json')
        context_path.write_text(json.dumps(context, indent=2, sort_keys=True) + '\n')
        posting_path.write_text(json.dumps(posting, indent=2, sort_keys=True) + '\n')
        row.update({'event_sha256': sha(event_path),
                    'context_sha256': sha(context_path),
                    'posting_sha256': sha(posting_path)})
        rows.append(row)
    output = {
        'format': 'c201084-selected-source-review-packets-v1',
        'manifest_sha256': manifest_sha, 'selected_cases': rows,
        'diagnostic_only': True, 'original_native_observed': False,
        'original_context_review_bound': False,
        'original_posting_review_bound': False,
        'physical_or_legal_completion_claimed': False,
    }
    path = HERE / 'selected-source-review-index.json'
    require(not path.exists(), 'Retain prior review index')
    path.write_text(json.dumps(output, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'selected': len(rows), 'index_sha256': sha(path)}))


if __name__ == '__main__':
    main()
