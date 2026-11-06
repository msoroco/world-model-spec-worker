import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from exception_case import BRANCHES, inspect_case

class ExceptionCaseProofs(unittest.TestCase):
    def test_complete_and_missing_source_for_all_six(self):
        frames=list(range(100,580))
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'exception_context.json'
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
                                      cited_law_text_sha256='a'*64,ego_action_frames=[221])
                    else:
                        packet.update(original_pixel_sha256='b'*64,direction_source_id='device-1',
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
