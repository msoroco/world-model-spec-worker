import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from exception_case import BRANCHES, CITED_DEVICE_LAW_SHA256, inspect_case

class ExceptionCaseProofs(unittest.TestCase):
    def test_complete_and_missing_source_for_all_six(self):
        frames=list(range(100,580))
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'exception_context.json'
            (root/'parking.mkv').write_bytes(b'synthetic pixel source')
            (root/'other_actor_history.jsonl').write_text(''.join(json.dumps({'native_frame':frame,'conflict_occupancy':frame==320})+'\n' for frame in frames))
            (root/'ego_response_history.jsonl').write_text(''.join(json.dumps({'native_frame':frame,
                'brake_applied':index==221,'conflict_brake_override':index==221,
                'response_onset':index==221,'speed_mps':4.0 if index<221 else 3.0})+'\n'
                for index,frame in enumerate(frames)))
            (root/'device_action_history.jsonl').write_text(''.join(json.dumps({'native_frame':frame,
                'device_id':'620','device_type':'206','device_road_id':2,
                'ego_brake_applied':index==221,'ego_speed_mps':4.0 if index<221 else 3.0})+'\n'
                for index,frame in enumerate(frames)))
            for suffix,(branch,polarity) in BRANCHES.items():
                packet={'source_kind':'native_context_schema','branch':branch,
                    'requested_polarity':polarity,'original_frames':list(frames),
                    'observed_exception_source_ids':[]}
                if polarity=='present':
                    packet['observed_exception_source_ids']=['synthetic-source']
                    if branch=='necessary_traffic_conflict':
                        packet.update(other_actor_frames=[220,221],ego_brake_frames=[221],
                                      intersection_boundary_source='native_map_readback')
                    elif branch=='compliance_with_law':
                        packet.update(cited_law_id='NRS-484B-300-1',
                                      cited_law_text_sha256=CITED_DEVICE_LAW_SHA256,ego_action_frames=[221])
                    else:
                        packet.update(original_pixel_sha256=hashlib.sha256((root/'parking.mkv').read_bytes()).hexdigest(),direction_source_id='device-1',
                                      direction_frame=221,ego_action_frames=[221])
                path.write_text(json.dumps(packet))
                with self.subTest(suffix=suffix):
                    result=inspect_case(path,suffix,frames)
                    self.assertFalse(result['physical_observation_claimed'])
                    packet['original_frames'][-1]=999
                    path.write_text(json.dumps(packet))
                    with self.assertRaisesRegex(ValueError,'not joined'):
                        inspect_case(path,suffix,frames)
            path.unlink()
            with self.assertRaisesRegex(ValueError,'Missing required source'):
                inspect_case(path,'exception_1_1',frames)
