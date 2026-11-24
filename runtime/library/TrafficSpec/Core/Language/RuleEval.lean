/-
  TrafficSpec.Core.Language.RuleEval
  Evaluating a rule over a trace, and checking it before any trace.

  `verdicts` combines the binder classes, the applicability and the obligation per instant
  (Kleene, `verdictAt`). `check` finds from the syntax every defect the evaluator would otherwise
  report as `malformed` or `unboundVariable`; its doc comment lists them. `checkReading`
  names the parameters and aggregates the reading lacks, over the rule and the rules it composes,
  with their concept calls expanded; `Concept.checkReading` the aggregates a concept's body names.

  `RuleSet` evaluates `requiredBy` and `lawful` against the library: which rules each ranges over
  (the strata that keep them free of cycles), and the formula over those rules it stands for; and
  which rules, and so which approved abstractions, a rule's verdict reads.

  `Concept.check` holds a concept to the same standard on every admissible instantiation of
  its formals, with its calls expanded. `Concept.callDefects` holds every concept call to the
  callee's signature before expansion loses it.

  Nothing under Rules/ or Concepts/ imports this file; Grounding, Manifest and Monitor do.
-/
import TrafficSpec.Core.Language.Rule
import TrafficSpec.Core.Language.Concept
import TrafficSpec.Core.Language.Semantics
import TrafficSpec.Core.Language.EvalFast

namespace TrafficSpec

namespace RuleSet

/-- Whether a rule reads a rule-set leaf satisfying `p`, in its own formulas or through a rule it
    composes. -/
def reads (rules : List Rule) (r : Rule) (p : Formula → Bool) : Bool :=
  (Rule.closure rules r).any fun x => x.formulas.any fun φ => (Formula.ruleSets φ).any p

/-- Whether a rule uses a rule-set operator at all. -/
def usesSets (rules : List Rule) (r : Rule) : Bool := reads rules r fun _ => true

/-- Whether a rule uses a `lawful`. -/
def usesLawful (rules : List Rule) (r : Rule) : Bool := reads rules r fun | .lawful .. => true | _ => false

/-- Whether a case requires conduct `k`. -/
def requires (k : Conduct) (c : RuleCase) : Bool := match c.kind with
  | .requires k' => k' == k
  | .permits => false

/-- The rules a `requiredBy k` ranges over: the rules of `lib` that declare a case requiring `k`,
    are no surrogate and no permission, and use no rule-set operator. A rule that uses one is never
    among them, so no rule is in its own set and no set reaches back to a rule that reads it. -/
def caseMembers (lib : List Rule) (k : Conduct) : List Rule :=
  lib.filter fun r => !r.surrogate && !r.permission && !r.id.startsWith "#" && r.cases.any (requires k) && !usesSets lib r

/-- Whether a rule is in a scope: every rule; one whose subject binder's class names the aggregate;
    one that declares the purpose; or both. -/
def inScope (r : Rule) : RuleScope → Bool
  | .every => true
  | .subjectClass a | .asClass a => match r.binders.head? with
    | some b => (Formula.aggregateIds b.cls).contains a
    | none => false
  | .purpose p => r.purposes.contains p
  | .asClassPurpose a p => r.purposes.contains p && match r.binders.head? with
    | some b => (Formula.aggregateIds b.cls).contains a
    | none => false

/-- The rules of `lib` in a scope that a `lawful` reads: no surrogate, no permission, no reserved
    id. Those that use no `lawful` are its members; the others are left out by the strata. -/
def inLawfulScope (lib : List Rule) (s : RuleScope) : List Rule :=
  lib.filter fun r => !r.surrogate && !r.permission && !r.id.startsWith "#" && inScope r s

/-- The rules a `lawful s` ranges over: those of its scope that use no `lawful`; they may use
    `requiredBy`, whose rules use no operator, so the sets stand in three strata and none reaches
    back to a rule that reads it. -/
def lawfulMembers (lib : List Rule) (s : RuleScope) : List Rule :=
  (inLawfulScope lib s).filter fun r => !usesLawful lib r

/-- The rules a rule-set leaf ranges over in `lib`; none for any other formula. -/
def membersOf (lib : List Rule) : Formula → List Rule
  | .requiredBy k _ => caseMembers lib k
  | .lawful s _ => lawfulMembers lib s
  | _ => []

/-- Every rule whose verdicts a rule's verdict reads, the rule first: the rules it composes and the
    members of every rule-set operator it reads, transitively, each once. -/
def dependencies (lib : List Rule) (r : Rule) : List Rule :=
  let rec go (fuel : Nat) (seen : List String) (todo : List Rule) : List Rule :=
    match fuel, todo with
    | 0, _ | _, [] => []
    | fuel + 1, x :: rest =>
      let found := (x.composes.filterMap fun id => lib.find? (·.id == id)) ++
        (x.formulas.flatMap Formula.ruleSets).flatMap (membersOf lib)
      let next := found.foldl (fun acc y => if seen.contains y.id || acc.any (·.id == y.id) then acc else acc ++ [y]) []
      x :: go fuel (seen ++ next.map (·.id)) (rest ++ next)
  go (lib.length + 1) [r.id] [r]

/-- The approved abstractions a rule's verdict rests on: its own and those of every rule it reads,
    each once. A verdict with any is partial coverage. -/
def abstractionsOf (lib : List Rule) (r : Rule) : List String :=
  ((dependencies lib r).flatMap (·.abstractions)).eraseDups

/-- Whether a rule's verdict rests on a duration read from the trace's samples: the rule or a rule
    it reads (a composition, a case, a member of a rule-set operator it reads) has a formula that
    reads `durationWithin`. Such a verdict is marked `sampled_duration`: it judges the time the
    samples show, not a time proved between them. Read on rules with their concept calls expanded,
    so that a concept body is seen. -/
def sampledDurationOf (lib : List Rule) (r : Rule) : Bool :=
  (dependencies lib r).any fun x => x.formulas.any Formula.readsDuration

/-- The rule standing for case `c` of `r`: its binders, its applicability and the case's
    situation for applicability, and no duty. A case never holds where its rule does not apply. -/
