"""Versioned exhaustive relevance planning, separate from simulation campaigns.

Only this coordinator writes planning state. Workers use the existing read-only
command adapter. Missing decisions never become negatives. No CARLA dispatch.
"""
import argparse
import asyncio
import fcntl
import hashlib
import json
import math
import sqlite3
import sys
import time
from pathlib import Path
from .store import atomic, encode
from .stages import actors
from .runner import CommandAdapter, RateLimiter, AccountUsageLimitError
from pipeline_paths import OUTPUT_ROOT, PROJECT_ROOT, require_artifact_path

VERSION = 'exhaustive-law-planning-v1'
CONTRACTS = {
    'summary': '''Validate the recovered summary against the current authoritative law and definitions; repair missing/stale structure. Return {law_id, subject, activation, obligations, exceptions, timing, judgments, required_context, unresolved_references, quotations, recovery_notes}. Each structured field is a list (subject may be string). Preserve obligations and unresolved references; do not interpret judgment standards. quotations is a nonempty list of exact substrings supporting the structure. Account for every operative clause.''',
    'actors': '''Review every supplied cell independently using fixed facts, vocabulary definitions, and ALL supplied law subjects. Preserve declared actors. Identify missing specialized subject roles as well as cells with no actors. Do not infer actors from grounding citations. Return {reviews:[{cell_id, assignments:[{actor,reason}], unresolved:[string]}]}. Use existing exact actor IDs from actor_vocabulary; a justified new subject role may be proposed with its own explicit actor ID and reason. Do not substitute a driver for a pedestrian or cyclist. An unresolved subject assignment remains a blocker.''',
    'mapping': '''Evaluate EVERY supplied law for EVERY supplied actor of this cell. Share analysis but retain independent actor-specific decisions. Return {decisions:[{law_id,actor,decision,quote,relevance_type,confidence,reason,required_context}]}. decision is relevant|conditional|irrelevant|unresolved. Include every Cartesian-product member exactly once. Never use grounding/source_laws, keywords or domains as exclusion filters. Include general duties and specialized/pedestrian duties. Compatible unstated conditions mean conditional, not irrelevant. irrelevant requires a concrete contradiction of fixed facts or subject scope. Uncertain exclusion means unresolved. Positive quotes must be exact current-law substrings; relevance_type is specific_match|general_duty; confidence high|medium|low; required_context is a list. No judgment values, compliance outcomes or inferred activation.''',
    'audit': '''Independently re-evaluate every supplied prior decision against current full text, structured law, cell facts and exact actor. Pay particular attention to general duties, compatible unstated context, specialized drivers, pedestrians and misleading grounding citations. Return {decisions:[same complete decision shape as mapping],pattern_findings:[string]}. Include every supplied pair exactly once. Report a missed positive as relevant/conditional; do not preserve a negative merely because it was previously returned.''',
    'evidence': '''For each supplied positive cell/actor/law decision propose active evidence, separately from legal relevance. Return {assignments:[{law_id,actor,branch,context,required_observations,proposal,readiness,capabilities,blockers}]}. branch is a precise active obligation/exception targeted; context and required_observations are lists; proposal is a complete comparison/sweep object or an incomplete proposal naming missing inputs. No inactive controls alone count. Use unlabeled physical sweeps for judgments, never judgment values/cutoffs. capabilities is a list of {path,sha256,description} for locally supplied source supporting simulator, extractor, actor routing and Lean requirements. readiness is supported|blocked. Supported requires complete comparison/sweep, recording requirements, and verified capability references for every required component; otherwise blocked. Include all supplied positives. assignments also contains targeted_requirements:[{id,quote,rationale}] for every supplied demo requirement specifically realized by the proposal; use exact law quotations and do not claim unrelated branches. capabilities entries include scopes:[simulator|extractor|actor_routing|lean]. Explicitly assess 250-2, backing over crosswalks, and backing around corners when compatible. Existing recordings are historical candidates only, not validation proof.'''
}

def contract_for(stage):
    if stage=='mapping_tensor':
        from .law_group_mapping import TENSOR_CONTRACT
        return TENSOR_CONTRACT
    if stage=='actors':
        from .law_actor_resolution import POLICY
        return CONTRACTS[stage]+'\n'+POLICY
    if stage=='actor_resolve':
        from .law_actor_resolution import CONTRACT
        return CONTRACT
    if stage=='mapping_group':
        from .law_group_mapping import CONTRACT
        return CONTRACT
    return CONTRACTS[stage]


def sha(value):
    raw = value if isinstance(value, bytes) else encode(value).encode()
    return hashlib.sha256(raw).hexdigest()


def connect(path, readonly=False):
    db = sqlite3.connect(Path(path).resolve().as_uri() + ('?mode=ro' if readonly else ''), uri=True)
    db.row_factory = sqlite3.Row
    return db


def records(path):
    result = {}
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row['id'] in result:
            raise ValueError('Duplicate law: ' + row['id'])
        result[row['id']] = row
    return result


