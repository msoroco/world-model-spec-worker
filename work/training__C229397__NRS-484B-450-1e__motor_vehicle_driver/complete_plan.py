"""Add exact camera and source-observation mapping to the case plan."""
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
PLAN = FOLDER / 'case-plan.json'


def complete():
    plan = json.loads(PLAN.read_text())
    plan['camera_plan'] = {'profile': 'overview1080-capability',
        'duration_s': 30, 'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'subject, roadway and full crosswalk',
             'interval': 'all 600 frames'},
            {'view': 'approach', 'subject': 'subject approach and stop/stand/park activity',
             'interval': 'all 600 frames'},
            {'view': 'reference_corner', 'subject': 'crosswalk boundary and exception context',
             'interval': 'all 600 frames'},
            {'view': 'driver_reference', 'subject': 'subject and driver reference',
             'interval': 'all 600 frames'}]}
    source = 'original actor-sources.jsonl joined to crosswalk-source.json and video_frames.jsonl'
    plan['source_observation_mapping'] = {
        'drv.standing_or_parked': {'evidence': 'same-tick speed and rest interval',
            'channels': ['crosswalk_observation'], 'source_refs': [source]},
        'st.crosswalk': {'evidence': 'source-hashed crosswalk polygon and four camera views',
            'channels': ['crosswalk_observation'], 'source_refs': [source]},
        'rel.occupies': {'evidence': 'same-tick vehicle footprint versus polygon',
            'channels': ['crosswalk_observation'], 'source_refs': [source]},
        'drv.forced_halt': {'evidence': 'reviewed traffic-conflict source packet',
            'channels': [], 'source_refs': ['exception-context.json and reviewed original pixels']},
        'dev.human_direction': {'evidence': 'reviewed officer direction source packet',
            'channels': [], 'source_refs': ['exception-context.json and reviewed original pixels']},
        'dev.traffic_signal': {'evidence': 'reviewed official-device direction source packet',
            'channels': [], 'source_refs': ['exception-context.json and reviewed original pixels']}}
    PLAN.write_text(json.dumps(plan, indent=2) + '\n')


if __name__ == '__main__':
    complete()