def caseRule (r : Rule) (c : RuleCase) : Rule :=
  { r with id := caseId r.id c.name, applicability := .and r.applicability c.when, obligation := .tt, cases := [] }

/-- `r` with its subject binder's class not required: its duty binds a road user of any class. -/
def asClassRule (r : Rule) : Rule :=
  { r with id := s!"#as:{r.id}", binders := match r.binders with | b :: bs => { b with cls := .tt } :: bs | [] => [] }

/-- `body` with a road user bound to each of the binders `bs`: some (`ex`) or every road user of
    the scene other than `who` and those bound before it; `body` receives the binder map. -/
def others (ex : Bool) (bs : List String) (body : List (String × String) → Formula) : Formula :=
  go 1 [] bs
where
  go (k : Nat) (done : List (String × String)) : List String → Formula
    | [] => body done
    | b :: rest =>
      let v := s!"#o{k}"
      let distinct : Formula := ("who" :: done.map (·.2)).foldr (fun u acc => .and (.not (.same (.var v) (.var u))) acc) .tt
      let inner := go (k + 1) (done ++ [(b, v)]) rest
      if ex then .existsUser v (.and distinct inner) else .forallUser v (.implies distinct inner)

private def anyOf : List Formula → Formula
  | [] => .ff
  | [φ] => φ
  | φ :: rest => .or φ (anyOf rest)
private def allOf : List Formula → Formula
  | [] => .tt
  | [φ] => φ
  | φ :: rest => .and φ (allOf rest)

/-- A leaf that is unknown everywhere, for the reason given: what a set reads where it cannot know. -/
def unknownLeaf (why : String) : Formula := .rule s!"#unknown:{why}" []

/-- What a rule-set composition id stands for over `lib`, with `who` the one variable it reads:
    the formula over the rules it ranges over, and the rules that formula composes beside `lib`;
    or why it decides nothing (an empty set, an id no operator has). A rule of a `lawful` scope
    left out by the strata is read through its subject class: where `who` meets it, the result is
    unknown, since that rule's verdict is not known. -/
def expansion (lib : List Rule) (id : String) : Except String (Formula × List Rule) :=
  match RuleSet.ofId id with
  | some (.requiredBy k _) =>
    let cs := (caseMembers lib k).flatMap fun r => (r.cases.filter (requires k)).map (caseRule r)
    if cs.isEmpty then .error s!"{id}: no rule of the library declares a case requiring {k}" else
    .ok (anyOf (cs.map fun p => match p.binders with
      | b :: bs => others true (bs.map (·.name)) fun m => .ruleApplies p.id ((b.name, "who") :: m)
      | [] => .ff), cs)
  | some (.lawful s _) =>
    let ms := lawfulMembers lib s
    let left := (inLawfulScope lib s).filter (usesLawful lib ·)
    if ms.isEmpty && left.isEmpty then .error s!"{id}: the scope holds no rule of the library" else
    let asCls := match s with | .asClass _ | .asClassPurpose _ _ => true | _ => false
    let ts := if asCls then ms.map asClassRule else ms
    let leftOut := left.map fun r =>
      match r.binders.head? with
      | some b => if asCls then unknownLeaf s!"{r.id} is in the scope but uses `lawful` itself"
                  else .implies (Concept.substF { vars := [(b.name, .var "who")], params := [], tag := "scope" } b.cls) (unknownLeaf s!"{r.id} is in the scope but uses `lawful` itself")
      | none => .tt
    .ok (allOf (ts.map (fun p => match p.binders with
      | b :: bs => others false (bs.map (·.name)) fun m => .rule p.id ((b.name, "who") :: m)
      | [] => .tt) ++ leftOut), if asCls then ts else [])
  | _ => .error s!"{id}: no rule-set operator"

/-- Every rule a monitor must register to evaluate `targets`: each with the rules it composes, and,
    where any of them reads a rule-set operator, the whole library, which the operators range over. -/
def registered (all targets : List Rule) : List Rule :=
  let closed := (targets.flatMap (Rule.closure all)).foldl (fun acc r => if acc.any (·.id == r.id) then acc else acc ++ [r]) []
  if closed.any (fun r => r.formulas.any fun φ => !(Formula.ruleSets φ).isEmpty) then
    closed ++ all.filter fun r => !closed.any (·.id == r.id)
  else closed

end RuleSet

namespace Rule
open Semantics

/-- A rule's formula as evaluated: every comparison over a `cond` decided by cases, through the
    sub-expression cache (`evalFastAll`, whose every stored value is the one `evalAll` gives). -/
def evalRuleFormula (c : SemCtx) (φ : Formula) : Array R := evalFastAll c (Formula.elimCond φ)

/-- Every binder's class holds for its bound track and the applicability holds, per instant. -/
def engagedAll (r : Rule) (c : SemCtx) : Array R :=
  Temporal.allOf c.n (r.binders.map (fun b => evalRuleFormula c b.cls) ++ [evalRuleFormula c r.applicability])

/-- The verdict at every instant. -/
def verdicts (r : Rule) (c : SemCtx) : Array Verdict :=
  Array.zipWith verdictAt (r.engagedAll c) (evalRuleFormula c r.obligation)

/-- The rule as a three-valued statement per instant: complied with (true), violated (false), or
    unknown. Not engaged counts as complied with — a rule that does not apply is not broken. -/
def asRAll (r : Rule) (c : SemCtx) : Array R :=
  (r.verdicts c).map fun v => match v with
    | .compliant | .notApplicable => R.t
    | .violated => R.f
    | .unknown w => ⟨.u, w⟩

/-- Structural well-formedness apart from having a binder: binders named and distinct, the id
    set, every assumption, intention and fact used declared, every intention and fact id
    well-formed, every operationalization bounding its standard by atoms, primitives or concepts. -/
