"""Check provenance of independent school-zone facts, without legal conclusions."""
import hashlib
import json
import shutil
from pathlib import Path


REQUIRED = (
    'zone_designation', 'zone_boundaries', 'school_adjacency', 'highway_status',
    'driver_identity', 'driver_control', 'vehicle_classification',
    'child_identity', 'child_location', 'school_session', 'school_operation',
    'class_hours', 'civil_time', 'beacon_configuration', 'beacon_lights',
    'zone_sign',
)
EXCEPTIONS = ('a_no_children', 'b_not_in_session', 'c_operation_interval',
              'd_operational_beacon_class_hours', 'e_no_operational_beacon_sign')
EXCEPTION_TOPICS = {
    'a_no_children': {'child_identity', 'child_location'},
    'b_not_in_session': {'school_session', 'civil_time'},
    'c_operation_interval': {'school_operation', 'civil_time'},
    'd_operational_beacon_class_hours': {'beacon_configuration', 'beacon_lights', 'class_hours', 'civil_time'},
    'e_no_operational_beacon_sign': {'beacon_configuration', 'zone_sign', 'civil_time'},
}


def verified_sources(attempt, context):
    """Bind supplied review records to bytes; no worker record proves a statute."""
    attempt = Path(attempt).resolve()
    review = context.get('independent_review')
    if not isinstance(review, dict) or review.get('format') != 'c263073-source-review-v1':
        raise ValueError('Independent school-zone source review missing')
    records = review.get('records')
    if not isinstance(records, dict) or set(records) != set(REQUIRED):
        raise ValueError('Independent source record inventory incomplete')
    bound = {}
    for topic in REQUIRED:
        record = records[topic]
        if not isinstance(record, dict) or record.get('topic') != topic:
            raise ValueError('Independent source topic differs: ' + topic)
        relative = record.get('path')
        digest = record.get('sha256')
        if not isinstance(relative, str) or not relative or not isinstance(digest, str) or len(digest) != 64:
            raise ValueError('Independent source reference missing: ' + topic)
        path = (attempt / relative).resolve()
        if not path.is_relative_to(attempt) or not path.is_file():
            raise ValueError('Independent source file missing: ' + topic)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Independent source hash differs: ' + topic)
        if not isinstance(record.get('reviewer'), str) or not record['reviewer'].strip():
            raise ValueError('Independent source reviewer missing: ' + topic)
        if not isinstance(record.get('observation'), str) or not record['observation'].strip():
            raise ValueError('Independent source observation missing: ' + topic)
        bound[topic] = {'path': relative, 'sha256': digest,
                        'reviewer': record['reviewer'], 'observation': record['observation']}
    dispositions = review.get('exception_dispositions')
    if not isinstance(dispositions, dict) or set(dispositions) != set(EXCEPTIONS):
        raise ValueError('Five statutory exception dispositions incomplete')
    for exception in EXCEPTIONS:
        item = dispositions[exception]
        if not isinstance(item, dict) or item.get('status') not in ('applies', 'does_not_apply', 'unresolved'):
            raise ValueError('Exception disposition missing: ' + exception)
        topics = item.get('source_topics')
        if not isinstance(topics, list) or not topics or any(topic not in bound for topic in topics):
            raise ValueError('Exception source binding missing: ' + exception)
        if not EXCEPTION_TOPICS[exception].issubset(set(topics)):
            raise ValueError('Exception source topics incomplete: ' + exception)
        if not isinstance(item.get('reason'), str) or not item['reason'].strip():
            raise ValueError('Exception review reason missing: ' + exception)
    return {'records': bound, 'exception_dispositions': dispositions}


def attach_original_review(output, source_dir):
    """Seal independently supplied records into the original Native acquisition."""
    source_dir = Path(source_dir).resolve()
    packet = source_dir / 'review.json'
    if not packet.is_file():
        raise ValueError('Independent review packet missing before Native capture')
    context = json.loads(packet.read_text())
    verified_sources(source_dir, context)
    output = Path(output).resolve()
    target_dir = output / 'review-sources'
    target_dir.mkdir(parents=True, exist_ok=False)
    for topic in REQUIRED:
        record = context['independent_review']['records'][topic]
        source = (source_dir / record['path']).resolve()
        target = target_dir / (topic + '.json')
        shutil.copyfile(source, target)
        record['path'] = str(target.relative_to(output))
    verified_sources(output, context)
    return context['independent_review']
