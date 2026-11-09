"""Coverage-first law search. Unsearched cells remain unevaluated, never negative."""
import argparse
import asyncio
import fcntl
import json
import sqlite3
import time
from pathlib import Path

from .law_planning import Planner, sha
from .law_partitions import solve
from .law_selection_audit import verify_solution
from .runner import CommandAdapter, RateLimiter, AccountUsageLimitError
from .stages import actors
from .store import atomic, encode

CONTRACT = '''Find positive active law-to-cell witnesses in the supplied candidate pool.
Catalog annotations only prioritize discovery; they are NOT evidence of relevance.
Read each full law and verified structured record. Evaluate actual fixed facts,
actor subject, activation, exceptions and timing. Compatible unstated conditions
are conditional, not exclusions. Never invent an actor outside available_actors.
Return {laws:[{law_id,assignments:[{cell,actor,quote,decision,relevance_type,
confidence,reason,required_context,branch,subject_reason,covers,
targeted_requirements:[{id,quote,rationale}]}],evidence_plan:{active_setup,
observations:[string],comparison_or_sweep,implementation_prerequisites:[string]},
unresolved:[string]}]} for EVERY supplied law, including those with no witnesses.
Use only supplied cell IDs. decision relevant|conditional; relevance_type
specific_match|general_duty; confidence high|medium|low. quote MUST be an exact
nonempty substring of the current target law. covers includes law_id and only
demo IDs specifically realized by this active assignment; quote each demo branch
in targeted_requirements using EXACT SUBSTRINGS OF full_text.text, never the
paraphrased demo_requirements.obligation or structured record. required_context is a list of compatible setup facts,
never silently assume them. subject_reason must justify this exact party.
For training laws return at least FOUR distinct compatible cell alternatives,
including at least TWO not reserved for training/heldout, unless truly impossible.
For heldout laws return at least THREE alternatives, preferably existing heldout
cells where compatible. If demo requirements exist, provide a training-eligible
active witness for EVERY demo obligation, using multiple cells when necessary.
Choose clear specific matches over tenuous general candidates. It is acceptable
to propose prohibited behavior for recording. No inactive-law control alone is
coverage. Fixed cell geometry, maneuver and control cannot be changed by context.
Review scene_requirements, preserving them as prerequisites. State uncertainty
explicitly; do not force a witness when subject/fixed facts conflict.
Each law's evidence_plan must describe active setup and raw physical observations,
plain/statutory comparisons or unlabeled physical sweeps for judgment phrases.
Never interpret judgment standards, choose legal judgment cutoffs or label
judgment sweeps. Statutory numeric values may be retained. Feasibility is unverified;
list simulator/extractor/actor-routing/Lean prerequisites honestly. Do not claim
recorded coverage. Keep output concise. Unchosen candidates are UNEVALUATED, not
irrelevant. If the pool is inadequate explain missing facts in unresolved.
'''

AUDIT_CONTRACT = '''Independently audit EVERY supplied positive assignment using
the authoritative current law, fixed scene facts, exact actor subject and the
proposed active branch. Prior reasoning is a draft, not authority. Check general
duties, missing compatible context, specialized actors, exceptions and timing.
This is POTENTIAL relevance, not proof that a law activates or a judgment is true.
An unresolved legal interaction must remain explicit; it does not by itself prove
that a compatible scene is irrelevant. Accept a conditional candidate only if a
potentially operative physical setup can be described without contradicting fixed
facts and the subject scope. Do not demand a complete legal interpretation as a
prerequisite for potential relevance. Conversely, if the law and fixed facts rule
out every operative setup, reject it; if no defensible potential setup can be
identified, keep uncertain. Never conceal an unresolved legal applicability issue
or describe potential coverage as executable, recorded or determinate coverage.
Return {reviews:[{law_id,cell,actor,verdict,reason,additional_context:[],
accepted_demo_requirements:[]}],pattern_findings:[]}.
verdict accept|reject|uncertain. Include every supplied (law_id,cell,actor) once.
Accept conditional legal relevance only when the required setup could be true
without contradicting fixed layout, maneuver or control. Check physical object
meaning in the supplied vocabulary. A prohibited action may be an active example.
Each claimed demo branch must actually be realizable in THIS cell; retain only
valid IDs in accepted_demo_requirements. Never infer relevance from citations.
If active relevance or the exact subject cannot be justified, reject or mark
uncertain; explain the conflict. Preserve unresolved scene prerequisites.
Do not claim verified execution, recorded evidence or legal judgment meanings.
'''