def wellFormedBody (r : Rule) : Bool :=
  r.binderNames.eraseDups.length == r.binders.length &&
  r.binders.all (fun b => !b.name.isEmpty) &&
  !r.id.isEmpty &&
  r.usedAssumptions.all (r.assumptions.contains ·) &&
  r.usedIntentions.all (r.intentions.contains ·) &&
  r.intentions.all IntId.wellFormed &&
  r.usedFacts.all (r.facts.contains ·) &&
  r.facts.all FactId.wellFormed &&
  r.operationalizations.all (fun o => !o.concepts.isEmpty && o.concepts.all fun c =>
    c.startsWith "drv." || Primitives.primitiveNames.contains (defName c) || knowsAtom (defName c))

/-- Structural well-formedness: at least one binder, and `wellFormedBody`. -/
def wellFormed (r : Rule) : Bool := !r.binders.isEmpty && r.wellFormedBody

-- ---------------------------------------------------------------------------------------------
-- Static check
-- ---------------------------------------------------------------------------------------------
/-- Variables in scope with their sorts, the innermost first. -/
abbrev Scope := List (String × EntityKind)

/-- Whether `v` is bound and its innermost binding has sort `k`, as evaluation's lookup reads it. -/
def Scope.binds (scope : Scope) (v : String) (k : EntityKind) : Bool :=
  (scope.find? (·.1 == v)).map (·.2) == some k

/-- Resolve arguments against the scope with dummy ids, checking each variable's sort against the
    position's expected sort when the table knows it. An entity position takes a variable only:
    a literal or a number there would name a track, region or device the rule has no right to. -/
private def dummyArgs (scope : Scope) (sorts : Option (List (Option EntityKind))) (args : List Arg)
    : Except String (List Primitives.DArg) :=
  (args.zip (List.range args.length)).mapM fun (a, k) =>
    match a with
    | .var v =>
      match scope.find? (·.1 == v) with
      | none => .error s!"variable `{v}` is not bound"
      | some (_, vs) =>
        match sorts.bind (·[k]?) with
        | some (some want) => if want == vs then .ok (.v 0) else .error s!"variable `{v}` has sort {repr vs}, position {k} wants {repr want}"
        | some none => .error s!"variable `{v}` where position {k} takes a literal"
        | none => .ok (.v 0)
    | .lit l =>
      match sorts.bind (·[k]?) with
      | some (some want) => .error s!"literal `{l}` where position {k} wants a {repr want}"
      | _ => .ok (.s l)
    | .nat n =>
      match sorts.bind (·[k]?) with
      | some (some want) => .error s!"number `{n}` where position {k} wants a {repr want}"
      | _ => .ok (.n n)

private def isMalformed : UnknownReason → Option String
  | .malformed w => some w
  | .parameterMissing w => some w
  | _ => none

