import copy
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from highway_continuity_comparison_audit import audit_attempts


HERE = Path(__file__).resolve().parents[1]


def _binding(topology):
    payload = {'format': 'worker-controlled-highway-route-pair',
               'map_name': topology['map_name'],
               'junction_id': str(topology['junction_id']),
               'routes': topology['routes'],
               'legal_highway_classification_claimed': False,
               'opendrive_sha256': sha256(b'synthetic OpenDRIVE').hexdigest()}
    payload['route_pair_sha256'] = sha256(json.dumps(
        payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return payload


class BoundAttemptAuditTests(unittest.TestCase):
    def _attempts(self, root):
        paths = [root / 'ending', root / 'continuing']
        for path, name in zip(paths, ('diagnostic-ending-yields.json',
                                      'diagnostic-highway-continuing.json')):
            path.mkdir()
            files = json.loads((HERE / name).read_text())['files']
            for source in ('intersection_participants.jsonl', 'video_frames.jsonl',
                           'control_inventory.json', 'road.xodr'):
                (path / source).write_text(files[source])
            topology_name = ('intersection_topology.json' if path == paths[0]
                             else 'highway_pair_topology.json')
            topology = json.loads(files[topology_name])
            if path == paths[0]:
                # The retained diagnostic predates Native road-id spelling.
                # This synthetic attempt uses the runner's original spelling.
                for lane in topology['lanes'].values():
                    if lane['highway_id'].startswith('road'):
                        lane['highway_id'] = 'native-road:' + lane['highway_id'][4:]
            (path / topology_name).write_text(json.dumps(topology))
            for camera in ('overview', 'approach', 'reference_corner',
                           'driver_reference'):
                (path / (camera + '.mkv')).write_bytes(b'synthetic camera placeholder')
        topology = json.loads((paths[1] / 'highway_pair_topology.json').read_text())
        binding = _binding(topology)
        binding['opendrive_sha256'] = sha256(
            (paths[0] / 'road.xodr').read_bytes()).hexdigest()
        payload = {key: value for key, value in binding.items()
                   if key != 'route_pair_sha256'}
        binding['route_pair_sha256'] = sha256(json.dumps(
            payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        for path in paths:
            (path / 'controlled_route_pair.json').write_text(json.dumps(binding))
        return paths

    def test_original_attempt_pair_and_changed_binding(self):
        with TemporaryDirectory() as temp:
            ending, continuing = self._attempts(Path(temp))
            proof = audit_attempts(ending, continuing)
            self.assertEqual(proof['controlled_route_pair_sha256'],
                             json.loads((ending / 'controlled_route_pair.json').read_text())
                             ['route_pair_sha256'])
            changed = json.loads((continuing / 'controlled_route_pair.json').read_text())
            changed['routes']['other'][0]['lane_id'] = -2
            (continuing / 'controlled_route_pair.json').write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, 'Stale'):
                audit_attempts(ending, continuing)
            (continuing / 'controlled_route_pair.json').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing original'):
                audit_attempts(ending, continuing)

    def test_changed_opendrive_source_rejected(self):
        with TemporaryDirectory() as temp:
            ending, continuing = self._attempts(Path(temp))
            (continuing / 'road.xodr').write_text('changed source')
            with self.assertRaisesRegex(ValueError, 'OpenDRIVE differs'):
                audit_attempts(ending, continuing)


if __name__ == '__main__':
    unittest.main()