class Focused:
    def __init__(self, source, root):
        self.planner = Planner(source)
        self.root = self.planner.root.parent / root
        self.root.mkdir(parents=True, exist_ok=True)
        if (self.root/'manifest.json').exists():
            saved=json.loads((self.root/'manifest.json').read_text())
            if saved['source_package']!=str(self.planner.root) or saved['source_version']!=self.planner.manifest['version']:
                raise ValueError('Focused package belongs to different frozen inputs; use a new --name')
        self.db = sqlite3.connect(str(self.root/'focused.sqlite'))
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS jobs(key TEXT PRIMARY KEY,request TEXT,status TEXT,
        attempts INTEGER DEFAULT 0,result TEXT,error TEXT,metadata TEXT);
        CREATE TABLE IF NOT EXISTS audits(key TEXT PRIMARY KEY,request TEXT,status TEXT,
        attempts INTEGER DEFAULT 0,result TEXT,error TEXT,metadata TEXT);
        ''')
        self.splits = json.loads((self.planner.root/'inputs/splits.json').read_text())
        self.ownership = json.loads((self.planner.root/'ownership-audit.json').read_text())
        self.fixed = set(self.ownership['fixed_training'])
        self.retained = set(self.ownership['retained_heldout_candidates'])-self.fixed
        self.demo = self.planner.demo_requirements()
        self.summaries = self.planner.summaries()
        self.reviews = self.planner.actor_reviews()
        self.terms = {axis:{v['id']:v.get('description','') for v in self.planner.catalog[field]}
            for axis,field in [('layout','road_layouts'),('maneuver','maneuvers'),('control','controls')]}

    def cell(self, cell):
        c = self.planner.cells[cell]
        review = self.reviews.get(cell,{})
        declared = set(actors(c))
        assigned = {a['actor'] for a in review.get('assignments',[])}
        return {'cell_id':cell, **{a:c[a] for a in self.terms},
            'term_descriptions':{a:self.terms[a].get(c[a],'') for a in self.terms},
            'available_actors':sorted(declared|assigned),
            'actor_provenance':'reviewed' if review else 'declared_catalog',
            'scene_requirements':review.get('scene_requirements',[]),
            'reserved_split':'training' if cell in self.fixed else 'heldout' if cell in self.retained else None}

    def pool(self, law, size=28, offset=0):
        ann = self.planner.catalog.get('law_analysis',{}).get(law,{})
        ranking = []
        for cid,c in self.planner.cells.items():
            if not actors(c) and cid not in self.reviews:continue
            score = 0
            for axis,field in [('layout','road_layouts'),('maneuver','maneuvers'),('control','controls')]:
                if c[axis] in ann.get(field,[]):score += {'layout':3,'maneuver':6,'control':5}[axis]
            for pattern in ann.get('fact_patterns',[]):
                if all(not pattern.get(f) or c[a] in pattern[f] for a,f in [('layout','road_layouts'),('maneuver','maneuvers'),('control','controls')]):score+=12
            if law in c.get('source_laws',[]):score+=2
            if cid in self.fixed or cid in self.retained:score+=1
            ranking.append((-score,cid))
        ranking.sort()
        # Include diverse controls and reserved cells while retaining alternatives
        # for the same strongest scene. No candidate outside this pool is excluded.
        chosen=[]; seen={}
        ranked=ranking[offset:]
        for _,cid in ranked:
            c=self.planner.cells[cid]; signature=(c['layout'],c['maneuver'],c['control'])
            if seen.get(signature,0)>=3:continue
            chosen.append(cid);seen[signature]=seen.get(signature,0)+1
            if len(chosen)>=size:break
        return [self.cell(c) for c in chosen]

    def prepare(self, batch=4):
        laws=sorted(self.planner.laws)
        for i in range(0,len(laws),batch):
            ids=laws[i:i+batch]
            inputs={'laws':{k:{'full_text':self.planner.laws[k],
                'structured':self.summaries[k],
                'split':'heldout' if k in self.splits['test'] else 'training_testing',
                'demo_requirements':{d:v for d,v in self.demo.items() if v['law']==k},
                'candidates':self.pool(k)} for k in ids},
                'catalog_semantics':self.planner.catalog.get('semantics',{})}
            refs=self.planner.context_refs(ids)
            if refs:
                from .law_contexts import load
                inputs['supplemental_context']=load(self.planner.root,refs,self.planner.laws)
            req={'stage':'focused_law_selection','instructions':CONTRACT,
                 'skill':(self.planner.root/'inputs/relevance-skill.md').read_text(),'inputs':inputs}
            key=sha(req)
            self.db.execute('INSERT OR IGNORE INTO jobs(key,request,status) VALUES(?,?,?)',(key,encode(req),'pending'))
        self.db.commit()
        atomic(self.root/'manifest.json',{'source_package':str(self.planner.root),
            'source_version':self.planner.manifest['version'],'contract_hash':sha(CONTRACT),
            'strategy':'law-first prioritized candidate pools; no exhaustive or exact-minimum claim',
            'requirements':{'training':221,'testing':221,'heldout':28,'training_demo_branches':len(self.demo)},
            'worker':self.planner.manifest['worker']})

    def validate(self, req, result):
        from .validation import no_interpretations
        no_interpretations(result)
        values=result.get('laws',[]); requested=req['inputs']['laws']
        if len(values)!=len(requested) or {v['law_id'] for v in values}!=set(requested):raise ValueError('Missing/duplicate laws')
        for v in values:
            law=v['law_id']; pool={c['cell_id']:c for c in requested[law]['candidates']}
            if not isinstance(v.get('unresolved'),list):raise ValueError('Missing unresolved accounting')
            plan=v.get('evidence_plan',{})
            if not all(plan.get(k) for k in ('active_setup','observations','comparison_or_sweep','implementation_prerequisites')):raise ValueError('Missing active evidence proposal/prerequisites')
            seen=set()
            for a in v.get('assignments',[]):
                if a['cell'] not in pool or a['actor'] not in pool[a['cell']]['available_actors']:raise ValueError('Unknown cell/actor')
                if (a['cell'],a['actor']) in seen:raise ValueError('Duplicate assignment')
                seen.add((a['cell'],a['actor']))
                if not a.get('quote') or a['quote'] not in self.planner.laws[law]['text']:raise ValueError('Unverified quotation: '+law)
                if not a.get('branch') or not a.get('subject_reason') or not a.get('reason'):raise ValueError('Missing branch/subject justification')
                if a.get('decision') not in ('relevant','conditional') or a.get('confidence') not in ('high','medium','low'):raise ValueError('Invalid relevance decision')
                if not isinstance(a.get('required_context'),list) or a['decision']=='conditional' and not a['required_context']:raise ValueError('Missing conditional context')
                covers=a.get('covers',[])
                if law not in covers or any(k!=law and (k not in self.demo or self.demo[k]['law']!=law) for k in covers):raise ValueError('Invalid coverage claim')
                tagged={t['id'] for t in a.get('targeted_requirements',[]) if t.get('quote') and t['quote'] in self.planner.laws[law]['text'] and t.get('rationale')}
                if set(covers)-{law}-tagged:raise ValueError('Unquoted demo obligation for '+law+': '+str(sorted(set(covers)-{law}-tagged))+'. targeted_requirements.quote must be an EXACT substring of full_text.text, not a paraphrase from the obligation summary.')
        return result

    def prepare_audit(self, retry_context=False, law_filter=()):
        report=json.loads((self.root/'partitions.json').read_text())
        selected={}
        for a in report.get('witnesses',[]):
            if a.get('audit_status')=='accepted':continue
            selected.setdefault(a['law'],{})[(a['cell'],a['actor'])]=a
        if retry_context:
            latest={}
            for old in self.db.execute("SELECT result FROM audits WHERE status='completed' ORDER BY rowid"):
                for a in json.loads(old['result'])['reviews']:latest[a['law_id'],a['cell'],a['actor']]=a['verdict']
            for row in self.db.execute("SELECT * FROM audits WHERE status IN ('completed','pending','failed') ORDER BY rowid").fetchall():
                request=json.loads(row['request'])
                uncertain=set()
                if row['status']=='completed':
                    uncertain={(a['law_id'],a['cell'],a['actor']) for a in json.loads(row['result'])['reviews'] if latest[a['law_id'],a['cell'],a['actor']]=='uncertain'}
                for law,v in request['inputs']['laws'].items():
                    for a in v['assignments']:
                        if row['status']!='completed' or (law,a['cell'],a['actor']) in uncertain:
                            selected.setdefault(law,{})[a['cell'],a['actor']]=a
                if row['status'] in ('pending','failed'):
                    self.db.execute("UPDATE audits SET status='superseded' WHERE key=?",(row['key'],))
        if law_filter:selected={k:v for k,v in selected.items() if k in law_filter}
        keys=sorted(selected)
        for i in range(0,len(keys),8):
            ids=keys[i:i+8]
            inputs={'laws':{k:{'full_text':self.planner.laws[k],
                'structured':self.summaries[k],
                'assignments':list(selected[k].values()),
                'cells':{a['cell']:self.cell(a['cell']) for a in selected[k].values()},
                'demo_requirements':{d:v for d,v in self.demo.items() if v['law']==k}}
                for k in ids},'catalog_semantics':self.planner.catalog.get('semantics',{})}
            # Referenced current laws and recovered scope provisions are inputs,
            # not new coverage targets. Their omission can create false blockers.
            references={}
            text=encode(inputs['laws'])
            for _ in range(3):
                added={k:v for k,v in self.planner.laws.items() if k not in ids and k not in references and k in text}
                if not added:break
                references.update(added);text+=encode(added)
            inputs['referenced_current_laws']=references
            definitions=json.loads((self.planner.root/'inputs/definitions.json').read_text())
            inputs['definitions']=list({sha(d):d for values in definitions.values() for d in values}.values())
            refs=self.planner.context_refs(ids)
            if refs:
                from .law_contexts import load
                inputs['supplemental_corpus_context']=load(self.planner.root,refs,self.planner.laws)
            inputs['source_context_policy']='Consume supplied current cross-references and hash-verified recovered corpus provisions provisionally, preserving version caveats; an available supplied source is not missing solely because it was recovered from the corpus archive.'
            req={'stage':'focused_law_audit','instructions':AUDIT_CONTRACT,
                'skill':(self.planner.root/'inputs/relevance-skill.md').read_text(),'inputs':inputs}
            self.db.execute('INSERT OR IGNORE INTO audits(key,request,status) VALUES(?,?,?)',(sha(req),encode(req),'pending'))
        self.db.commit()
        return self.status()

    def repair(self, explicit_laws=()):
        progress=self.export()
        needed={self.demo[k]['law'] if k in self.demo else k
            for missing in progress['missing'].values() for k in missing}
        needed.update(explicit_laws)
        candidates=json.loads((self.root/'candidates.json').read_text())
        for law in self.splits['train']:
            train={a['cell'] for a in candidates if a['law']==law and 'training' in a['splits']}
            test={a['cell'] for a in candidates if a['law']==law and 'testing' in a['splits']}
            if not any(train-{c} for c in test):needed.add(law)
        previous={}
        for row in self.db.execute("SELECT request,result FROM jobs WHERE status='completed'"):
            result=json.loads(row['result'])
            for v in result['laws']:previous[v['law_id']]=v
        queued=0
        for law in sorted(needed):
            prior=json.dumps(previous.get(law,{}))
            # Expand the prioritized search; a small head is retained for branch
            # alternatives and later ranks supply genuinely new candidate scenes.
            pool={c['cell_id']:c for c in self.pool(law,size=12)+self.pool(law,size=60,offset=20)}
            if law in explicit_laws:
                used={a['cell'] for a in candidates if a['law']==law}
                pool={cid:c for cid,c in pool.items() if cid not in used and not c['reserved_split']}
            inputs={'laws':{law:{'full_text':self.planner.laws[law],
                'structured':self.summaries[law],
                'split':'heldout' if law in self.splits['test'] else 'training_testing',
                'demo_requirements':{} if law in explicit_laws else {d:v for d,v in self.demo.items() if v['law']==law},
                'candidates':list(pool.values()),'previous_search':json.loads(prior)}},
                'catalog_semantics':self.planner.catalog.get('semantics',{})}
            if law in explicit_laws:
                inputs['repair_goal']='Find at least TWO NEW test-eligible active cell alternatives; existing cells are exhausted by other split requirements. Demo branches are already covered in training and need not be repeated.'
            req={'stage':'focused_law_selection','instructions':CONTRACT,
                'skill':(self.planner.root/'inputs/relevance-skill.md').read_text(),'inputs':inputs}
            queued+=self.db.execute('INSERT OR IGNORE INTO jobs(key,request,status) VALUES(?,?,?)',(sha(req),encode(req),'pending')).rowcount
        self.db.commit()
        return {'repair_laws':sorted(needed),'new_batches':queued,**self.status()}

    def recover(self):
        """Salvage independently valid sibling laws without changing raw evidence."""
        recovered=[]
        for row in self.db.execute("SELECT * FROM jobs WHERE status='failed'").fetchall():
            request=json.loads(row['request'])
            files=sorted((self.root/'worker-evidence'/row['key']).glob('*/response.json'),reverse=True)
            if not files:continue
            try:response=json.loads(files[0].read_text())
            except ValueError:continue
            for value in response.get('laws',[]):
                law=value.get('law_id')
                if law not in request['inputs']['laws']:continue
                req=dict(request,inputs=dict(request['inputs'],laws={law:request['inputs']['laws'][law]}))
                result={'laws':[value]}
                normalizations=[]
                # A paraphrased branch quote may be replaced by its complete
                # authoritative target law, without altering any branch claim.
                # Independent semantic audit still decides whether that law
                # supports the claimed branch in this particular scene.
                for assignment in value.get('assignments',[]):
                    for target in assignment.get('targeted_requirements',[]):
                        if target.get('id') in self.demo and self.demo[target['id']]['law']==law and (not isinstance(target.get('quote'),str) or target['quote'] not in self.planner.laws[law]['text']):
                            normalizations.append({'id':target['id'],'cell':assignment['cell'],
                                'original_quote':target.get('quote'),'replacement':'complete authoritative law text'})
                            target['quote']=self.planner.laws[law]['text']
                try:self.validate(req,result)
                except (ValueError,KeyError,TypeError):continue
                key=sha(req)
                if key==row['key']:continue
                self.db.execute('INSERT OR IGNORE INTO jobs(key,request,status,result,metadata) VALUES(?,?,?,?,?)',
                    (key,encode(req),'completed',encode(result),encode({'recovered_from_job':row['key'],
                        'worker_response':str(files[0]),'response_sha256':sha(files[0].read_bytes()),
                        'quotation_normalizations':normalizations})))
                recovered.append(law)
            self.db.execute("UPDATE jobs SET status='superseded' WHERE key=?",(row['key'],))
        self.db.commit()
        return {'recovered_valid_laws':recovered,**self.status()}

    def validate_audit(self,req,result):
        from .validation import no_interpretations
        no_interpretations(result)
        expected={(law,a['cell'],a['actor']):a for law,v in req['inputs']['laws'].items() for a in v['assignments']}
        reviews=result.get('reviews',[])
        actual={(a['law_id'],a['cell'],a['actor']) for a in reviews}
        if actual!=set(expected) or len(reviews)!=len(expected):raise ValueError('Incomplete audit accounting')
        for a in reviews:
            prior=expected[a['law_id'],a['cell'],a['actor']]
            if a.get('verdict') not in ('accept','reject','uncertain') or not a.get('reason'):raise ValueError('Invalid audit judgment')
            if not isinstance(a.get('additional_context'),list):raise ValueError('Missing audited context')
            if not set(a.get('accepted_demo_requirements',[]))<=set(prior['covers'])-{a['law_id']}:raise ValueError('Audit invented demo coverage')

    async def run(self, concurrency=2, limit=0, audit=False):
        table='audits' if audit else 'jobs'
        adapter=CommandAdapter(self.planner.manifest['worker'],900)
        limiter=RateLimiter(10);dispatched=0;stop=False
        with (self.root/'coordinator.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.db.execute("UPDATE "+table+" SET status='pending' WHERE status='running'");self.db.commit()
            async def worker():
                nonlocal dispatched,stop
                while not stop and not (self.root/'drain-request.json').exists() and (not limit or dispatched<limit):
                    row=self.db.execute("SELECT * FROM "+table+" WHERE status='pending' AND attempts<3 ORDER BY key LIMIT 1").fetchone()
                    if not row:return
                    dispatched+=1
                    self.db.execute("UPDATE "+table+" SET status='running',attempts=attempts+1 WHERE key=?",(row['key'],));self.db.commit()
                    req=json.loads(row['request']);req['_worker_evidence_directory']=str(self.root/'worker-evidence'/row['key']/str(row['attempts']+1))
                    if row['error']:req['previous_attempt_error']=row['error']
                    try:
                        await limiter.wait()
                        result,metadata=await adapter.call(req)
                        (self.validate_audit if audit else self.validate)(json.loads(row['request']),result)
                        self.db.execute("UPDATE "+table+" SET status='completed',result=?,metadata=?,error=NULL WHERE key=?",(encode(result),encode(metadata),row['key']))
                    except Exception as exc:
                        self.db.execute("UPDATE "+table+" SET status=?,error=? WHERE key=?",('pending' if isinstance(exc,ValueError) and row['attempts']<2 else 'failed',str(exc),row['key']))
                        if isinstance(exc,AccountUsageLimitError):stop=True
                    self.db.commit();print(encode(self.status()),flush=True)
                    self.export()
            await asyncio.gather(*(worker() for _ in range(concurrency)))
        return self.export()

    def status(self):
        return {'jobs':{r[0]:r[1] for r in self.db.execute('SELECT status,count(*) FROM jobs GROUP BY status')},
            'audits':{r[0]:r[1] for r in self.db.execute('SELECT status,count(*) FROM audits GROUP BY status')},
            'failures':[dict(r) for r in self.db.execute("SELECT key,error FROM jobs WHERE status='failed'")]}

    def export(self):
        candidates=[];plans={}
        audited={}
        for row in self.db.execute("SELECT request,result,key FROM audits WHERE status='completed' ORDER BY rowid"):
            request=json.loads(row['request'])
            self.validate_audit(request,json.loads(row['result']))
            sources={(law,a['cell'],a['actor']):a['source_assignment_hash']
                for law,v in request['inputs']['laws'].items() for a in v['assignments']}
            for a in json.loads(row['result'])['reviews']:
                key=(a['law_id'],a['cell'],a['actor'])
                audited[key]=dict(a,receipt=row['key'],source_assignment_hash=sources[key])
        for row in self.db.execute("SELECT * FROM jobs WHERE status='completed'"):
            req=json.loads(row['request']);result=json.loads(row['result']);self.validate(req,result)
            for v in result['laws']:
                plans[v['law_id']]=v['evidence_plan']
                for a in v['assignments']:
                    a=dict(a)
                    source_hash=sha(a)
                    review=audited.get((v['law_id'],a['cell'],a['actor']))
                    if review and review['source_assignment_hash']!=source_hash:review=None
                    if review and review['verdict']!='accept':continue
                    if review:
                        a['covers']=[v['law_id']]+review['accepted_demo_requirements']
                        a['required_context']=sorted(set(a['required_context']+review['additional_context']))
                    a['audit_status']='accepted' if review else 'pending'
                    a['audit_receipt']=review['receipt'] if review else None
                    a['source_assignment_hash']=source_hash
                    reserved='training' if a['cell'] in self.fixed else 'heldout' if a['cell'] in self.retained else None
                    splits=[reserved] if reserved else ['training','testing','heldout']
                    candidates.append(dict(a,law=v['law_id'],splits=splits,readiness_score=0,
                        receipt=row['key'],evidence_readiness='unverified_proposal'))
        candidates=list({(a['law'],a['cell'],a['actor']):a for a in candidates}.values())
        candidates.sort(key=lambda a:(a['law'],a['cell'],a['actor']))
        reqs={'training':self.splits['train']+sorted(self.demo),'testing':self.splits['train'],'heldout':self.splits['test']}
        missing={s:[k for k in targets if not any(k in a['covers'] and s in a['splits'] for a in candidates)] for s,targets in reqs.items()}
        progress=dict(self.status(),positive_assignments=len(candidates),mapped_laws=len(plans),
            missing=missing,full_selected_coverage=False,exact_minimum_proven=False,
            unevaluated_policy='Unsearched cells/actors/laws are unknown, not negative',
            recorded_coverage='Historical candidates only; no new recording validation',
            executable_coverage='Unverified; see evidence plans and prerequisites')
        partition_path=self.root/'partitions.json'
        if partition_path.exists():
            report=json.loads(partition_path.read_text())
            if report.get('candidate_hash')==sha(candidates):
                progress['full_selected_coverage']=report.get('selected_coverage_complete',False)
                progress['selected_cells']=report.get('total_cells',{})
        atomic(self.root/'candidates.json',candidates);atomic(self.root/'evidence-plans.json',plans)
        atomic(self.root/'progress.json',progress)
        return progress

    def optimize(self):
        self.export()
        c=json.loads((self.root/'candidates.json').read_text())
        requirements={'training':self.splits['train']+sorted(self.demo),'testing':self.splits['train'],'heldout':self.splits['test']}
        r=solve(c,requirements,self.fixed,self.retained,timeout=30)
        r['exact_minimum_proven']=False
        r['candidate_hash']=sha(c)
        r['scope']='approximate selection from reviewed candidate subset; exhaustive discovery not required'
        if r.get('selection') and any(r['selection'].values()):
            r['verification']=verify_solution(r,c,requirements,self.fixed,self.retained)
            r['unaudited_witnesses']=sum(a['audit_status']!='accepted' for a in r['witnesses'])
            r['selected_coverage_complete']=r['verification']['passed'] and r['unaudited_witnesses']==0
            for s,cells in r['selection'].items():atomic(self.root/(s+'-cells.json'),cells)
            atomic(self.root/'training-demo-gap-worklist.json',[dict(w,tag='training_demo_gap',
                historical_branch_evidence='requires_validation') for w in r['witnesses']
                if w['split']=='training' and w['requirement'].startswith('demo:')])
        atomic(self.root/'partitions.json',r)
        if r.get('verification',{}).get('passed'):self.delivery_report(r)
        self.export()
        return r

    def delivery_report(self, report):
        selection={s:set(cells) for s,cells in report['selection'].items()}
        history=json.loads((self.planner.root/'inputs/recording-history.json').read_text())
        eligibility=[]
        for old in history:
            assigned=next((s for s,cells in selection.items() if old['cell'] in cells),None)
            target=old.get('target_law')
            target_split='heldout' if target in self.splits['test'] else 'training' if target in self.splits['train'] else None
            status='historical_only'
            if assigned and target_split==assigned and old.get('status')=='completed':status='potentially_reusable_requires_current_evidence_validation'
            if old.get('split')=='heldout' and old['cell'] in self.fixed:status='excluded_from_heldout_training_owned'
            eligibility.append(dict(old,selected_split=assigned,current_target_split=target_split,current_eligibility=status))
        atomic(self.root/'recording-eligibility.json',eligibility)
        atomic(self.root/'historical-overlap-migration.json',{
            'training_owned_old_heldout_cells':self.ownership['heldout_replacement_required'],
            'selected_heldout_cells':report['selection']['heldout'],
            'history_preserved':True,'recording_evidence_revalidated':False})
        atomic(self.root/'coverage-witnesses.json',report['witnesses'])
        prerequisites=json.loads((self.root/'evidence-plans.json').read_text())
        atomic(self.root/'implementation-prerequisites.json',{
            law:plan['implementation_prerequisites'] for law,plan in prerequisites.items()})
        atomic(self.root/'feasibility-qualified.json',{'status':'blocked',
            'reason':'Active evidence proposals are available, but simulator/extractor/actor-routing/Lean support has not been verified.',
            'unverified_laws':sorted(prerequisites),
            'implementation_prerequisites_file':'implementation-prerequisites.json',
            'currently_executable_coverage':None,'validated_recorded_coverage':None})
        cells=sorted(set().union(*selection.values()))
        atomic(self.root/'selected-actor-reviews.json',{c:self.cell(c) for c in cells})
        receipts=[];audit_reviews=[];patterns=[]
        for table in ('jobs','audits'):
            for row in self.db.execute('SELECT * FROM '+table+" WHERE status='completed'"):
                request=json.loads(row['request']);result=json.loads(row['result'])
                receipts.append({'key':row['key'],'stage':request['stage'],
                    'input_hash':sha(request),'result_hash':sha(result),
                    'metadata':json.loads(row['metadata'] or '{}')})
                if table=='audits':
                    audit_reviews+=result['reviews'];patterns+=result.get('pattern_findings',[])
        atomic(self.root/'processing-receipts.json',receipts)
        atomic(self.root/'recall-audit.json',{'scope':'independent review of selected positive witnesses',
            'negative_recall_scope':'Not applicable to focused search: no negative relevance claims are made for unsearched pairs.',
            'selected_unaudited_witnesses':report.get('unaudited_witnesses'),
            'reviews':audit_reviews,'pattern_findings':patterns})
        regressions={
            'general_duties':[a for a in report['witnesses'] if a.get('relevance_type')=='general_duty'],
            'compatible_unstated_context':[a for a in report['witnesses'] if a['decision']=='conditional'],
            'specialized_drivers':[a for a in report['witnesses'] if a['actor'] in ('bus_driver','taxi_driver','emergency_vehicle_driver','heavy_vehicle_driver')],
            'pedestrian_obligations':[a for a in report['witnesses'] if 'pedestrian' in a['actor']],
            'positive_without_grounding_citation':[a for a in report['witnesses'] if a['law'] not in self.planner.cells[a['cell']].get('source_laws',[])]}
        atomic(self.root/'regression-examples.json',{k:[dict(a,fixed_facts=self.cell(a['cell'])) for a in values[:2]] for k,values in regressions.items()})
        atomic(self.root/'unresolved-legal-scope.json',{
            'NRS-484B-250-3':{
                'issue':'Interaction of statutory through-highway status, the controlled-intersection exclusion and subsection 4 remains unresolved.',
                'selection_scope':'Potential conditional relevance only; no established activation or legal interpretation is claimed.',
                'preserve_in_context':True}})
        lines=['# Approximate law-coverage cell selections','',
            'Status: '+('selected coverage complete with independent semantic review' if report.get('selected_coverage_complete') else 'provisional selection; independent review remains')+'.','',
            '| Split | Cells | Additional cells | Required laws |',
            '| --- | ---: | ---: | ---: |']
        for split in ('training','testing','heldout'):
            lines.append('| %s | %s | %s | %s |'%(split,report['total_cells'][split],report['additional_cells'][split],28 if split=='heldout' else 221))
        lines+=['',
            'Training also covers the 16 demo laws and '+str(len(self.demo))+' separately tracked demo obligations/branches.',
            'All three splits are cell-disjoint. Existing fixed training selections and compatible held-out selections are retained.',
            'The selection is approximate over the reviewed candidate pool. Global minimum and exhaustive irrelevance are not claimed.','',
            'Selected coverage means quoted, actor-specific potential legal relevance with an active evidence proposal. Execution feasibility remains unverified. Simulator, extractor, actor-routing and Lean prerequisites are listed separately. Historical recordings are candidates pending current evidence validation. No CARLA runs or Lean schema changes were performed.','',
            'NRS-484B-250-3 is retained as conditional potential coverage. Its through-highway/control interaction remains an explicit legal applicability question; see unresolved-legal-scope.json.','',
            '- Cell lists: training-cells.json, testing-cells.json, heldout-cells.json',
            '- Law and branch witnesses: coverage-witnesses.json',
            '- Separate training demo supplement: training-demo-gap-worklist.json',
            '- Active setup and comparison/sweep proposals: evidence-plans.json',
            '- Implementation prerequisites: implementation-prerequisites.json',
            '- Feasibility-qualified status: feasibility-qualified.json',
            '- Regression examples and unresolved legal scope: regression-examples.json, unresolved-legal-scope.json',
            '- Recording eligibility and migration: recording-eligibility.json, historical-overlap-migration.json',
            '- Optimizer, coverage verification and bounds: partitions.json',
            '- Independent review and original request/response evidence: focused.sqlite, worker-evidence/',
            '- Frozen authoritative inputs and ownership audit: '+str(self.planner.root),'']
        (self.root/'README.md').write_text('\n'.join(lines))

    async def finish(self, concurrency=6):
        """Repair coverage gaps, solve, and audit only witnesses actually selected."""
        if self.db.execute("SELECT 1 FROM jobs WHERE status='pending' AND attempts<3").fetchone():
            await self.run(concurrency)
        for round_number in range(1,7):
            self.recover()
            repair=self.repair()
            print(encode({'round':round_number,'repair':repair}),flush=True)
            if self.db.execute("SELECT 1 FROM jobs WHERE status='pending' AND attempts<3").fetchone():
                await self.run(concurrency)
                self.recover()
            errors=[r[0] for table in ('jobs','audits') for r in self.db.execute('SELECT error FROM '+table+" WHERE status='failed'")]
            if any('usage limit' in (e or '').lower() for e in errors):break
            report=self.optimize()
            if not report.get('selection') or not report.get('verification',{}).get('passed'):
                if repair['new_batches']==0:break
                continue
            if report.get('selected_coverage_complete'):
                atomic(self.root/'completion.json',{'status':'selected_coverage_complete',
                    'rounds':round_number,'partition_hash':sha(report),
                    'exact_minimum_proven':False,'recording_execution':'outside this phase'})
                return report
            self.prepare_audit()
            if self.db.execute("SELECT 1 FROM audits WHERE status='pending' AND attempts<3").fetchone():
                await self.run(concurrency,audit=True)
            report=self.optimize()
            if report.get('selected_coverage_complete'):
                atomic(self.root/'completion.json',{'status':'selected_coverage_complete',
                    'rounds':round_number,'partition_hash':sha(report),
                    'exact_minimum_proven':False,'recording_execution':'outside this phase'})
                return report
            errors=[r[0] for table in ('jobs','audits') for r in self.db.execute('SELECT error FROM '+table+" WHERE status='failed'")]
            if any('usage limit' in (e or '').lower() for e in errors):break
        atomic(self.root/'completion.json',{'status':'incomplete','progress':self.export()})
        return self.export()

    def verify_delivery(self):
        self.export()
        report=json.loads((self.root/'partitions.json').read_text())
        candidates=json.loads((self.root/'candidates.json').read_text())
        requirements={'training':self.splits['train']+sorted(self.demo),
            'testing':self.splits['train'],'heldout':self.splits['test']}
        audit=verify_solution(report,candidates,requirements,self.fixed,self.retained)
        errors=audit['errors']
        if not set(self.splits['demo'])<=set(self.splits['train']):errors.append('Demo laws are not a subset of training')
        if report.get('candidate_hash')!=sha(candidates):errors.append('Stale candidate universe')
        for split,cells in report.get('selection',{}).items():
            if json.loads((self.root/(split+'-cells.json')).read_text())!=cells:errors.append('Cell list differs: '+split)
            if set(cells)-set(self.planner.cells):errors.append('Unknown catalog cells: '+split)
        for witness in report.get('witnesses',[]):
            law=witness['law'];quote=witness.get('quote')
            if not quote or quote not in self.planner.laws[law]['text']:errors.append('Invalid witness quote: '+law)
            if witness['actor'] not in self.cell(witness['cell'])['available_actors']:errors.append('Unknown witness actor: '+law)
            source=self.db.execute("SELECT request FROM jobs WHERE key=? AND status='completed'",(witness['receipt'],)).fetchone()
            source_cells=[] if not source else json.loads(source['request'])['inputs']['laws'][law]['candidates']
            frozen=[c for c in source_cells if c['cell_id']==witness['cell']]
            if not frozen or frozen[0]!=self.cell(witness['cell']):errors.append('Witness facts or actor-review context changed: '+law)
            row=self.db.execute("SELECT request,result FROM audits WHERE key=? AND status='completed'",(witness.get('audit_receipt'),)).fetchone()
            if not row:
                errors.append('Missing independent audit: '+law);continue
            request=json.loads(row['request']);result=json.loads(row['result']);self.validate_audit(request,result)
            prior=[a for a in request['inputs']['laws'][law]['assignments'] if (a['cell'],a['actor'])==(witness['cell'],witness['actor'])]
            checks=[a for a in result['reviews'] if (a['law_id'],a['cell'],a['actor'])==(law,witness['cell'],witness['actor'])]
            if not prior or prior[0]['source_assignment_hash']!=witness['source_assignment_hash'] or not checks or checks[0]['verdict']!='accept':errors.append('Audit does not support current witness: '+law)
            if witness['requirement'].startswith('demo:') and (not checks or witness['requirement'] not in checks[0]['accepted_demo_requirements']):errors.append('Demo branch lacks independent acceptance')
        current_inputs=[]
        for path,digest in self.planner.manifest['input_hashes'].items():
            if ('/laws/example/' in path and path.endswith('laws.jsonl')) or path.endswith('/inputs/catalog/vocabulary_catalog.json'):
                matches=sha(Path(path).read_bytes())==digest
                current_inputs.append({'path':path,'matches':matches})
                if not matches:errors.append('Current source changed: '+path)
        result=dict(audit,passed=not errors,errors=errors,current_inputs=current_inputs,
            demo_subset_verified=set(self.splits['demo'])<=set(self.splits['train']),
            selected_coverage_kind='actor-specific conditional legal relevance with active evidence proposals',
            recording_execution_verified=False,exact_minimum_claimed=False)
        atomic(self.root/'completion-audit.json',result)
        return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['prepare','run','status','optimize','audit-prepare','audit-context-repair','audit-run','repair','recover','finish','verify'])
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--name',default='focused-coverage-20261016-v1')
    p.add_argument('--concurrency',type=int,default=2);p.add_argument('--limit',type=int,default=0)
    p.add_argument('--wait-pid',type=int)
    p.add_argument('--law',action='append',default=[])
    args=p.parse_args()
    if args.wait_pid:
        proc=Path('/proc')/str(args.wait_pid)/'cmdline'
        while proc.exists():
            try:command=proc.read_bytes()
            except FileNotFoundError:break
            if b'batch_pipeline.law_focused_selection' not in command:break
            time.sleep(5)
    f=Focused(args.source,args.name)
    if args.action=='prepare':f.prepare();v=f.export()
    elif args.action in ('run','audit-run'):v=asyncio.run(f.run(args.concurrency,args.limit,args.action=='audit-run'))
    elif args.action=='audit-prepare':v=f.prepare_audit()
    elif args.action=='audit-context-repair':v=f.prepare_audit(retry_context=True,law_filter=args.law)
    elif args.action=='repair':v=f.repair(args.law)
    elif args.action=='recover':v=f.recover()
    elif args.action=='finish':v=asyncio.run(f.finish(args.concurrency))
    elif args.action=='verify':v=f.verify_delivery()
    elif args.action=='optimize':v=f.optimize()
    else:v=f.export()
    print(encode(v),flush=True)

if __name__=='__main__':main()
