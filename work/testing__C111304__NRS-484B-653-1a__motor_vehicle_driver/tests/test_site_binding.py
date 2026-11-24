import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import encounter
import site_binding


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + '\n', encoding='utf-8')


class Map:
    name = 'TestIntersection'
    def to_opendrive(self):
        return 'diagnostic opendrive map'


class World:
    def get_map(self):
        return Map()


def sources(root, case):
    access = root / 'access.txt'
    access.write_text('Diagnostic public-access source only.\n', encoding='utf-8')
    review = root / 'review.json'
    write(review, {'site_id': 'diagnostic-site',
                   'public_access_basis': case.public_access_basis,
                   'source_sha256': sha(access), 'source_kind': 'synthetic_fixture'})
    plan = root / 'camera-plan.json'
    write(plan, {'cameras': {name: {'width': 64, 'height': 64}
                            for name in ('front', 'rear', 'left', 'right')}})
    canonical_plan = json.dumps(json.loads(plan.read_text()), sort_keys=True,
                                separators=(',', ':')).encode()
    site = root / 'site.json'
    write(site, {'site_id': 'diagnostic-site', 'cell_id': 'C111304',
                 'layout': 'intersection', 'map_name': Map.name,
                 'map_sha256': hashlib.sha256(Map().to_opendrive().encode()).hexdigest(),
                 'camera_plan_sha256': hashlib.sha256(canonical_plan).hexdigest(),
                 'public_access_basis': case.public_access_basis,
                 'public_access_source_sha256': sha(access),
                 'public_access_review_sha256': sha(review),
                 'lanes': {name: {'lane_id': name, 'source_sha256': 'a' * 64,
                                  'waypoints': [name + '0', name + '1']}
                           for name in ('northbound', 'southbound', 'crossing')},
                 'conflict_zone': {'source_sha256': 'b' * 64},
                 'property_anchor': {'source_sha256': 'c' * 64},
                 'crossing_occupant': {'source_sha256': 'd' * 64}})
    return site, access, review, plan


class SiteBindingTests(unittest.TestCase):
    def test_two_bases_bind_loaded_map_and_sources(self):
        for case in (encounter.CASES[0], encounter.CASES[6]):
            with TemporaryDirectory() as tmp:
                paths = sources(Path(tmp), case)
                with self.assertRaisesRegex(ValueError, 'reviewed original public-access source required'):
                    site_binding.bind_world_site(World(), *paths, case)
                bound = site_binding.bind_world_site(World(), *paths, case,
                                                     allow_diagnostic=True)
                self.assertEqual(bound['site_sha256'], sha(paths[0]))
                self.assertEqual(bound['public_access_basis'], case.public_access_basis)

    def test_rejects_map_review_and_plan_drift(self):
        case = encounter.CASES[0]
        with TemporaryDirectory() as tmp:
            site, access, review, plan = sources(Path(tmp), case)
            access.write_text('Changed source\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'review/source join mismatch'):
                site_binding.bind_world_site(World(), site, access, review, plan, case,
                                             allow_diagnostic=True)
            site, access, review, plan = sources(Path(tmp), case)
            packet = json.loads(site.read_text()); packet['map_sha256'] = '0' * 64
            write(site, packet)
            with self.assertRaisesRegex(ValueError, 'OpenDRIVE hash differs'):
                site_binding.bind_world_site(World(), site, access, review, plan, case,
                                             allow_diagnostic=True)
            site, access, review, plan = sources(Path(tmp), case)
            write(plan, {'cameras': {}})
            with self.assertRaisesRegex(ValueError, 'camera plan source hash mismatch'):
                site_binding.bind_world_site(World(), site, access, review, plan, case,
                                             allow_diagnostic=True)


if __name__ == '__main__':
    unittest.main()