private def emptyScene : Scene := { t := 0 }
private def emptyCtx : Primitives.Ctx := { scenes := #[], times := #[], ρ := {} }

/-- A quantifier's kind: a spelling the codec decodes. A variable is a concept's literal formal
    that reached the check unfilled. -/
private def kindErrors (where_ : String) (a : Arg) (what : String) (known : String → Bool) : List String :=
  match a with
  | .lit s => if known s then [] else [s!"{where_}: {what} kind `{s}` names no kind"]
  | .var v => [s!"{where_}: {what} kind `{v}` is a variable; spell the kind, or fill it from a literal formal"]
  | .nat _ => [s!"{where_}: {what} kind is a number"]

private def constParamErrors (where_ name : String) (ps : List Term) : List String :=
  ps.filter (!Term.isConstant ·) |>.map fun _ => s!"{where_}: `{name}` parameter is not a constant term"

/-- The step bound of `op`: a literal or a reading parameter, a literal strictly positive. -/
private def stepErrors (where_ op : String) : Term → List String
  | .lit q _ => if Q.lt Q.zero q then [] else [s!"{where_}: {op} step bound is not strictly positive"]
  | .param _ => []
  | _ => [s!"{where_}: {op} step bound is not a literal or a reading parameter"]

mutual
  partial def checkTerm (scope : Scope) (where_ : String) : Term → List String
    | .lit _ _ | .param _ => []
    | .measure a args =>
      match dummyArgs scope (atomArgSorts a) args with
      | .error e => [s!"{where_}: {e}"]
      | .ok ds => match evalMeasure emptyScene a ds with
        | .error w => match isMalformed w with | some m => [s!"{where_}: measure `{a}`: {m}"] | none => []
        | .ok _ => []
    | .quantity concept args ps =>
      let inner := ps.flatMap (checkTerm scope where_) ++ constParamErrors where_ concept ps
      match dummyArgs scope (Primitives.argSorts concept) args with
      | .error e => [s!"{where_}: {e}"] ++ inner
      | .ok ds => match Primitives.evalQ concept emptyCtx ds (ps.map fun _ => Q.zero) with
        | .error w => (match isMalformed w with | some m => [s!"{where_}: `{concept}`: {m}"] | none => []) ++ inner
        | .ok _ => inner
    | .distanceWhile subj φ =>
      (if scope.binds subj .track then [] else [s!"{where_}: subject `{subj}` is not a bound track"]) ++
      checkFormula scope where_ φ
    | .sinceRise φ => checkFormula scope where_ φ
    | .headingSince subj g ψ =>
      (if scope.binds subj .track then [] else [s!"{where_}: subject `{subj}` is not a bound track"]) ++
      stepErrors where_ "heading_since" g ++ checkTerm scope where_ g ++ checkFormula scope where_ ψ
    | .aggregate _ v φ t => checkFormula ((v, .track) :: scope) where_ φ ++ checkTerm ((v, .track) :: scope) where_ t
    | .add a b | .sub a b | .mul a b | .div a b => checkTerm scope where_ a ++ checkTerm scope where_ b
    | .neg a | .abs a => checkTerm scope where_ a
    | .cond φ a b => checkFormula scope where_ φ ++ checkTerm scope where_ a ++ checkTerm scope where_ b

  partial def checkFormula (scope : Scope) (where_ : String) : Formula → List String
    | .tt | .ff | .asm _ => []
    | .intent _ who target =>
      [(who, EntityKind.track, "road user"), (target, EntityKind.region, "region")].flatMap fun (a, want, what) =>
        match a with
        | .var v => if scope.binds v want then [] else [s!"{where_}: intent's {what} `{v}` is not a bound {repr want}"]
        | _ => [s!"{where_}: intent's {what} is a variable"]
    | .fact id xs =>
      let regions := xs.filter fun a => match a with | .var v => scope.binds v .region | _ => false
      (if xs.length == 1 || xs.length == 2 then [] else [s!"{where_}: fact `{id}` names one or two subjects, not {xs.length}"]) ++
      (if regions.length ≤ 1 then [] else [s!"{where_}: fact `{id}` names more than one region"]) ++
      (match xs with
       | [.var a, .var b] => if a == b then [s!"{where_}: fact `{id}` names `{a}` twice; its subjects are distinct"] else []
       | _ => []) ++
      xs.flatMap fun a => match a with
        | .var v => if scope.binds v .track || scope.binds v .region then []
                    else [s!"{where_}: fact `{id}`'s subject `{v}` is not a bound track or region"]
        | _ => [s!"{where_}: fact `{id}`'s subject is a variable"]
    | .same a b => [a, b].flatMap fun arg => match arg with
      | .var v => if scope.any (·.1 == v) then [] else [s!"{where_}: variable `{v}` is not bound"]
      | _ => [s!"{where_}: `same` compares two bound variables"]
    | .atom name args ps =>
      let inner := ps.flatMap (checkTerm scope where_) ++ constParamErrors where_ name ps
      match dummyArgs scope (atomArgSorts name) args with
      | .error e => [s!"{where_}: {e}"] ++ inner
      | .ok ds =>
        if name == "ru_aggregate" then inner     -- membership is the reading's; `checkReading` holds the word
        else match evalAtomE emptyScene name ds (ps.map fun _ => Q.zero) with
        | .error w => (match isMalformed w with | some m => [s!"{where_}: atom `{name}`: {m}"] | none => []) ++ inner
        | .ok _ => inner
    | .cmp l _ r => checkTerm scope where_ l ++ checkTerm scope where_ r
    | .not φ | .always φ | .eventually φ => checkFormula scope where_ φ
    | .and φ ψ | .or φ ψ | .implies φ ψ | .until φ ψ | .since φ ψ => checkFormula scope where_ φ ++ checkFormula scope where_ ψ
    | .holdsFor m d subj φ | .within m d subj φ =>
      windowErrors scope where_ m d subj ++ checkTerm scope where_ d ++ checkFormula scope where_ φ
    | .untilWithin m d subj φ ψ =>
      windowErrors scope where_ m d subj ++ checkTerm scope where_ d ++ checkFormula scope where_ φ ++ checkFormula scope where_ ψ
    | .atLast m d subj ψ φ =>
      windowErrors scope where_ m d subj ++ checkTerm scope where_ d ++ checkFormula scope where_ ψ ++ checkFormula scope where_ φ
    | .count e sφ _ _ => checkFormula scope where_ e ++ checkFormula scope where_ sφ
    | .durationWithin w g φ op b =>
      (if op == .gt then [] else [s!"{where_}: duration_within compares by `gt` only (more than its bound)"]) ++
      windowErrors scope where_ .time w "" ++ stepErrors where_ "duration_within" g ++
      (if Term.isConstant b then [] else [s!"{where_}: duration_within bound is not a constant term"]) ++
      checkTerm scope where_ w ++ checkTerm scope where_ g ++ checkTerm scope where_ b ++ checkFormula scope where_ φ
    | .rises φ => checkFormula scope where_ φ
    | .definedWhen p φ => checkFormula scope where_ p ++ checkFormula scope where_ φ
    | .derived concept args ps =>
      let inner := ps.flatMap (checkTerm scope where_) ++ constParamErrors where_ concept ps
      match dummyArgs scope (Primitives.argSorts concept) args with
      | .error e => [s!"{where_}: {e}"] ++ inner
      | .ok ds => match Primitives.evalB concept emptyCtx ds (ps.map fun _ => Q.zero) with
        | .error w => (match isMalformed w with | some m => [s!"{where_}: `{concept}`: {m}"] | none => []) ++ inner
        | .ok _ => inner
    | .rule _ map | .ruleApplies _ map | .ruleCase _ _ map => map.flatMap fun (_, outer) =>
        if scope.binds outer .track then [] else [s!"{where_}: composition maps to `{outer}`, not a bound track"]
    | .requiredBy _ who | .lawful _ who =>
        if scope.binds who .track then [] else [s!"{where_}: a rule-set operator's road user `{who}` is not a bound track"]
    | .existsRegion k v φ | .forallRegion k v φ =>
      kindErrors where_ k "region" (fun s => (StructureKind.ofString s).isSome) ++ checkFormula ((v, .region) :: scope) where_ φ
    | .existsDevice k v φ | .forallDevice k v φ =>
      kindErrors where_ k "device" (fun s => (DeviceKind.ofString s).isSome) ++ checkFormula ((v, .device) :: scope) where_ φ
    | .existsUser v φ | .forallUser v φ => checkFormula ((v, .track) :: scope) where_ φ

  partial def windowErrors (scope : Scope) (where_ : String) (m : Measure) (d : Term) (subj : String) : List String :=
    (if m = .path && !scope.binds subj .track then [s!"{where_}: window subject `{subj}` is not a bound track"] else []) ++
    (if Term.isConstant d then [] else [s!"{where_}: window length is not a constant term"])
end

-- A declared intention read ahead of the judged observation: an `intent` leaf, or a composed
-- rule that reads one, within the scope of a future operator, in a formula or a term.
mutual
  partial def futureTerm (reads : String → Bool) (fut : Bool) : Term → List String
    | .quantity _ _ ps => ps.flatMap (futureTerm reads fut)
    | .distanceWhile _ φ | .sinceRise φ => futureReads reads fut φ
    | .headingSince _ g ψ => futureTerm reads fut g ++ futureReads reads fut ψ
    | .aggregate _ _ φ t => futureReads reads fut φ ++ futureTerm reads fut t
    | .add a b | .sub a b | .mul a b | .div a b => futureTerm reads fut a ++ futureTerm reads fut b
    | .neg a | .abs a => futureTerm reads fut a
    | .cond φ a b => futureReads reads fut φ ++ futureTerm reads fut a ++ futureTerm reads fut b
    | _ => []
  partial def futureReads (reads : String → Bool) (fut : Bool) : Formula → List String
    | .intent id _ _ => if fut then [s!"declared intention `{id}` is read ahead of the judged observation"] else []
    | .rule id _ | .ruleApplies id _ | .ruleCase id _ _ =>
      if fut && reads id then [s!"`{id}` reads a declared intention and is read ahead of the judged observation"] else []
    | .requiredBy .. | .lawful .. =>
      if fut && reads "#" then ["a rule-set operator, over a library a rule of which reads a declared intention, is read ahead of the judged observation"] else []
    | .atom _ _ ps | .derived _ _ ps => ps.flatMap (futureTerm reads fut)
    | .cmp l _ r => futureTerm reads fut l ++ futureTerm reads fut r
    | .always φ | .eventually φ => futureReads reads true φ
    | .until φ ψ => futureReads reads true φ ++ futureReads reads true ψ
    | .within _ d _ φ => futureTerm reads fut d ++ futureReads reads true φ
    | .untilWithin _ d _ φ ψ => futureTerm reads fut d ++ futureReads reads true φ ++ futureReads reads true ψ
    | .not φ | .rises φ => futureReads reads fut φ
    | .and φ ψ | .or φ ψ | .implies φ ψ | .since φ ψ | .definedWhen φ ψ => futureReads reads fut φ ++ futureReads reads fut ψ
    | .holdsFor _ d _ φ => futureTerm reads fut d ++ futureReads reads fut φ
    | .atLast _ d _ ψ φ => futureTerm reads fut d ++ futureReads reads fut ψ ++ futureReads reads fut φ
    | .count e sφ _ _ => futureReads reads fut e ++ futureReads reads fut sφ
    | .durationWithin w g φ _ b => futureTerm reads fut w ++ futureTerm reads fut g ++ futureReads reads fut φ ++ futureTerm reads fut b
    | .existsRegion _ _ φ | .forallRegion _ _ φ | .existsDevice _ _ φ | .forallDevice _ _ φ
    | .existsUser _ φ | .forallUser _ φ => futureReads reads fut φ
    | _ => []
end

-- The distance travelled since the trace began (`kin_path_length`), whose zero is the start of the
-- recording, read where it can decide a search into the past: inside an operand of `since`, of
-- `atLast`, of `count` or of `durationWithin`, inside the formula of `sinceRise`, the onset of
-- `headingSince` or the formula of `rises`, directly or through a composed rule that reads it. Everywhere else it is
-- ordinary arithmetic; path windows and `distanceWhile` measure differences and are never this.
mutual
  partial def pathTerm (reads : String → Bool) (back : Bool) : Term → List String
    | .measure "kin_path_length" _ =>
      if back then ["the distance travelled since the trace began (`kin_path_length`) is read inside a search into the past (`since`, `sinceRise`, `atLast`, `count` or `rises`); the start of a recording is no event of a road user's history"] else []
    | .quantity _ _ ps => ps.flatMap (pathTerm reads back)
    | .distanceWhile _ φ => pathReads reads back φ
    | .sinceRise φ => pathReads reads true φ
    | .headingSince _ g ψ => pathTerm reads back g ++ pathReads reads true ψ
    | .aggregate _ _ φ t => pathReads reads back φ ++ pathTerm reads back t
    | .add a b | .sub a b | .mul a b | .div a b => pathTerm reads back a ++ pathTerm reads back b
    | .neg a | .abs a => pathTerm reads back a
    | .cond φ a b => pathReads reads back φ ++ pathTerm reads back a ++ pathTerm reads back b
    | _ => []
  partial def pathReads (reads : String → Bool) (back : Bool) : Formula → List String
    | .rule id _ | .ruleApplies id _ | .ruleCase id _ _ =>
      if back && reads id then [s!"`{id}` reads the distance travelled since the trace began and is composed inside a search into the past"] else []
    | .requiredBy .. | .lawful .. =>
      if back && reads "#" then ["a rule-set operator, over a library a rule of which reads the distance travelled since the trace began, is read inside a search into the past"] else []
    | .atom _ _ ps | .derived _ _ ps => ps.flatMap (pathTerm reads back)
    | .cmp l _ r => pathTerm reads back l ++ pathTerm reads back r
    | .since φ ψ => pathReads reads true φ ++ pathReads reads true ψ
    | .atLast _ d _ ψ φ => pathTerm reads back d ++ pathReads reads true ψ ++ pathReads reads true φ
    | .count e sφ _ _ => pathReads reads true e ++ pathReads reads true sφ
    | .durationWithin w g φ _ b => pathTerm reads back w ++ pathTerm reads back g ++ pathReads reads true φ ++ pathTerm reads back b
    | .rises φ => pathReads reads true φ
    | .not φ | .always φ | .eventually φ => pathReads reads back φ
    | .and φ ψ | .or φ ψ | .implies φ ψ | .until φ ψ | .definedWhen φ ψ => pathReads reads back φ ++ pathReads reads back ψ
    | .holdsFor _ d _ φ | .within _ d _ φ => pathTerm reads back d ++ pathReads reads back φ
    | .untilWithin _ d _ φ ψ => pathTerm reads back d ++ pathReads reads back φ ++ pathReads reads back ψ
    | .existsRegion _ _ φ | .forallRegion _ _ φ | .existsDevice _ _ φ | .forallDevice _ _ φ
    | .existsUser _ φ | .forallUser _ φ => pathReads reads back φ
    | _ => []
end

/-- Whether a rule, or a rule it composes, reads `kin_path_length` anywhere. -/
def readsPath (rules : List Rule) (r : Rule) : Bool :=
  (closure rules r).any fun x => x.formulas.any fun φ => !(pathReads (fun _ => false) true φ).isEmpty

/-- Every defect a rule has before any trace; empty for a rule the evaluator will never report
    `malformed` or `unboundVariable` on: an empty id; no binder, or one unnamed or named twice;
    an assumption, intention or fact read but not declared, or an intention or fact id ill-formed; a
    fact whose subjects are not one or two distinct bound road users or regions, at most one a region; an
    operationalization bounded by nothing, or by a name that is no atom, primitive or concept; a
    name no table knows; an atom, measure, primitive or concept given the wrong number of
    arguments; an unbound variable, or one of the wrong sort where a track, region or device is
    read (such a position takes a variable, never a spelling or a number; a literal position
    takes no variable); a spelling no enumeration decodes; a quantifier kind that is not a
    spelling; a parameter of an atom or a call, or a window's length, that is not a constant
    term (a literal, a reading parameter, or arithmetic over them); a heading change's or a sampled
    duration's step bound that is not a literal or a reading parameter, or a literal one not
    strictly positive; a sampled duration compared by anything but `gt`, or whose bound is not a
    constant term; a
    declared intention read ahead of the judged observation; the distance travelled since the trace began read inside a
    search into the past; a composed rule not in the set, or a map that names a variable not
    bound to a track, misses one of its binders or names one it does not have; an id beginning with
    `#`; a rule-set operator whose road user is not a bound track; a case that reads a rule-set
    operator or a case, is unnamed, ill-named or named twice; a case requiring a conduct declared
    by a rule that uses a rule-set operator (it would be in no set); a permission whose obligation
    is not `tt`, that permits nothing or requires something; a class that reads a rule-set operator
    or a case; a case read of a rule that declares no such case; a purpose declared twice.
    `regions` names
    variables the caller binds to regions: the region formals of a concept's instance, which
    alone may then have no binder. -/
def check (rules : List Rule) (r : Rule) (regions : List String := []) : List String :=
  let scope : Scope := r.binderNames.map (fun n => (n, EntityKind.track)) ++ regions.map fun n => (n, EntityKind.region)
  let formed := if regions.isEmpty then r.wellFormed else r.wellFormedBody
  let reads (id : String) : Bool :=
    if id == "#" then rules.any (·.readsIntention rules) else
    match rules.find? (·.id == id) with
    | some r' => r'.readsIntention rules
    | none => false
  let readsP (id : String) : Bool :=
    if id == "#" then rules.any (readsPath rules) else (rules.find? (·.id == id)).any (readsPath rules)
  (if formed then [] else [s!"{r.id}: binders empty, duplicated or unnamed, an assumption, intention, fact or concept undeclared, or an intention or fact id ill-formed"]) ++
  (r.binders.flatMap fun b => checkFormula [(b.name, .track)] s!"{r.id} binder `{b.name}`" b.cls) ++
  checkFormula scope s!"{r.id} applicability" r.applicability ++
  checkFormula scope s!"{r.id} obligation" r.obligation ++
  (r.formulas.flatMap (futureReads reads false) |>.eraseDups.map fun e => s!"{r.id}: {e}") ++
  (r.formulas.flatMap (pathReads readsP false) |>.eraseDups.map fun e => s!"{r.id}: {e}") ++
  (if r.id.startsWith "#" then [s!"{r.id}: an id beginning with `#` is reserved for the rule-set operators"] else []) ++
  (r.cases.zipIdx.flatMap fun (c, k) =>
    checkFormula scope s!"{r.id} case {k}" c.shown ++ checkFormula scope s!"{r.id} case {k}" c.when ++
    (if (Formula.refLeaves c.shown ++ Formula.refLeaves c.when).isEmpty then [] else [s!"{r.id} case `{c.name}`: a case reads no rule-set operator and no case"]) ++
    (if c.name.isEmpty || !c.name.all (fun ch => ch.isLower || ch.isDigit || ch == '_') then [s!"{r.id} case {k}: a case name is lower-case letters, digits and `_`"] else [])) ++
  (if (r.cases.map (·.name)).eraseDups.length != r.cases.length then [s!"{r.id}: two cases share a name"] else []) ++
  (if r.cases.any (fun c => match c.kind with | .requires _ => true | _ => false) && RuleSet.usesSets rules r then
    [s!"{r.id}: declares a case requiring a conduct but uses a rule-set operator, itself or through a rule it composes, so it is in no set and the case is never read"] else []) ++
  (if r.permission then
    (match r.obligation with | .tt => [] | _ => [s!"{r.id}: a permission's obligation is `tt`"]) ++
    (if r.cases.any (fun c => c.kind == .permits) then [] else [s!"{r.id}: a permission declares the case it permits"]) ++
    (if r.cases.any (fun c => c.kind != .permits) then [s!"{r.id}: a permission requires nothing"] else [])
   else []) ++
  (r.binders.filter (fun b => !(Formula.refLeaves b.cls).isEmpty) |>.map fun b => s!"{r.id} binder `{b.name}`: a class reads no rule-set operator and no case") ++
  (if r.purposes.eraseDups.length != r.purposes.length then [s!"{r.id}: a purpose declared twice"] else []) ++
  (r.formulas.flatMap Formula.caseRefs |>.eraseDups |>.filterMap fun (id, n) =>
    match rules.find? (·.id == id) with
    | some r' => if r'.cases.any (·.name == n) then none else some s!"{r.id}: reads case `{n}` of `{id}`, which declares no such case"
    | none => none) ++
  (r.formulas.flatMap Formula.compositions).flatMap (fun (id, map) =>
    match rules.find? (·.id == id) with
    | none => [s!"{r.id}: composes unknown rule `{id}`"]
    | some r' =>
      (map.filter (fun (inner, _) => !r'.binderNames.contains inner) |>.map fun (inner, _) => s!"{r.id}: composition of `{id}` maps `{inner}`, not one of its binders") ++
      (r'.binderNames.filter (fun b => !map.any (·.1 == b)) |>.map fun b => s!"{r.id}: composition of `{id}` leaves its binder `{b}` unmapped"))

/-- The aggregate ids `who` names that the reading does not declare, or whose declaration lists
    an id that is no road-user class. -/
def aggregateDefects (who : String) (ids : List String) (ρ : Reading) : List String :=
  ids.eraseDups.flatMap fun w =>
    match ρ.aggregate w with
    | none => [s!"{who}: aggregate `{w}` is not declared by the reading"]
    | some a => (a.included ++ a.unresolved).filter (fun id => !id.startsWith "ru." || (RoadUserClass.ofString (id.drop 3).toString).isNone)
        |>.map fun id => s!"{who}: aggregate `{w}` lists `{id}`, which is not a road-user class"

/-- Parameters and aggregates that the rule, or a rule it composes, names and the reading lacks,
    each rule read with its calls of the concepts `cs` expanded. -/
def checkReading (rules : List Rule) (r : Rule) (ρ : Reading) (cs : List Concept := []) : List String :=
  (Rule.closure rules r).flatMap fun x =>
    let xx := Concept.expandRule cs x
    (xx.params.filter (!ρ.has ·) |>.map fun p => s!"{x.id}: parameter `{p}` is not in the reading")
    ++ aggregateDefects x.id (xx.formulas.flatMap Formula.aggregateIds) ρ

end Rule

/-- Rule composition over a library, with fuel bounding the nesting depth. The composed rule's
    binders are bound through `map` (inner binder ↦ caller variable); an unmapped binder is an
    unbound variable, an unknown id is `compositionUnknown`. `engaged` selects the composed
    rule's applicability (for an exception or a condition) over its compliance. A rule-set id
    (`RuleSet`) is its expansion over the rules the operator ranges over (`sets`, where a witness
    names them, else `rules`), evaluated with `who` bound; a set that decides nothing is
    `compositionUnknown` with the reason; where the run declares a set `incomplete` (its id), a
    `requiredBy` is never false and a `lawful` never true there, unknown instead. A case id is that rule's case (`RuleSet.caseRule`). -/
def composeWith (rules : List Rule) (sets : Option (List Rule)) (incomplete : List String) (d : Primitives.Ctx) :
    Nat → String → List (String × String) → Binding → Bool → Array R
  | 0, id, _, _, _ => Array.replicate d.n (R.u (.compositionUnknown id))
  | fuel + 1, id, map, β, engaged =>
    let β' : Binding := ⟨map.filterMap fun (inner, outer) => (β.lookup outer).map fun v => (inner, v)⟩
    if id.startsWith "#unknown:" then Array.replicate d.n (R.u (.compositionUnknown (id.drop 9).toString)) else
    match RuleSet.ofCaseId id with
    | some (rid, n) =>
      match rules.find? (·.id == rid) with
      | none => Array.replicate d.n (R.u (.compositionUnknown rid))
      | some r =>
        match r.cases.find? (·.name == n) with
        | none => Array.replicate d.n (R.u (.compositionUnknown s!"{rid} declares no case `{n}`"))
        | some cs =>
          let c : Semantics.SemCtx := { d := d, β := β', compose := composeWith rules sets incomplete d fuel }
          (RuleSet.caseRule r cs).engagedAll c
    | none =>
    if id.startsWith "#" && !(rules.any (·.id == id)) then
      let lib := sets.getD rules
      match RuleSet.expansion lib id with
      | .error why => Array.replicate d.n (R.u (.compositionUnknown why))
      | .ok (φ, extra) =>
        let rules' := extra ++ (match sets with | some fs => fs ++ rules | none => rules)
        let c : Semantics.SemCtx := { d := d, β := β', compose := composeWith rules' sets incomplete d fuel }
        let v := Rule.evalRuleFormula c φ
        -- an incomplete set may lack the rule that would require the conduct, or that is broken
        let undecidable : Tri := if id.startsWith "#requiredBy:" then .f else .t
        if incomplete.contains id then v.map fun x => if x.v == undecidable then R.u (.compositionUnknown s!"{id}: the run declares this set incomplete") else x
        else v
    else
    match rules.find? (·.id == id) with
    | none => Array.replicate d.n (R.u (.compositionUnknown id))
    | some r =>
      let c : Semantics.SemCtx := { d := d, β := β', compose := composeWith rules sets incomplete d fuel }
      if engaged then r.engagedAll c else r.asRAll c

/-- The evaluation context for a rule set over an indexed trace: composition resolves against
    `rules`, nested at most twice the library's size and the strata of the rule-set operators
    deep; the rule-set operators range over `sets` where a witness names them, else over `rules`. -/
def Rule.context (rules : List Rule) (d : Primitives.Ctx) (β : Binding) (sets : Option (List Rule) := none)
    (incomplete : List String := []) : Semantics.SemCtx :=
  { d := d, β := β, compose := composeWith rules sets incomplete d (2 * (rules.length + (sets.map List.length).getD 0) + 6) }

namespace Concept
open Semantics

-- Every concept call against the callee's signature: a track formal takes a variable bound to a
-- track, a region formal one bound to a region, a literal formal one of its admissible values, a
-- nat formal a number. Run on formulas whose own literal and nat formals already hold values.
mutual
  partial def termCallDefects (cs : List Concept) (scope : Rule.Scope) (where_ : String) : Term → List String
    | .quantity n args ps => callArgs cs scope where_ n args ++ ps.flatMap (termCallDefects cs scope where_)
    | .measure _ _ | .lit _ _ | .param _ => []
    | .distanceWhile _ φ | .sinceRise φ => callDefects cs scope where_ φ
    | .headingSince _ g ψ => termCallDefects cs scope where_ g ++ callDefects cs scope where_ ψ
    | .aggregate _ v φ t => callDefects cs ((v, .track) :: scope) where_ φ ++ termCallDefects cs ((v, .track) :: scope) where_ t
    | .add a b | .sub a b | .mul a b | .div a b => termCallDefects cs scope where_ a ++ termCallDefects cs scope where_ b
    | .neg a | .abs a => termCallDefects cs scope where_ a
    | .cond φ a b => callDefects cs scope where_ φ ++ termCallDefects cs scope where_ a ++ termCallDefects cs scope where_ b
  partial def callDefects (cs : List Concept) (scope : Rule.Scope) (where_ : String) : Formula → List String
    | .derived n args ps => callArgs cs scope where_ n args ++ ps.flatMap (termCallDefects cs scope where_)
    | .atom _ _ ps => ps.flatMap (termCallDefects cs scope where_)
    | .cmp l _ r => termCallDefects cs scope where_ l ++ termCallDefects cs scope where_ r
    | .not φ | .always φ | .eventually φ | .rises φ => callDefects cs scope where_ φ
    | .and φ ψ | .or φ ψ | .implies φ ψ | .until φ ψ | .since φ ψ | .definedWhen φ ψ | .count φ ψ _ _ =>
      callDefects cs scope where_ φ ++ callDefects cs scope where_ ψ
    | .holdsFor _ d _ φ | .within _ d _ φ => termCallDefects cs scope where_ d ++ callDefects cs scope where_ φ
    | .untilWithin _ d _ φ ψ | .atLast _ d _ φ ψ =>
      termCallDefects cs scope where_ d ++ callDefects cs scope where_ φ ++ callDefects cs scope where_ ψ
    | .durationWithin w g φ _ b =>
      termCallDefects cs scope where_ w ++ termCallDefects cs scope where_ g ++ callDefects cs scope where_ φ ++
      termCallDefects cs scope where_ b
    | .existsUser v φ | .forallUser v φ => callDefects cs ((v, .track) :: scope) where_ φ
    | .existsRegion _ v φ | .forallRegion _ v φ => callDefects cs ((v, .region) :: scope) where_ φ
    | .existsDevice _ v φ | .forallDevice _ v φ => callDefects cs ((v, .device) :: scope) where_ φ
    | _ => []
  partial def callArgs (cs : List Concept) (scope : Rule.Scope) (where_ name : String) (args : List Arg) : List String :=
    match cs.find? (·.leanName == name) with
    | none => []
    | some c =>
      if args.length != c.args.length then []        -- an arity the expansion leaves for `Rule.check` to report
      else (c.args.zip args).filterMap fun ((n, so), a) =>
        let bad := some s!"{where_}: `{c.id}` formal `{n}` ({repr so}) is given {repr a}"
        match so, a with
        | .track, .var v => if scope.binds v .track then none else bad
        | .region, .var v => if scope.binds v .region then none else bad
        | .literal vs, .lit l => if vs.contains l then none else bad
        | .nat, .nat _ => none
        | _, _ => bad
end

/-- `callDefects` on a rule before expansion: each binder's class with that binder, the
    applicability and the obligation with every binder, all as tracks. -/
def ruleCallDefects (cs : List Concept) (r : Rule) : List String :=
  let scope : Rule.Scope := r.binderNames.map fun n => (n, EntityKind.track)
  (r.binders.flatMap fun b => callDefects cs [(b.name, .track)] s!"{r.id} binder `{b.name}`" b.cls) ++
  callDefects cs scope s!"{r.id} applicability" r.applicability ++
  callDefects cs scope s!"{r.id} obligation" r.obligation


/-- Every defect a concept has before any trace: an empty id; a formal or a parameter named
    twice; a parameter named as a reading's, or a body parameter that is no formal parameter; a
    literal formal that admits no value; a composed rule, a rule-set operator, a declared intention
    or a declared fact in the body (a concept reads none of them); a referenced concept unknown, or a reference cycle; and, on every
    admissible instantiation of its literal formals with its calls expanded, every defect
    `Rule.check` finds in a formula and a call whose arguments do not fit the callee's formals. -/
def check (cs : List Concept) (c : Concept) : List String :=
  let names := c.args.map (·.1)
  let pnames := c.paramNames
  let body := c.bodyFormula
  let structural :=
    (if c.id.isEmpty then ["concept: empty id"] else []) ++
    (if names.eraseDups.length != names.length then [s!"{c.id}: duplicate formal argument"] else []) ++
    (if pnames.eraseDups.length != pnames.length then [s!"{c.id}: duplicate formal parameter"] else []) ++
    (pnames.filter (·.contains '.') |>.map fun p => s!"{c.id}: parameter `{p}` names a reading parameter; a body references its formals only") ++
    (c.args.filterMap fun (n, s) => match s with
      | .literal [] => some s!"{c.id}: literal formal `{n}` admits no value"
      | _ => none) ++
    ((Formula.params body).eraseDups.filter (!pnames.contains ·) |>.map fun p => s!"{c.id}: `{p}` is not a formal parameter") ++
    ((Formula.composed body).map fun id => s!"{c.id}: a concept composes no rule (`{id}`)") ++
    ((Formula.ruleSets body).map fun φ => s!"{c.id}: a concept reads no rule-set operator ({(RuleSet.idOf φ).getD ""})") ++
    ((Formula.intentions body).eraseDups.map fun id => s!"{c.id}: a concept reads no declared intention (`{id}`)") ++
    ((Formula.facts body).eraseDups.map fun id => s!"{c.id}: a concept reads no declared fact (`{id}`)") ++
    (c.refs.filter (fun n => !cs.any (·.leanName == n))
      |>.map fun n => s!"{c.id}: references unknown concept `{n}`") ++
    (if (onCycle cs).contains c.id then [s!"{c.id}: on a reference cycle"] else [])
  let scope : Rule.Scope := c.args.filterMap fun (n, s) => match s with
    | .track => some (n, EntityKind.track)
    | .region => some (n, EntityKind.region)
    | _ => none
  let ps : List Term := c.params.map fun p => Term.param p.name
  let byInstance := (samples c).flatMap fun args =>
    match instantiate c args ps "check" with
    | none => [s!"{c.id}: arity"]
    | some b =>
      let φ := match b with | .formula φ => φ | .quantity t => Formula.cmp t .eq t
      let φx := expand cs φ
      callDefects cs scope c.id φ ++ Rule.checkFormula scope c.id φx ++
        (Rule.pathReads (fun _ => false) false φx).map fun e => s!"{c.id}: {e}"
  structural ++ byInstance.eraseDups

/-- The aggregates a concept's body names, its calls expanded, that the reading does not declare
    or declares with an id that is no road-user class. -/
def checkReading (cs : List Concept) (c : Concept) (ρ : Reading) : List String :=
  Rule.aggregateDefects c.id (aggregateIds cs c) ρ

end Concept

end TrafficSpec
