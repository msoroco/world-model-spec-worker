"""Source-gated NRS 486.351(2)-(3) alternative review, without a legal verdict."""
from pathlib import Path
import hashlib
import json

RIDER_CLASSES = {'motorcycle', 'moped', 'trimobile'}
PROHIBITED_ACTIONS = {'abreast', 'overtake', 'pass'}
EXCEPTION_PAIR_CLASSES = {'motorcycle', 'moped'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def review(context, source_root):
    """Keep visual geometry separate from identity and driver-consent evidence."""
    if context.get('rider_class') not in RIDER_CLASSES:
        raise ValueError('Rider class needs original blueprint and Chapter 486 review')
    if context.get('other_class') not in RIDER_CLASSES | {'motor_vehicle'}:
        raise ValueError('Other vehicle class needs original identity review')
    action = context.get('observed_action')
    if action not in PROHIBITED_ACTIONS | {'following'}:
        raise ValueError('Observed action must be separately source-classified')
    evidence = context.get('classification_source')
    if not isinstance(evidence, dict) or not evidence.get('path') or not evidence.get('sha256'):
        raise ValueError('Participant classification needs original source hash')
    path = Path(source_root) / evidence['path']
    if not path.is_file() or sha(path) != evidence['sha256']:
        raise ValueError('Participant classification source missing or changed')
    pair_eligible = (context['rider_class'] in EXCEPTION_PAIR_CLASSES and
                     context['other_class'] in EXCEPTION_PAIR_CLASSES and
                     action == 'abreast' and context.get('abreast_count') == 2)
    consent = context.get('driver_consent')
    if consent is not None:
        consent_source = context.get('consent_source')
        if not isinstance(consent_source, dict) or not consent_source.get('path') or not consent_source.get('sha256'):
            raise ValueError('Driver consent cannot be inferred from visual arrangement')
        path = Path(source_root) / consent_source['path']
        if not path.is_file() or sha(path) != consent_source['sha256']:
            raise ValueError('Driver consent source missing or changed')
    return {'observed_action': action,
            'rider_class': context['rider_class'],
            'other_class': context['other_class'],
            'same_lane_prohibition_action_observed': action in PROHIBITED_ACTIONS,
            'subsection_3_pair_eligible': pair_eligible,
            'subsection_3_consent_verified': consent is True if pair_eligible else False,
            'subsection_3_exception_established': pair_eligible and consent is True,
            'consent_unverified': pair_eligible and consent is None,
            'classification_source_sha256': evidence['sha256'],
            'legal_verdict_claimed': False}
