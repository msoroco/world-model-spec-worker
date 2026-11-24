"""Check 140(B) and 46.030 authored survey geometry and source joins."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def audit():
    for tag, labels in (('140b', ('cane_prop_candidate', 'no_cane_prop')),
                        ('46', ('school_warning_candidate', 'no_school_warning'))):
        manifest = json.loads((HERE / f'crossref-{tag}-manifest.json').read_text())
        assert len(manifest['cases']) == 2
        traces = []
        samples = []
        for entry, label in zip(manifest['cases'], labels):
            folder = HERE / f'crossref-{tag}-native' / label
            assert sha(folder / 'construction.json') == entry['construction_sha256']
            sources = folder / 'fixture-sources'
            context = json.loads((sources / 'curb-context.json').read_text())
            road = (HERE / 'native/road-school-warning-candidate.xodr'
                    if tag == '46' and label == labels[0] else HERE / 'native/road.xodr')
            assert context['authored_road_sha256'] == sha(road)
            review = context['cross_reference_review']
            assert review['original_school_warning_pixels_verified'] is False if tag == '46' else review['original_cane_pixels_verified'] is False
            if tag == '46':
                objects = ET.parse(road).getroot().findall('.//objects/object')
                assert len(objects) == (2 if label == labels[0] else 0)
                if objects:
                    assert {obj.get('type') for obj in objects} == {'crosswalk', 'trafficLight'}
                assert review['school_warning_target_present'] == (label == labels[0])
                assert review['child_context_verified'] is False
                assert review['fifty_foot_stop_and_release_verified'] is False
            else:
                assert review['cane_prop_requested'] == (label == labels[0])
                assert review['pedestrian_blindness_verified'] is False
                assert review['driver_precautions_reviewed'] is False
            trace = rows(sources / 'trace.jsonl')
            sample = rows(sources / 'curb-samples.jsonl')
            assert len(trace) == len(sample) == 600
            traces.append(trace)
            samples.append(sample)
        assert traces[0] == traces[1]
        assert samples[0] == samples[1]
    return {'format': 'c230222-crossref-survey-source-audit-v1',
            'survey_pairs': 2, 'cases': 4, 'synthetic_source_frames_per_case': 600,
            'original_pixels_verified': False, 'legal_applicability_conclusion': None}


if __name__ == '__main__':
    path = HERE / 'crossref-survey-audit.json'
    path.write_text(json.dumps(audit(), indent=2) + '\n')
    print(path.read_text(), end='')