class Planner:
    def __init__(self, root):
        self.root = require_artifact_path(root)
        self.db = connect(self.root/'planning.sqlite')
        self.db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT);
        CREATE TABLE IF NOT EXISTS jobs(key TEXT PRIMARY KEY,stage TEXT,payload TEXT,status TEXT DEFAULT 'pending',attempts INTEGER DEFAULT 0,error TEXT,result TEXT,metadata TEXT);
        CREATE TABLE IF NOT EXISTS decisions(cell TEXT,actor TEXT,law TEXT,version TEXT,decision TEXT,payload TEXT,receipt TEXT,PRIMARY KEY(cell,actor,law,version));
        CREATE INDEX IF NOT EXISTS decisions_law_actor ON decisions(law,actor,decision);
        CREATE TABLE IF NOT EXISTS receipts(key TEXT PRIMARY KEY,stage TEXT,input_hash TEXT,result_hash TEXT,expected INTEGER,completed INTEGER,created REAL);
        CREATE TABLE IF NOT EXISTS revisions(id INTEGER PRIMARY KEY,cell TEXT,actor TEXT,law TEXT,old_payload TEXT,new_payload TEXT,receipt TEXT);
        ''')
        self.manifest = json.loads((self.root/'manifest.json').read_text())
        if self.manifest['contract_hash'] != sha(CONTRACTS):
            raise ValueError('Processing contract changed; prepare a new versioned package')
        for name,digest in self.manifest.get('frozen_hashes',{}).items():
            if sha((self.root/'inputs'/name).read_bytes())!=digest:
                raise ValueError('Frozen planning input changed: '+name)
        if self.manifest.get('group_contract_hash',sha(contract_for('mapping_group')))!=sha(contract_for('mapping_group')):
            raise ValueError('Grouped processing contract changed; prepare a new package')
        self.catalog = json.loads((self.root/'inputs/catalog.json').read_text())
        self.laws = json.loads((self.root/'inputs/laws.json').read_text())
        self.cells = {c['cell_id']:c for c in self.catalog['cells']}

    def context_refs(self,law_ids=None):
        from .law_contexts import references
        return references(self.root,law_ids)

    def fixed_fact_contract(self,cell_ids):
        cells={c:self.cells[c] for c in sorted(cell_ids)}
        terms={field:{v['id']:v.get('description','') for v in self.catalog.get(field,[]) if v['id'] in {cell[axis] for cell in cells.values()}}
            for field,axis in [('road_layouts','layout'),('maneuvers','maneuver'),('controls','control')]}
        from .law_actor_resolution import POLICY
        return sha({'cells':cells,'terms':terms,'semantics':self.catalog.get('semantics',{}),'actor_scope_policy':POLICY})

    def put(self, stage, payload):
        payload=dict(payload)
        if stage in ('actors','actor_resolve','mapping','mapping_group','mapping_tensor','audit','evidence'):
            ids=payload.get('cells') or [payload['cell']]
            payload['fixed_fact_contract']=self.fixed_fact_contract(ids)
        if stage in ('actors','actor_resolve','mapping','mapping_group','mapping_tensor','audit','evidence'):
            refs=self.context_refs(None if stage in ('actors','actor_resolve') else payload.get('laws',[]))
            if refs:payload['context_refs']=refs
        key = sha([VERSION, contract_for(stage), self.manifest['contract_hash'], stage, payload])
        self.db.execute('INSERT OR IGNORE INTO jobs(key,stage,payload) VALUES(?,?,?)', (key,stage,encode(payload)))
        return key

    def reuse(self):
        source = self.manifest.get('reuse_package')
        if not source:
            return 0
        cached = Planner(source)
        count = 0
        try:
            for row in self.db.execute("SELECT * FROM jobs WHERE status='pending'").fetchall():
                old = cached.db.execute("SELECT * FROM jobs WHERE key=? AND status='completed'",(row['key'],)).fetchone()
                if old:
                    self.accept(row,json.loads(old['result']),{'reused_package':source,'receipt':old['key'],'original_metadata':json.loads(old['metadata'])})
                    count += 1
        finally:
            cached.db.close()
        return count

    def results(self, stage):
        return [json.loads(r[0]) for r in self.db.execute("SELECT result FROM jobs WHERE stage=? AND status='completed' ORDER BY key", (stage,))]

    def summaries(self):
        return {v['law_id']:v for v in self.results('summary')}

    def actor_reviews(self):
        current={v['cell_id']:v for batch in self.results('actors') for v in batch['reviews']}
        for row in self.db.execute("SELECT j.payload,j.result FROM jobs j JOIN receipts r ON r.key=j.key WHERE j.stage='actor_resolve' AND j.status='completed' ORDER BY r.created,j.key"):
            request=json.loads(row['payload'])
            if request.get('fixed_fact_contract')!=self.fixed_fact_contract(request['cells']) or request.get('context_refs',[])!=self.context_refs():
                continue
            for review in json.loads(row['result'])['reviews']:
                cell=review['cell_id']
                if sha(current.get(cell))==request['prior_review_hashes'][cell]:
                    current[cell]=review
        return current

    def resolve_actors(self,reviews):
        attempts={}
        scope=sha(self.context_refs())
        for row in self.db.execute("SELECT key,payload,status FROM jobs WHERE stage='actor_resolve'"):
            request=json.loads(row['payload'])
            if sha(request.get('context_refs',[]))!=scope or request.get('fixed_fact_contract')!=self.fixed_fact_contract(request['cells']):
                if row['status'] in ('pending','failed'):
                    self.db.execute("UPDATE jobs SET status='superseded',error='Retained historical request; supplementary source context changed' WHERE key=?",(row['key'],))
                continue
            for cell in request['cells']:attempts[cell]=attempts.get(cell,0)+1
        selected=sorted(c for c,v in reviews.items() if v['unresolved'] and attempts.get(c,0)<3)
        for offset in range(0,len(selected),10):
            cells=selected[offset:offset+10]
            self.put('actor_resolve',{'cells':cells,'prior_reviews':{c:reviews[c] for c in cells},
                'prior_review_hashes':{c:sha(reviews[c]) for c in cells},
                'cell_hashes':{c:sha(self.cells[c]) for c in cells},'summaries_hash':sha(self.summaries())})
        self.db.commit()
        return bool(self.db.execute("SELECT 1 FROM jobs WHERE stage IN ('actors','actor_resolve') AND status IN ('pending','running')").fetchone())

    def expand(self, batch_size=40):
        summaries = self.summaries()
        if len(summaries) != len(self.laws):
            return
        reviews = self.actor_reviews()
        # All cells get actor review: declared actors alone do not establish
        # completeness for specialized subjects required by current laws.
        if not reviews:
            ids = sorted(self.cells)
            subjects = {k:v['subject'] for k,v in summaries.items()}
            prior_path=self.root/'actor-review-priors.json'
            priors=json.loads(prior_path.read_text()) if prior_path.exists() else {}
            for i in range(0,len(ids),25):
                cells=ids[i:i+25]
                payload={'cells':cells,'subjects':subjects,'summary_hash':sha(summaries)}
                if any(c in priors for c in cells):
                    payload['historical_proposals']={c:priors[c] for c in cells if c in priors}
                    payload['historical_policy']='Previous draft assignments are a starting point only. Independently consider every supplied law subject against the explicit partial-geometry catalog semantics. Preserve original declared roles, not invalid provisional additions.'
                self.put('actors',payload)
        if self.resolve_actors(reviews):
            return
        if self.manifest.get('cell_batch_size',1)>1:
            from .law_group_mapping import cell_groups
            summaries_hashes={k:sha(v) for k,v in summaries.items()}
            law_hashes={k:sha(v) for k,v in self.laws.items()}
            keys=sorted(self.laws)
            for group in cell_groups(self.cells,reviews,self.manifest['cell_batch_size']):
                for offset in range(0,len(keys),batch_size):
                    selected=keys[offset:offset+batch_size]
                    self.put('mapping_tensor',dict(group,laws=selected,
                        cell_hashes={c:sha(self.cells[c]) for c in group['cells']},
                        actor_hashes={c:sha(reviews[c]) for c in group['cells']},
                        law_hashes={k:law_hashes[k] for k in selected},
                        summary_hashes={k:summaries_hashes[k] for k in selected}))
            self.db.commit()
            return
        for cell, review in reviews.items():
            if review['unresolved']:
                continue
            party_ids = sorted(a['actor'] for a in review['assignments'])
            if not party_ids:
                continue
            keys = sorted(self.laws)
            for i in range(0,len(keys),batch_size):
                selected = keys[i:i+batch_size]
                self.put('mapping', {'cell':cell,'actors':party_ids,'laws':selected,
                    'cell_hash':sha(self.cells[cell]),'actor_hash':sha(review),
                    'law_hashes':{k:sha(self.laws[k]) for k in selected},
                    'summary_hashes':{k:sha(summaries[k]) for k in selected}})
        self.db.commit()

    def request(self, row):
        payload = json.loads(row['payload'])
        stage = row['stage']
        inputs = dict(payload)
        if payload.get('fixed_fact_contract'):
            ids=payload.get('cells') or [payload['cell']]
            if payload['fixed_fact_contract']!=self.fixed_fact_contract(ids):raise ValueError('Fixed-fact processing context changed')
            inputs['catalog_semantics']=self.catalog.get('semantics',{})
            from .law_actor_resolution import POLICY
            inputs['actor_scope_policy']=POLICY
        if stage == 'summary':
            inputs['law'] = self.laws[payload['law_id']]
            inputs['definitions'] = json.loads((self.root/'inputs/definitions.json').read_text())
        elif stage in ('mapping_group','mapping_tensor'):
            inputs['cells']=[self.cells[c] for c in payload['cells']]
            inputs['law_records']={k:self.laws[k] for k in payload['laws']}
            reviews=self.actor_reviews()
            inputs['actor_reviews']={c:reviews[c] for c in payload['cells']}
            summaries=self.summaries()
            inputs['summaries']={k:summaries[k] for k in payload['laws']}
            inputs['vocabulary']={k:[v for v in self.catalog[k] if v['id'] in {c[axis] for c in inputs['cells']}]
                for k,axis in [('road_layouts','layout'),('maneuvers','maneuver'),('controls','control')]}
        elif stage in ('actors','actor_resolve'):
            inputs['cells'] = [self.cells[k] for k in payload['cells']]
            inputs['vocabulary']={k:[v for v in self.catalog[k] if v['id'] in {c[axis] for c in inputs['cells']}]
                for k,axis in [('road_layouts','layout'),('maneuvers','maneuver'),('controls','control')]}
            inputs['actor_vocabulary'] = sorted({a for c in self.cells.values() for a in actors(c)})
            if stage=='actor_resolve':
                inputs['law_records']=self.laws
                inputs['verified_structures']=self.summaries()
                inputs['law_subjects']={k:v['subject'] for k,v in self.summaries().items()}
                inputs['vocabulary']={k:[v for v in self.catalog[k] if v['id'] in {c[axis] for c in inputs['cells']}]
                    for k,axis in [('road_layouts','layout'),('maneuvers','maneuver'),('controls','control')]}
                inputs['definitions']=json.loads((self.root/'inputs/definitions.json').read_text())
        else:
            inputs['cell'] = self.cells[payload['cell']]
            inputs['actor_review']=self.actor_reviews().get(payload['cell'])
            inputs['vocabulary'] = {k:[v for v in self.catalog[k] if v['id']==inputs['cell'][axis]]
                for k,axis in [('road_layouts','layout'),('maneuvers','maneuver'),('controls','control')]}
            inputs['law_records'] = {k:self.laws[k] for k in payload['laws']}
            summaries = self.summaries()
            inputs['summaries'] = {k:summaries[k] for k in payload['laws']}
            if stage=='evidence':
                from .stages import CONTRACTS as pipeline_contracts
                inputs['proposal_contract']=pipeline_contracts['cases']
                inputs['capability_sources']=json.loads((self.root/'inputs/capabilities.json').read_text())
                inputs['demo_requirements']=self.demo_requirements()
                inputs['scene_prerequisite_policy']='Every positive planning_scene_requirements entry stays blocked unless resolved_scene_requirements names its exact prior_issue, actual source evidence, and nonempty proposal_refs for the compatible supported setup. No silent deletion of geometry/control prerequisites.'
                inputs['capability_policy']='Provide supported only with current source hashes and scopes simulator, extractor, actor_routing, lean. Missing verified sources means blocked.'
        if payload.get('context_refs'):
            from .law_contexts import load
            inputs['supplemental_corpus_context']=load(self.root,payload['context_refs'],self.laws)
            inputs['supplement_policy']='Exact recovered context from the supplied corpus archive is an explicitly supplied draft input and may be consumed provisionally. Preserve source/version caveats as context; absence of separate approval or online revalidation alone does not block planning. Material source conflicts remain unresolved. Current target-law texts remain authoritative. Excluded archive targets are not selected laws.'
        if row['error']:
            inputs['previous_attempt_error'] = row['error']
            if row['result']:inputs['previous_proposal'] = json.loads(row['result'])
        skill = (self.root/'inputs/relevance-skill.md').read_text()
        return {'stage':'planning_'+stage,'instructions':contract_for(stage), 'skill':skill,
                'processing_contract_version':VERSION,'inputs':inputs}

    def validate(self, stage, p, result):
        from .validation import no_interpretations
        no_interpretations(result)
        if not isinstance(result,dict):
            raise ValueError('Result must be an object')
        if stage == 'actor_resolve':
            from .law_actor_resolution import validate_resolution
            return validate_resolution(self,p,result)
        if stage in ('mapping_group','mapping_tensor'):
            from .law_group_mapping import expand_groups
            expanded=expand_groups(p,result,allow_actor_lists=stage=='mapping_tensor')
            for cell in p['cells']:
                self.validate('mapping',{'cell':cell,'actors':p['actors_by_cell'][cell],'laws':p['laws']},
                    {'decisions':[v for v in expanded if v['cell_id']==cell]})
            result['decisions']=expanded
            return len(expanded)
        if stage == 'summary':
            if result.get('law_id') != p['law_id'] or not result.get('subject'):
                raise ValueError('Summary identity/subject missing')
            for field in ('activation','obligations','exceptions','timing','judgments','required_context','unresolved_references','quotations'):
                if not isinstance(result.get(field),list):
                    raise ValueError('Summary missing structured field: '+field)
            quotes = result['quotations']
            law_text = self.laws[p['law_id']]['text']
            definition_path = self.root/'inputs/definitions.json'
            definitions = json.loads(definition_path.read_text()) if definition_path.exists() else {}
            texts = [law_text]+[d['text'] for values in definitions.values() for d in values]
            if not quotes or any(not isinstance(q,str) or not q or not any(q in text for text in texts) for q in quotes) or not any(q in law_text for q in quotes):
                raise ValueError('Unverified summary quotations')
            result['quotation_sources'] = [{'quote':q,'sources':([p['law_id']] if q in law_text else [])+
                sorted({d['id'] for values in definitions.values() for d in values if q in d['text']})} for q in quotes]
            if not result['obligations']:
                raise ValueError('Summary omitted obligations')
            return 1
        if stage == 'actors':
            values = result.get('reviews',[])
            if len(values)!=len(p['cells']) or {v['cell_id'] for v in values}!=set(p['cells']):
                raise ValueError('Incomplete/duplicate actor reviews')
            for v in values:
                from .law_actor_resolution import validate_scene_requirements
                validate_scene_requirements(self,v['cell_id'],v)
                assignments = v['assignments']
                if not isinstance(v['unresolved'],list) or len({a['actor'] for a in assignments})!=len(assignments):
                    raise ValueError('Invalid actor assignments')
                if not set(actors(self.cells[v['cell_id']])) <= {a['actor'] for a in assignments}:
                    raise ValueError('Declared actors must be preserved')
                if any(not a['reason'].strip() or not a['actor'].strip() for a in assignments):
                    raise ValueError('Actor assignment needs justification')
            return len(values)
        if stage in ('mapping','audit'):
            values = result.get('decisions',[])
            expected = ({(k,a) for k in p['laws'] for a in p['actors']} if stage=='mapping'
                        else {(v['law_id'],v['actor']) for v in p['prior_decisions']})
            if len(values)!=len(expected) or {(v['law_id'],v['actor']) for v in values}!=expected:
                raise ValueError('Incomplete/duplicate per-law actor accounting')
            for v in values:
                if v['decision'] not in ('relevant','conditional','irrelevant','unresolved') or not v.get('reason','').strip():
                    raise ValueError('Invalid decision or missing reason')
                if not isinstance(v.get('required_context'),list) or v.get('confidence') not in ('high','medium','low'):
                    raise ValueError('Missing context/confidence')
                if v['decision'] in ('relevant','conditional'):
                    if not v.get('quote') or v['quote'] not in self.laws[v['law_id']]['text']:
                        raise ValueError('Unverified positive quotation')
                    if v.get('relevance_type') not in ('specific_match','general_duty'):
                        raise ValueError('Invalid relevance type')
                if v['decision']=='conditional' and not v['required_context']:
                    raise ValueError('Conditional candidate needs explicit context')
            return len(expected)
        if stage == 'evidence':
            values = result.get('assignments',[])
            expected = {(v['law_id'],v['actor']) for v in p['positives']}
            if len(values)!=len(expected) or {(v['law_id'],v['actor']) for v in values}!=expected:
                raise ValueError('Incomplete evidence assignments')
            for v in values:
                if not v.get('branch') or not isinstance(v.get('context'),list) or not v.get('required_observations') or not isinstance(v.get('proposal'),dict):
                    raise ValueError('Evidence assignment lacks active branch/context/observations/proposal')
                if v.get('readiness') not in ('supported','blocked') or not isinstance(v.get('blockers'),list):
                    raise ValueError('Missing readiness/blockers')
                if v['readiness']=='supported':
                    proposal = v['proposal']
                    if v['blockers'] or proposal.get('status')!='complete' or not proposal.get('recording_description'):
                        raise ValueError('Unsupported complete evidence claim')
                    if not proposal.get('cases') and not proposal.get('sweep_specs'):
                        raise ValueError('Missing complete comparison/sweep')
                    prior=next(x for x in p['positives'] if x['law_id']==v['law_id'] and x['actor']==v['actor'])
                    needs=prior.get('planning_scene_requirements',[])
                    resolved=v.get('resolved_scene_requirements',[])
                    if needs and (len(resolved)!=len(needs) or {x.get('prior_issue') for x in resolved}!={x['prior_issue'] for x in needs} or any(not x.get('evidence') or not x.get('proposal_refs') for x in resolved)):
                        raise ValueError('Supported evidence must resolve preserved scene prerequisites')
                    from .validation import recording_description
                    from .sweeps import validate_spec
                    recording_description(proposal['recording_description'])
                    for case in proposal.get('cases',[]):
                        if any(k not in case for k in ('case_id','target_law_id','target_type','rationale','variable_assignments','paired_probe_id','deliberate_differences')):
                            raise ValueError('Incomplete active comparison case')
                        if case['target_law_id']!=v['law_id'] or case['target_type']=='baseline':
                            raise ValueError('Inactive or wrong-law controls cannot cover active evidence')
                        recording_description(case.get('recording_description',proposal['recording_description']))
                    complete_sweeps = []
                    for spec in proposal.get('sweep_specs',[]):
                        validate_spec(spec)
                        if spec['target_law_id']!=v['law_id'] or spec['status']!='complete':
                            raise ValueError('Incomplete or wrong-law sweep')
                        recording_description(spec['recording_description'])
                        complete_sweeps.append(spec)
                    if not complete_sweeps and len(proposal.get('cases',[]))<2:
                        raise ValueError('Active coverage requires a complete comparison or sweep')
                    scopes = set()
                    for capability in v.get('capabilities',[]):
                        path = Path(capability['path']).resolve()
                        if PROJECT_ROOT not in path.parents or not path.is_file() or sha(path.read_bytes())!=capability['sha256']:
                            raise ValueError('Unverified capability reference')
                        scopes.update(capability.get('scopes',[]))
                    if not {'simulator','extractor','actor_routing','lean'} <= scopes:
                        raise ValueError('All implementation capability scopes required')
                v.update(cell=p['cell'],law=v['law_id'],covers=[v['law_id']],readiness_score=1 if v['readiness']=='supported' else 0)
                # Explicit branch coverage is independently inspected; no
                # model-provided arbitrary requirement identifiers are trusted.
                v['receipt_source'] = sha(p)
                for target in v.get('targeted_requirements',[]):
                    definition = self.demo_requirements().get(target['id'])
                    if not definition or definition['law']!=v['law_id'] or not target.get('rationale') or not target.get('quote') or target['quote'] not in self.laws[v['law_id']]['text']:
                        raise ValueError('Invalid demo branch witness')
                    v['covers'].append(target['id'])
            return len(expected)
        raise ValueError('Unsupported stage: '+stage)

    def accept(self, row, result, metadata):
        p = json.loads(row['payload'])
        count = self.validate(row['stage'],p,result)
        with self.db:
            if row['stage'] in ('mapping','mapping_group','mapping_tensor','audit'):
                reviews=self.actor_reviews()
                for v in result['decisions']:
                    cell = v['cell_id'] if row['stage'] in ('mapping_group','mapping_tensor') else p['cell']
                    if v['decision'] in ('relevant','conditional') and reviews.get(cell,{}).get('scene_requirements'):
                        v['planning_scene_requirements']=reviews[cell]['scene_requirements']
                    old = self.db.execute('SELECT payload FROM decisions WHERE cell=? AND actor=? AND law=? AND version=?',
                        (cell,v['actor'],v['law_id'],self.manifest['version'])).fetchone()
                    if old and old[0]!=encode(v):
                        self.db.execute('INSERT INTO revisions(cell,actor,law,old_payload,new_payload,receipt) VALUES(?,?,?,?,?,?)',
                            (cell,v['actor'],v['law_id'],old[0],encode(v),row['key']))
                    if row['stage']=='audit' and old and json.loads(old[0])['decision']!=v['decision']:
                        dirty_row = self.db.execute("SELECT value FROM metadata WHERE key='recall_dirty'").fetchone()
                        dirty = json.loads(dirty_row[0]) if dirty_row else []
                        scope = [v['law_id'],v['actor']]
                        if scope not in dirty:dirty.append(scope)
                        self.db.execute("INSERT OR REPLACE INTO metadata VALUES('recall_dirty',?)",(encode(dirty),))
                    self.db.execute('INSERT OR REPLACE INTO decisions VALUES(?,?,?,?,?,?,?)',
                        (cell,v['actor'],v['law_id'],self.manifest['version'],v['decision'],encode(v),row['key']))
            self.db.execute('INSERT INTO receipts VALUES(?,?,?,?,?,?,?)',
                (row['key'],row['stage'],sha(p),sha(result),count,count,time.time()))
            self.db.execute("UPDATE jobs SET status='completed',result=?,metadata=?,error=NULL WHERE key=?",
                (encode(result),encode(metadata),row['key']))

    async def run(self, concurrency=2, rpm=10, timeout=900, limit=0):
        if concurrency<1 or rpm<=0 or timeout<1 or limit<0:
            raise ValueError('Invalid worker limits')
        adapter = CommandAdapter(self.manifest['worker'],timeout)
        limiter = RateLimiter(rpm)
        dispatched = 0
        draining=lambda:(self.root/'drain-request.json').exists()
        # Lock survives async work and prevents another coordinator resetting jobs.
        with (self.root/'coordinator.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.db.execute("UPDATE jobs SET status='pending',error='Interrupted coordinator; prior attempt retained in worker evidence' WHERE status='running'")
            self.db.commit()
            stop = False
            async def worker():
                nonlocal dispatched, stop
                while not stop and not draining() and (not limit or dispatched<limit):
                    row = self.db.execute("SELECT * FROM jobs WHERE status='pending' AND attempts<3 ORDER BY CASE stage WHEN 'summary' THEN 0 WHEN 'actors' THEN 1 WHEN 'actor_resolve' THEN 1 ELSE 2 END,key LIMIT 1").fetchone()
                    if row is None:
                        return
                    dispatched += 1
                    self.db.execute("UPDATE jobs SET status='running',attempts=attempts+1 WHERE key=?",(row['key'],))
                    self.db.commit()
                    await limiter.wait()
                    result = None
                    try:
                        request = self.request(row)
                        evidence = self.root/'worker-evidence'/row['key']/str(row['attempts']+1)
                        request['_worker_evidence_directory'] = str(evidence)
                        result, metadata = await adapter.call(request)
                        self.accept(row,result,metadata)
                    except Exception as exc:
                        failed = row['attempts']+1>=3 or not (getattr(exc,'transient',False) or isinstance(exc,ValueError))
                        self.db.execute('UPDATE jobs SET status=?,error=?,result=? WHERE key=?',
                            ('failed' if failed else 'pending',str(exc),encode(result) if result is not None else None,row['key']))
                        self.db.commit()
                        if isinstance(exc,AccountUsageLimitError):
                            stop = True
                    print(encode(self.status()),flush=True)
            while not stop and not draining() and (not limit or dispatched<limit):
                self.reuse()
                self.expand()
                self.reuse()
                before = dispatched
                await asyncio.gather(*(worker() for _ in range(concurrency)))
                if dispatched==before:
                    if self.advance():
                        continue
                    break
        return self.export()

    def advance(self):
        """Proceed to independent audit and prerequisites once mapping is whole.

        A recall correction re-evaluates every negative in the affected law/actor
        scope, across layouts, before a new independent stratified recheck.
        """
        if self.db.execute("SELECT count(*) FROM jobs WHERE status NOT IN ('completed','superseded')").fetchone()[0]:
            return False
        reviews = self.actor_reviews()
        if len(self.summaries())!=len(self.laws) or len(reviews)!=len(self.cells) or any(v['unresolved'] or not v['assignments'] for v in reviews.values()):
            return False
        dirty = self.db.execute("SELECT value FROM metadata WHERE key='recall_dirty'").fetchone()
        if dirty:
            rounds_row = self.db.execute("SELECT value FROM metadata WHERE key='repair_rounds'").fetchone()
            rounds = int(rounds_row[0]) if rounds_row else 0
            if rounds>=3:return False
            scopes = json.loads(dirty[0])
            by_cell = {}
            for law,actor in scopes:
                for r in self.db.execute("SELECT * FROM decisions WHERE law=? AND actor=? AND decision IN ('irrelevant','unresolved')",(law,actor)):
                    by_cell.setdefault(r['cell'],[]).append(json.loads(r['payload']))
            for cell,values in by_cell.items():
                # Keep the Cartesian product exact by grouping by actor.
                for actor in sorted({v['actor'] for v in values}):
                    selected = sorted({v['law_id'] for v in values if v['actor']==actor})
                    for i in range(0,len(selected),40):
                        laws = selected[i:i+40]
                        self.put('mapping',{'cell':cell,'actors':[actor],'laws':laws,
                            'cell_hash':sha(self.cells[cell]),'summary_hashes':{k:sha(self.summaries()[k]) for k in laws},
                            'law_hashes':{k:sha(self.laws[k]) for k in laws},'actor_hash':sha(reviews[cell]),
                            'repair_round':rounds+1,'affected_scope_findings':scopes,
                            'repair_instruction':'An independent audit changed a decision in this law/actor pattern. Re-evaluate fixed contradictions, compatible context and general duties carefully.'})
            self.db.execute("DELETE FROM metadata WHERE key IN ('recall_dirty','audit_scheduled','evidence_scheduled')")
            self.db.execute("INSERT OR REPLACE INTO metadata VALUES('repair_rounds',?)",(str(rounds+1),))
            self.db.commit()
            if by_cell:return True
        if not self.db.execute("SELECT 1 FROM metadata WHERE key='audit_scheduled'").fetchone():
            rounds = self.db.execute("SELECT value FROM metadata WHERE key='repair_rounds'").fetchone()
            self.audit('law-recall-v1-round-'+(rounds[0] if rounds else '0'))
            self.db.execute("INSERT OR REPLACE INTO metadata VALUES('audit_scheduled','true')")
            self.db.commit()
            return True if self.db.execute("SELECT 1 FROM jobs WHERE status='pending'").fetchone() else self.advance()
        if not self.db.execute("SELECT 1 FROM metadata WHERE key='evidence_scheduled'").fetchone():
            self.evidence()
            self.db.execute("INSERT OR REPLACE INTO metadata VALUES('evidence_scheduled','true')")
            self.db.commit()
            return bool(self.db.execute("SELECT 1 FROM jobs WHERE status='pending'").fetchone())
        return False

    def export(self):
        destination = self.root/'relevance-map.jsonl'
        temporary = destination.with_suffix('.jsonl.tmp')
        with temporary.open('w') as stream:
            for r in self.db.execute('SELECT * FROM decisions ORDER BY cell,actor,law'):
                stream.write(encode(dict(r))+'\n')
        temporary.replace(destination)
        atomic(self.root/'actor-reviews.json',self.actor_reviews())
        atomic(self.root/'processing-receipts.json',[dict(r) for r in self.db.execute('SELECT * FROM receipts ORDER BY key')])
        atomic(self.root/'recall-corrections.json',[dict(r) for r in self.db.execute('SELECT * FROM revisions ORDER BY id')])
        return self.report()

    def status(self):
        return {'version':self.manifest['version'], 'jobs':{r[0]+':'+r[1]:r[2] for r in self.db.execute('SELECT stage,status,count(*) FROM jobs GROUP BY stage,status')},
            'decisions':dict(self.db.execute('SELECT decision,count(*) FROM decisions GROUP BY decision')),
            'comparisons_expected_declared':self.manifest['declared_comparisons']}

    def audit(self, seed='law-recall-v1'):
        """Stratified negatives, every uncertain exclusion and scarce-law negatives."""
        self.expand()
        if self.db.execute("SELECT count(*) FROM jobs WHERE stage IN ('summary','actors','actor_resolve','mapping','mapping_group','mapping_tensor') AND status NOT IN ('completed','superseded')").fetchone()[0]:
            raise ValueError('Exhaustive mapping must finish before recall sampling')
        reviews = self.actor_reviews()
        if len(reviews)!=len(self.cells) or any(v['unresolved'] or not v['assignments'] for v in reviews.values()):
            raise ValueError('Unresolved actor reviews block complete recall audit')
        positive_counts = dict(self.db.execute("SELECT law,count(DISTINCT cell) FROM decisions WHERE decision IN ('relevant','conditional') GROUP BY law"))
        ownership_path = self.root/'ownership-audit.json'
        ownership = json.loads(ownership_path.read_text()) if ownership_path.exists() else {}
        fixed_training = set(ownership.get('fixed_training',[]))
        split_path = self.root/'inputs/splits.json'
        splits = json.loads(split_path.read_text()) if split_path.exists() else {}
        testing_candidates = {r['law'] for r in self.db.execute(
            "SELECT DISTINCT law,cell FROM decisions WHERE decision IN ('relevant','conditional')")
            if r['cell'] not in fixed_training}
        scarce_laws = {law for law in self.laws if positive_counts.get(law,0)<3}
        scarce_laws.update(set(splits.get('train',[]))-testing_candidates)
        strata = {}
        chosen = {}
        uncertain_exclusions = 0
        for r in self.db.execute('SELECT * FROM decisions'):
            v = json.loads(r['payload'])
            if r['decision']=='unresolved':
                chosen[(r['cell'],r['actor'],r['law'])]=v
            elif r['decision']=='irrelevant':
                if v.get('confidence')!='high':
                    chosen[(r['cell'],r['actor'],r['law'])]=v
                    uncertain_exclusions += 1
                key = (r['law'],r['actor'],self.cells[r['cell']]['layout'])
                strata.setdefault(key,[]).append((r['cell'],v))
        for key, members in strata.items():
            members.sort(key=lambda m:sha([seed,key,m[0]]))
            n = len(members) if key[0] in scarce_laws else math.ceil(len(members)*.05)
            for cell,v in members[:n]:
                chosen[(cell,v['actor'],v['law_id'])]=v
        for r in self.db.execute('SELECT DISTINCT cell,actor,law FROM revisions'):
            current = self.db.execute('SELECT payload FROM decisions WHERE cell=? AND actor=? AND law=? AND version=?',
                (r['cell'],r['actor'],r['law'],self.manifest['version'])).fetchone()
            if current:chosen[(r['cell'],r['actor'],r['law'])]=json.loads(current[0])
        by_cell = {}
        for (cell,actor,law),v in chosen.items():
            by_cell.setdefault(cell,[]).append(v)
        for cell, values in sorted(by_cell.items()):
            for i in range(0,len(values),40):
                batch = values[i:i+40]
                self.put('audit',{'cell':cell,'laws':sorted({v['law_id'] for v in batch}),
                    'actors':sorted({v['actor'] for v in batch}),'prior_decisions':batch,
                    'seed':seed,'summaries_hash':sha(self.summaries()),'cell_hash':sha(self.cells[cell])})
        self.db.commit()
        atomic(self.root/'recall-sample.json',{'seed':seed,'strata':len(strata),'sampled':len(chosen),'fraction_minimum':.05,
            'uncertain_exclusions':uncertain_exclusions,'scarce_laws':sorted(scarce_laws),
            'regression_patterns':['general duties','compatible unstated context','specialized drivers','pedestrian obligations','misleading grounding citations']})
        return self.report()

    def demo_requirements(self):
        splits = json.loads((self.root/'inputs/splits.json').read_text())
        result = {}
        for law in splits['demo']:
            for obligation in self.summaries().get(law,{}).get('obligations',[]):
                result['demo:'+law+':'+sha(obligation)[:12]]={'law':law,'obligation':obligation}
        result.update({
            'demo:NRS-484B-250-2:active':{'law':'NRS-484B-250-2','obligation':'Active approximate-simultaneous-arrival evidence'},
            'demo:NRS-484B-113-2:crosswalk':{'law':'NRS-484B-113-2','obligation':'Backing on or over a crosswalk'},
            'demo:NRS-484B-113-2:corner':{'law':'NRS-484B-113-2','obligation':'Backing around a street corner'}})
        return result

    def evidence(self):
        by_cell = {}
        for r in self.db.execute("SELECT * FROM decisions WHERE decision IN ('relevant','conditional')"):
            by_cell.setdefault(r['cell'],[]).append(json.loads(r['payload']))
        for cell, values in by_cell.items():
            for i in range(0,len(values),20):
                batch = values[i:i+20]
                self.put('evidence',{'cell':cell,'laws':sorted({v['law_id'] for v in batch}),
                    'actors':sorted({v['actor'] for v in batch}),'positives':batch,
                    'cell_hash':sha(self.cells[cell]),'summary_hash':sha(self.summaries()),
                    'capability_hash':sha((self.root/'inputs/capabilities.json').read_bytes())})
        self.db.commit()
        return self.report()

    def report(self):
        status = self.status()
        total = self.db.execute('SELECT count(*) FROM decisions').fetchone()[0]
        reviews = self.actor_reviews()
        expected = sum(len(v['assignments'])*len(self.laws) for v in reviews.values() if not v['unresolved'])
        revisions = self.db.execute('SELECT count(*) FROM revisions').fetchone()[0]
        blockers = []
        if len(self.summaries())!=len(self.laws):blockers.append('Structured law verification incomplete')
        if len(reviews)!=len(self.cells) or any(v['unresolved'] or not v['assignments'] for v in reviews.values()):blockers.append('Subject-role review incomplete or unresolved')
        if not expected or total!=expected:blockers.append('Exhaustive decision accounting incomplete')
        if self.db.execute("SELECT count(*) FROM decisions WHERE decision='unresolved'").fetchone()[0]:blockers.append('Unresolved relevance decisions')
        if not (self.root/'recall-sample.json').exists():blockers.append('Independent recall audit not yet scheduled')
        if self.db.execute("SELECT count(*) FROM jobs WHERE stage='audit' AND status NOT IN ('completed','superseded')").fetchone()[0]:blockers.append('Independent recall audit incomplete')
        if self.db.execute("SELECT 1 FROM metadata WHERE key='recall_dirty'").fetchone():blockers.append('Audit corrections require affected-pattern repair and recheck; see revisions')
        if self.db.execute("SELECT 1 FROM jobs WHERE status='failed'").fetchone():blockers.append('Failed semantic jobs require diagnosed repair')
        ownership_path = self.root/'ownership-audit.json'
        recorded = json.loads(ownership_path.read_text()) if ownership_path.exists() else {}
        status.update({'historical_heldout_recorded_target_law_count':len(recorded.get('heldout_recorded_current_test_targets',[])),
            'fixed_training_cell_count':len(recorded.get('fixed_training',[])),
            'heldout_replacement_cells':recorded.get('heldout_replacement_required',[]),'comparison_rows':total,'reviewed_actor_comparisons_expected':expected,'blockers':blockers,
            'selected_coverage':None,'currently_executable_coverage':None,'already_recorded_coverage':'Historical targets inventoried; evidence validation required',
            'exact_minimum_proven':False,
            'failed_jobs':[dict(r) for r in self.db.execute("SELECT key,stage,error,attempts FROM jobs WHERE status='failed'")]})
        atomic(self.root/'progress.json',status)
        return status


def prepare(root, catalog_path, corpus, reuse=None, cell_batch_size=25):
    if type(cell_batch_size) is not int or cell_batch_size<1:raise ValueError('Cell batch size must be positive')
    root = require_artifact_path(root)
    if root.exists():raise ValueError('Planning package already exists; use run/status to resume')
    c = json.loads(Path(catalog_path).read_text())
    from catalog import validate_catalog
    validate_catalog(c)
    splits = {name:records(corpus/'example'/name/'laws.jsonl') for name in ('train','test','demo')}
    if not set(splits['demo'])<=set(splits['train']):raise ValueError('Demo is not a training subset')
    if set(splits['train']) & set(splits['test']):raise ValueError('Law splits overlap')
    laws = dict(splits['train'],**splits['test'])
    full = records(corpus/'full_list/laws.jsonl')
    for k,v in laws.items():
        if k not in full or v['text']!=full[k]['text']:raise ValueError('Split/full-text mismatch: '+k)
    root.mkdir(parents=True)
    sources = [Path(catalog_path),corpus/'full_list/laws.jsonl',Path(__file__),PROJECT_ROOT/'scenario_pipeline/skills/law-relevance-mapping/SKILL.md',
        PROJECT_ROOT/'scenario_pipeline/batch_pipeline/law_partitions.py',
        PROJECT_ROOT/'scenario_pipeline/batch_pipeline/law_group_mapping.py',
        PROJECT_ROOT/'scenario_pipeline/batch_pipeline/validation.py',
        PROJECT_ROOT/'scenario_pipeline/batch_pipeline/sweeps.py',
        PROJECT_ROOT/'scenario_pipeline/pipeline.py']
    definitions = {}
    for name in splits:
        p = corpus/'example'/name/'definitions.jsonl'
        sources.append(corpus/'example'/name/'laws.jsonl')
        if p.exists():sources.append(p);definitions[name]=[json.loads(x) for x in p.read_text().splitlines() if x.strip()]
    summaries = {}
    ownership = []
    history = []
    workers = []
    # Read transactions establish a consistent per-database view, including WAL.
    for path in sorted((OUTPUT_ROOT/'state').glob('*.sqlite')):
        db = connect(path,True)
        try:
            db.execute('BEGIN')
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='runs'").fetchone():continue
            runrows = db.execute('SELECT * FROM runs').fetchall()
            for row in runrows:
                config = json.loads(row['config'])
                for k,v in config.get('summaries',{}).items():
                    if k in laws:summaries.setdefault(k,[]).append({'source':str(path),'run':row['id'],'summary':v})
                if row['id']=='production-motor-v1':workers.append(config['model']['worker_argv'])
            for row in db.execute("SELECT j.*,r.run_id,r.active FROM jobs j JOIN run_jobs r ON r.job_id=j.id WHERE j.stage='execution'"):
                p = json.loads(row['payload']); run = row['run_id'];cell = p.get('cell',{}).get('cell_id',row['entity'].split(':')[0])
                split = 'training' if run.startswith('production-motor-v') or 'fewshot' in run else 'heldout' if run.startswith('heldout-') else 'historical-demo' if run.startswith('demo') else 'unassigned'
                item = {'source_db':str(path),'run':run,'job':row['id'],'active':row['active'],'cell':cell,'actor':row['actor'],'split':split,
                    'target_law':p.get('case',{}).get('target_law_id'),'case':p.get('case',{}).get('case_id'),'status':row['status'],'artifact_id':row['artifact_id'],
                    'eligibility':'requires_evidence_validation','payload_hash':sha(p)}
                history.append(item)
                if split in ('training','heldout'):ownership.append(item)
        finally:db.close()
    for path in sorted((OUTPUT_ROOT/'inputs/fewshots').glob('*/example.json')):
        v = json.loads(path.read_text());sources.append(path)
        ownership.append({'source':str(path),'cell':v['cell_id'],'split':'training','reason':'indexed fewshot recording selection'})
    # The independent held-out campaign and later production continuations
    # use private orchestration state rather than state/*.sqlite jobs.
    explicit_sources = [
        (OUTPUT_ROOT/'work/production-motor-v2/inputs/ownership.json','training','ordered_cells'),
        (OUTPUT_ROOT/'work/production-motor-v2/orchestration/driver-state.json','training','selected_cell_order'),
        (OUTPUT_ROOT/'work/production-motor-v1/orchestration/selected-group-current-audit.json','training','groups'),
        (OUTPUT_ROOT/'work/held-out-v1/run.json','heldout','selected_cells')]
    for path,split,field in explicit_sources:
        if not path.exists():continue
        sources.append(path)
        snapshot = json.loads(path.read_text())
        for item in snapshot[field]:
            cell = item if isinstance(item,str) else item['cell_id']
            if field=='groups' and not item.get('selected_cases'):continue
            ownership.append({'source':str(path),'cell':cell,'split':split,'reason':'explicit simulation selection including pending work'})
    delivery = OUTPUT_ROOT/'work/held-out-v1/delivery_index.json'
    if delivery.exists():
        sources.append(delivery)
        for row in json.loads(delivery.read_text())['cases']:
            history.append({'source':str(delivery),'run':'held-out-v1','cell':row['cell_id'],'actor':row['actor'],
                'split':'heldout','target_law':row['law_id'],'case':row['case_id'],'status':'historically_validated',
                'source_attempt':row.get('source_attempt'),'trace_sha256':row.get('trace_sha256'),
                'eligibility':'requires_partition_and_current_evidence_validation','payload_hash':sha(row)})
    if not workers:raise ValueError('No configured production semantic worker found')
    for worker_path in workers[0][1:]:
        if Path(worker_path).is_file():sources.append(Path(worker_path))
    capability_paths = [PROJECT_ROOT/'README.md',
        PROJECT_ROOT/'scenario_pipeline/docs/traffic_spec_adapter.md',
        PROJECT_ROOT/'scenario_pipeline/scripts/pipeline_capture.py',
        PROJECT_ROOT/'scenario_pipeline/batch_pipeline/construction_contract.py',
        OUTPUT_ROOT/'work/production-motor-v2/inputs/atom_contract.json']
    capabilities = []
    for path in capability_paths:
        if path.exists():
            sources.append(path)
            capabilities.append({'path':str(path.resolve()),'sha256':sha(path.read_bytes()),'content':path.read_text()})
    atomic(root/'inputs/capabilities.json',capabilities)
    for p in sources:
        destination = root/'inputs/source-snapshots'/sha(str(p.resolve()))/p.name
        destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(p.read_bytes())
    skill = PROJECT_ROOT/'scenario_pipeline/skills/law-relevance-mapping/SKILL.md'
    (root/'inputs/relevance-skill.md').write_bytes(skill.read_bytes())
    for name,value in [('catalog',c),('laws',laws),('definitions',definitions),('recovered-summaries',summaries),('splits',{k:sorted(v) for k,v in splits.items()}),('ownership',ownership),('recording-history',history)]:
        atomic(root/'inputs'/(name+'.json'),value)
    declared = sum(len(actors(cell)) for cell in c['cells'])
    hashes = {str(p.resolve()):sha(p.read_bytes()) for p in sources}
    frozen_hashes = {p.name:sha(p.read_bytes()) for p in (root/'inputs').glob('*') if p.is_file()}
    manifest = {'frozen_hashes':frozen_hashes,'version':sha([VERSION,hashes,sha(summaries),sha(ownership),cell_batch_size]),'processing_version':VERSION,'cell_batch_size':cell_batch_size,'group_contract_hash':sha(contract_for('mapping_group')),'contract_hash':sha(CONTRACTS),
        'input_hashes':hashes,'worker':workers[0],'cells':len(c['cells']),'declared_cell_actors':declared,
        'cells_without_declared_actors':sum(not actors(cell) for cell in c['cells']), 'laws':len(laws),
        'splits':{k:len(v) for k,v in splits.items()},'declared_comparisons':declared*len(laws),
        'reuse_package':str(reuse.resolve()) if reuse else None,
        'created_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'concurrency':2,'requests_per_minute':10}
    atomic(root/'manifest.json',manifest)
    atomic(root/'inputs/processing-contracts.json',dict(CONTRACTS,mapping_group=contract_for('mapping_group')))
    training = {r['cell'] for r in ownership if r['split']=='training'}
    heldout = {r['cell'] for r in ownership if r['split']=='heldout'}
    atomic(root/'ownership-audit.json',{'fixed_training':sorted(training),'retained_heldout_candidates':sorted(heldout-training),
        'heldout_replacement_required':sorted(training & heldout), 'known_overlap_cells':['C131055','C323989','C394300'],
        'demo_recordings':[dict(r,eligibility='excluded_training_cell_owned' if r['cell'] in training else 'requires_partition_and_evidence_validation') for r in history if r['split']=='historical-demo'],
        'heldout_recorded_current_test_targets':sorted({r['target_law'] for r in history if r['split']=='heldout' and r['status']=='historically_validated' and r['target_law'] in splits['test']}),
        'heldout_recording_eligibility':[dict(r,eligibility='excluded_training_ownership_requires_replacement' if r['cell'] in training else 'compatible_assignment_requires_current_evidence_validation') for r in history if r['split']=='heldout'],
        'heldout_selected_current_test_targets':sorted({r['target_law'] for r in history if r['split']=='heldout' and r['target_law'] in splits['test']}),
        'policy':'Simulation selection establishes fixed training ownership, including pending and historical selections; relevance processing alone does not.'})
    planner = Planner(root)
    for k in sorted(laws):
        unique = {}
        for candidate in summaries.get(k,[]):
            unique.setdefault(sha(candidate['summary']),candidate)
        planner.put('summary',{'law_id':k,'law_hash':sha(laws[k]),'candidates':list(unique.values()),'definitions_hash':sha(definitions)})
    planner.db.commit()
    return planner.report()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run','status','export','audit','evidence','optimize'))
    parser.add_argument('--package',type=Path,required=True)
    parser.add_argument('--catalog',type=Path,default=OUTPUT_ROOT/'inputs/catalog/vocabulary_catalog.json')
    parser.add_argument('--corpus',type=Path,default=PROJECT_ROOT/'repo_prep/nevada_sydney/pipeline/traffic-spec-agent/laws')
    parser.add_argument('--reuse',type=Path,help='Reuse only exact contract and per-batch input matches from another planning package')
    parser.add_argument('--cell-batch-size',type=int,default=25,help='Shared layout/maneuver analysis; every cell/actor/law still receives its own decision')
    parser.add_argument('--limit',type=int,default=0)
    parser.add_argument('--timeout',type=int,default=900)
    parser.add_argument('--solver-timeout',type=int,default=30,
        help='Per-objective solver time budget in seconds; retain feasible incumbents without claiming optimality')
    parser.add_argument('--concurrency',type=int,default=2,help='Semantic requests in flight; initial trial uses two')
    parser.add_argument('--requests-per-minute',type=float,default=10,help='Global start-rate limit across all planning workers')
    parser.add_argument('--candidates',type=Path)
    args = parser.parse_args(argv)
    if args.action=='prepare':value = prepare(args.package,args.catalog,args.corpus,args.reuse,args.cell_batch_size)
    else:
        p = Planner(args.package)
        if args.action=='run':value = asyncio.run(p.run(concurrency=args.concurrency,rpm=args.requests_per_minute,timeout=args.timeout,limit=args.limit))
        elif args.action=='export':value = p.export()
        elif args.action=='audit':value = p.audit()
        elif args.action=='evidence':value = p.evidence()
        elif args.action=='optimize':
            from .law_partitions import optimize_package
            value = optimize_package(p,args.candidates,args.solver_timeout)
        else:value = p.report()
    print(json.dumps(value,indent=2))
    return 0

if __name__=='__main__':raise SystemExit(main())
