"""CPU fake source adapters; no fake is claimed to be physical evidence."""
import copy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from instrument_producer import (SourceProducer, audit_packet, audit_stream,
                                 build_packet, calibration_preflight, digest,
                                 serve_connection)
from delivery_audit import audit_attempt
from comparison_delivery_audit import audit_pair
from instrumentation import InstrumentClient


def sources(frame, actor=8):
    base = {'source_kind': 'original_sensor', 'native_frame': frame,
            'actor_id': actor}
    engine = dict(base, sensor_id='physical-engine-serial',
                  method='engine-shaft-rotation-sensor', engine_running=False)
    wheel = dict(base, sensor_id='wheel-optical-serial',
                 method='front-wheel-optical-encoder',
                 front_wheel_heading_world_deg={
                     'front_left': -20.0, 'front_right': -20.0})
    attendance = dict(base, sensor_id='cabin-person-serial',
                      method='cabin-and-person-tracker', occupant_count=0,
                      responsible_person_outside=True,
                      responsible_person_id='person-01')
    return engine, wheel, attendance


def calibration():
    survey = {'source_kind': 'original_survey', 'survey_id': 'right-curb-01',
              'road_id': 1, 'right_curb_y_m': -3.5,
              'curb_tangent_heading_world_deg': 0.0,
              'curb_distance_m': 1.75, 'road_xodr_sha256': '2' * 64}
    return {'format': 'c276263-curb-calibration-v1',
            'calibration_id': 'right-curb-survey-01',
            'source_kind': 'original_survey', 'curb_side': 'right',
            'survey_method': 'surveyed highway curb tangent',
            'sensor_method': 'front wheel optical encoder zero survey',
            'wheel_sensor_id': 'wheel-optical-serial',
            'curb_survey_id': 'right-curb-01',
            'curb_survey': survey, 'curb_survey_sha256': digest(survey),
            'curb_tangent_heading_world_deg': 0.0,
            'curb_distance_m': 1.75,
            'wheel_zero_offsets_deg': {'front_left': 0.0, 'front_right': 0.0},
            'max_angular_error_deg': 2.0,
            'valid_native_frames': [900, 1499]}


class FakeCarlaActor:
    id = 8
    heading_deg = 0.0
    native_wheels = {'front_left': -20.0, 'front_right': -20.0}


