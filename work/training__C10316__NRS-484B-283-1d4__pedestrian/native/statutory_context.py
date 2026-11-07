"""Source-bound fact inventory for d4 and its cited branches; no legal verdict."""
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assess(contract_path, source_measurement_path, facts_path=None):
    contract = json.loads(Path(contract_path).read_text())
    if isinstance(source_measurement_path, dict):
        measured = source_measurement_path
        measurement_sha256 = hashlib.sha256(json.dumps(
            measured, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    else:
        measured = json.loads(Path(source_measurement_path).read_text())
        measurement_sha256 = sha(source_measurement_path)
    if (contract.get('format') != 'c10316-prior-entry-statutory-context-contract-v2' or
            contract.get('target_law_id') != 'NRS-484B-283-1d4' or
            contract.get('legal_applicability_determined') is not False or
            contract.get('physical_context_observed') is not False):
        raise ValueError('Statutory context contract differs')
    dependencies = contract.get('dependencies')
    if not isinstance(dependencies, list) or len(dependencies) != 12 or len({
        row['law_id'] for row in dependencies}) != 12:
        raise ValueError('Statutory dependency inventory incomplete')
    if (measured.get('format') != 'c10316-prior-entry-source-observation-v1' or
            measured.get('legal_verdict_claimed') is not False):
        raise ValueError('Prior-entry source measurement differs')
    facts = {}
    provenance = None
    if facts_path is not None:
        packet = json.loads(Path(facts_path).read_text())
        if packet.get('format') != 'c10316-statutory-context-facts-v1' or (
                packet.get('source_sha256') != measured.get('source_sha256')):
            raise ValueError('Statutory context facts source differs')
        if packet.get('provenance') != 'synthetic_diagnostic':
            raise ValueError('Statutory context provenance unverified')
        facts = packet.get('facts')
        if not isinstance(facts, dict) or any(type(value) is not bool for value in facts.values()):
            raise ValueError('Statutory context facts invalid')
        provenance = packet['provenance']
    branches = []
    for dependency in dependencies:
        required = dependency['required_source_facts']
        if not isinstance(required, list) or not required or not all(isinstance(x, str) for x in required):
            raise ValueError('Statutory context fact contract invalid')
        missing = [field for field in required if field not in facts]
        branches.append({'law_id': dependency['law_id'],
                         'source_text_sha256': dependency['text_sha256'],
                         'required_source_facts': required,
                         'missing_source_facts': missing,
                         'diagnostic_facts_complete': not missing,
                         'physical_context_observed': False,
                         'legal_applicability_determined': False})
    return {'format': 'c10316-prior-entry-statutory-context-assessment-v1',
            'contract_sha256': sha(contract_path),
            'source_measurement_sha256': measurement_sha256,
            'facts_sha256': sha(facts_path) if facts_path is not None else None,
            'fact_provenance': provenance, 'branches': branches,
            'cited_exact_sources_absent_from_frozen_inventory':
                contract['cited_exact_sources_absent_from_frozen_inventory'],
            'official_cited_sections_reviewed': contract['official_cited_sections_reviewed'],
            'physical_context_observed': False,
            'legal_applicability_determined': False,
            'selected_delivery_cases': 0}
