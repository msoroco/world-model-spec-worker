import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from phase_source import entry_observation,load
from native_capture import apply_phase_sources,retain_phase_sources


class PhaseSourceTests(unittest.TestCase):
    def packet(self,folder):
        root=Path(folder);source=root/'governing-source.txt'
        source.write_text('Synthetic fixture: actor 17 follows reviewed light 29.\n')
        packet={'format':'c111125-reviewed-participant-phase-v1',
                'review_method':'original-governing-signal-and-entry-rule',
                'reviewer':'CPU fixture reviewer','source_ref':'synthetic fixture',
                'source_file':source.name,
                'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                'participant_actor_id':17,'participant_role':'vehicle',
                'governing_signal_actor_id':29,'permitted_entry_states':['Green'],
                'entry_rule_source_ref':'synthetic fixture only'}
        path=root/'review.json';path.write_text(json.dumps(packet))
        return path,source,packet

    def test_reviewed_entry_and_unknown_initial_presence(self):
        with tempfile.TemporaryDirectory() as folder:
            path,source,_=self.packet(folder);binding=load(path,source)
            person={'id':17,'role':'vehicle'}
            lights=[{'actor_id':29,'state':'Green'}]
            self.assertIsNone(entry_observation(binding,person,lights,frame=1,previous_inside=None,inside=True)['status'])
            green=entry_observation(binding,person,lights,frame=2,previous_inside=False,inside=True)
            self.assertTrue(green['status'])
            self.assertEqual(green['packet_sha256'],binding['packet_sha256'])
            self.assertFalse(entry_observation(binding,person,[{'actor_id':29,'state':'Red'}],frame=3,previous_inside=False,inside=True)['status'])
            self.assertIsNone(entry_observation(binding,person,[{'actor_id':29,'state':'Yellow'}],frame=4,previous_inside=False,inside=True)['status'])
            self.assertIsNone(entry_observation(binding,person,lights,frame=5,previous_inside=True,inside=True)['status'])

    def test_rejects_changed_source_and_wrong_actor_or_phase(self):
        with tempfile.TemporaryDirectory() as folder:
            path,source,packet=self.packet(folder)
            source.write_text('Changed after review')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):load(path,source)
            source.write_text('Synthetic fixture: actor 17 follows reviewed light 29.\n')
            binding=load(path,source)
            with self.assertRaisesRegex(ValueError,'identity mismatch'):
                entry_observation(binding,{'id':18,'role':'vehicle'},[{'actor_id':29,'state':'Green'}],frame=1,previous_inside=False,inside=True)
            with self.assertRaisesRegex(ValueError,'absent or ambiguous'):
                entry_observation(binding,{'id':17,'role':'vehicle'},[],frame=1,previous_inside=False,inside=True)
            packet['permitted_entry_states']=['Green','Yellow'];path.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError,'inventory missing'):load(path,source)

    def test_native_transition_requires_prior_outside_sample(self):
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as output:
            self.packet(folder)
            bindings,names=retain_phase_sources(folder,output)
            self.assertEqual(len(names),2)
            scene={'intersection_bounds_m':[-5,-5,8,5],
                   'adjacent_crosswalk_bounds_m':[[-8,-5,-5,5],[8,-5,11,5]]}
            prior={};statuses={};lights=[{'actor_id':29,'state':'Green'}]
            def person(x):
                return {'id':17,'role':'vehicle','body_vertices_m':[[x,0],[x+1,0],[x+1,1],[x,1]],
                        'lawfully_present':None,'lawful_presence_source':None}
            first=apply_phase_sources([person(0)],lights,scene,bindings,prior,statuses,1)[0]
            self.assertIsNone(first['lawfully_present'])
            apply_phase_sources([person(-20)],lights,scene,bindings,prior,statuses,2)
            entry=apply_phase_sources([person(0)],lights,scene,bindings,prior,statuses,3)[0]
            self.assertTrue(entry['lawfully_present'])
            self.assertEqual(entry['phase_entry_observation']['frame'],3)
            later=apply_phase_sources([person(1)],lights,scene,bindings,prior,statuses,4)[0]
            self.assertTrue(later['lawfully_present'])
            apply_phase_sources([person(30)],lights,scene,bindings,prior,statuses,5)
            self.assertEqual(statuses,{})