class InstrumentProducerTest(unittest.TestCase):
    def test_engine_actuator_preparation_is_separate_from_observation(self):
        producer = SourceProducer(
            lambda frame, actor: sources(frame, actor)[0],
            lambda frame, actor: sources(frame, actor)[1],
            lambda frame, actor: sources(frame, actor)[2], calibration(),
            engine_actuator=lambda actor, target: {
                'source_kind': 'original_actuator', 'actor_id': actor,
                'requested_engine_running': target, 'actuator_accepted': True,
                'actuator_id': 'vehicle-ignition-adapter'})
        request = {'format': 'c276263-engine-preparation-v1', 'actor_id': 8,
                   'case_id': 'engine_on', 'requested_engine_running': True}
        sample_request = {'format': 'c276263-instrument-request-v1',
                          'native_frame': 900, 'actor_id': 8,
                          'native_front_wheel_angles_deg': FakeCarlaActor.native_wheels,
                          'actor_heading_world_deg': 0.0}
        reader = io.StringIO(json.dumps(request) + '\n' +
                             json.dumps(sample_request) + '\n')
        writer = io.StringIO()
        self.assertTrue(serve_connection(reader, writer, producer, frames=1,
                                         diagnostic=True)['passed'])
        receipt, packet = map(json.loads, writer.getvalue().splitlines())
        self.assertTrue(receipt['requested_engine_running'])
        self.assertFalse(packet['engine_running'])
        client = InstrumentClient.__new__(InstrumentClient)
        client.reader = io.StringIO(json.dumps(receipt) + '\n')
        client.writer = io.StringIO()
        self.assertEqual(client.prepare_engine(8, 'engine_on', True), receipt)
        with self.assertRaisesRegex(ValueError, 'actuator callback required'):
            SourceProducer(None, None, None, calibration()).prepare_engine(
                8, 'engine_on', True)

    def packet(self, frame=900, diagnostic=True):
        actor = FakeCarlaActor()
        return build_packet(frame, actor.id, actor.native_wheels,
                            actor.heading_deg, calibration(),
                            *sources(frame), diagnostic=diagnostic)

    def test_fake_carla_original_shaped_producer_and_independent_audit(self):
        producer = SourceProducer(
            lambda frame, actor: sources(frame, actor)[0],
            lambda frame, actor: sources(frame, actor)[1],
            lambda frame, actor: sources(frame, actor)[2], calibration())
        actor = FakeCarlaActor()
        packets = [producer.sample(frame, actor.id, actor.native_wheels,
                    actor.heading_deg, diagnostic=True) for frame in range(900, 1500)]
        self.assertEqual(packets[0]['front_wheel_heading_to_curb_deg'], -20)
        self.assertTrue(audit_stream(packets, allow_diagnostic=True)['passed'])
        self.assertFalse(audit_stream(packets, allow_diagnostic=True)
                         ['physical_calibration_reviewed'])
        with self.assertRaisesRegex(ValueError, 'Diagnostic sensor packet'):
            audit_stream(packets)

    def test_source_service_joins_requests_and_rejects_frame_gap(self):
        producer = SourceProducer(
            lambda frame, actor: sources(frame, actor)[0],
            lambda frame, actor: sources(frame, actor)[1],
            lambda frame, actor: sources(frame, actor)[2], calibration())
        requests = []
        for frame in (900, 901):
            requests.append({'format': 'c276263-instrument-request-v1',
                             'native_frame': frame, 'actor_id': 8,
                             'native_front_wheel_angles_deg':
                                 FakeCarlaActor.native_wheels,
                             'actor_heading_world_deg': 0.0})
        reader = io.StringIO(''.join(json.dumps(row) + '\n' for row in requests))
        writer = io.StringIO()
        audit = serve_connection(reader, writer, producer, frames=2,
                                 diagnostic=True)
        self.assertTrue(audit['passed'])
        self.assertEqual(len(writer.getvalue().splitlines()), 2)
        requests[1]['native_frame'] = 902
        reader = io.StringIO(''.join(json.dumps(row) + '\n' for row in requests))
        with self.assertRaisesRegex(ValueError, 'frame or actor continuity'):
            serve_connection(reader, io.StringIO(), producer, frames=2,
                             diagnostic=True)

    def test_calibration_preflight_rejects_missing_survey_or_expired_window(self):
        record = calibration()
        self.assertIs(calibration_preflight(record, 900), record)
        changed = dict(record, curb_survey_sha256='0' * 64)
        with self.assertRaisesRegex(ValueError, 'survey hash'):
            calibration_preflight(changed, 900)
        changed = dict(record, curb_distance_m=2.5)
        with self.assertRaisesRegex(ValueError, 'geometry differ'):
            calibration_preflight(changed, 900)
        with self.assertRaisesRegex(ValueError, 'invalid for Native frame'):
            calibration_preflight(record, 1500)

    def test_source_proxy_stale_actor_and_wheel_disagreement_rejected(self):
        engine, wheel, attendance = sources(900)
        engine['method'] = 'speed_proxy'
        with self.assertRaisesRegex(ValueError, 'Proxy'):
            build_packet(900, 8, FakeCarlaActor.native_wheels, 0, calibration(),
                         engine, wheel, attendance, diagnostic=True)
        engine, wheel, attendance = sources(900)
        attendance['actor_id'] = 9
        with self.assertRaisesRegex(ValueError, 'identity/frame'):
            build_packet(900, 8, FakeCarlaActor.native_wheels, 0, calibration(),
                         engine, wheel, attendance, diagnostic=True)
        engine, wheel, attendance = sources(900)
        wheel['front_wheel_heading_world_deg']['front_left'] = 10
        with self.assertRaisesRegex(ValueError, 'disagree'):
            build_packet(900, 8, FakeCarlaActor.native_wheels, 0, calibration(),
                         engine, wheel, attendance, diagnostic=True)
        engine, wheel, attendance = sources(900)
        attendance['occupant_count'] = 1
        with self.assertRaisesRegex(ValueError, 'conflicts'):
            build_packet(900, 8, FakeCarlaActor.native_wheels, 0, calibration(),
                         engine, wheel, attendance, diagnostic=True)

    def test_independent_audit_rejects_tamper_and_identity_swap(self):
        packet = self.packet()
        self.assertTrue(audit_packet(packet, allow_diagnostic=True)
                        ['physical_review_required'])
        changed = copy.deepcopy(packet)
        changed['source_observations']['engine']['engine_running'] = True
        with self.assertRaisesRegex(ValueError, 'hash differs'):
            audit_packet(changed, allow_diagnostic=True)
        changed = copy.deepcopy(packet)
        changed['front_wheel_heading_to_curb_deg'] = 0
        with self.assertRaisesRegex(ValueError, 'Derived packet differs'):
            audit_packet(changed, allow_diagnostic=True)
        changed = copy.deepcopy(packet)
        changed['source_kind'] = 'claimed_original'
        with self.assertRaisesRegex(ValueError, 'provenance differs'):
            audit_packet(changed, allow_diagnostic=True)
        later = self.packet(frame=901)
        later['calibration']['calibration_id'] = 'another-calibration'
        later['wheel_calibration_id'] = 'another-calibration'
        with self.assertRaisesRegex(ValueError, 'identity or calibration changed'):
            audit_stream([packet, later], expected_frames=2,
                         allow_diagnostic=True)
        gap = self.packet(frame=902)
        with self.assertRaisesRegex(ValueError, 'Native frame gap'):
            audit_stream([packet, gap], expected_frames=2,
                         allow_diagnostic=True)

    def test_delivery_audit_rejects_diagnostic_acquisition(self):
        with tempfile.TemporaryDirectory(dir=Path(os.environ['TMPDIR']).resolve()) as tmp:
            root = Path(tmp)
            case = 'training__C276263__NRS-484B-533__motor_vehicle_driver__reference'
            (root / 'config.json').write_text(json.dumps({
                'case_id': case, 'selected_case_id': case}) + '\n')
            (root / 'acquisition-provenance.json').write_text(json.dumps({
                'diagnostic_fixture': True, 'native_vehicle_actor_id': 8}) + '\n')
            with self.assertRaisesRegex(ValueError, 'Original Native acquisition'):
                audit_attempt(root, case, root / 'physical-review.json')

    def test_pair_audit_rejects_reused_attempt_before_review(self):
        with tempfile.TemporaryDirectory(dir=Path(os.environ['TMPDIR']).resolve()) as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, 'Independent original attempts'):
                audit_pair(root, root, root / 'reference-review.json',
                           root / 'contrast-review.json')

    def test_pair_audit_rejects_diagnostic_source_before_comparison(self):
        with tempfile.TemporaryDirectory(dir=Path(os.environ['TMPDIR']).resolve()) as tmp:
            root = Path(tmp)
            reference, contrast = root / 'reference', root / 'contrast'
            reference.mkdir()
            contrast.mkdir()
            (reference / 'config.json').write_text(json.dumps({
                'case_id': 'training__C276263__NRS-484B-533__motor_vehicle_driver__reference',
                'selected_case_id': 'training__C276263__NRS-484B-533__motor_vehicle_driver__reference'}) + '\n')
            (reference / 'acquisition-provenance.json').write_text(json.dumps({
                'diagnostic_fixture': True, 'native_vehicle_actor_id': 8}) + '\n')
            with self.assertRaisesRegex(ValueError, 'Original Native acquisition'):
                audit_pair(reference, contrast, root / 'reference-review.json',
                           root / 'contrast-review.json')


if __name__ == '__main__':
    unittest.main()
