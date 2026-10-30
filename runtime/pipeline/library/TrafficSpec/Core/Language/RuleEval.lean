/-
  TrafficSpec.Core.Language.RuleEval
  Evaluating a rule over a trace, and checking it before any trace.

  `verdicts` combines the binder classes, the applicability and the obligation per instant
  (Kleene, `verdictAt`). `check` finds from the syntax every defect the evaluator would otherwise
  report as `malformed` or `unboundVariable`: unknown names, arities, literals no codec decodes,
  variables of the wrong sort, non-constant parameters, undeclared assumptions and intentions, a
  declared intention read ahead of the judged observation, compositions of rules not in the set or
  mapping to names that are not the composed rule's binders. `checkReading`
  names the parameters the reading lacks, over the rule and the rules it composes.

  `Concept.check` holds a concept to the same standard on every admissible instantiation of
  its formals, with its calls expanded. `Concept.callDefects` holds every concept call to the
  callee's signature before expansion loses it.

  Nothing under Rules/ or Concepts/ imports this file; Grounding, Manifest and Monitor do.
-/
import TrafficSpec.Core.Language.Rule
import TrafficSpec.Core.Language.Concept
import TrafficSpec.Core.Language.Semantics

namespace TrafficSpec
namespace Rule
open Semantics

/-- A rule's formula as evaluated: every comparison over a `cond` decided by cases. -/
def evalRuleFormula (c : SemCtx) (φ : Formula) : Array R := evalAll c (Formula.elimCond φ)

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
    set, every assumption and intention used declared, every intention id well-formed, every
    operationalization bounding its standard by atoms, primitives or concepts. -/
def wellFormedBody (r : Rule) : Bool :=
  r.binderNames.eraseDups.length == r.binders.length &&
  r.binders.all (fun b => !b.name.isEmpty) &&
  !r.id.isEmpty &&
  r.usedAssumptions.all (r.assumptions.contains ·) &&
  r.usedIntentions.all (r.intentions.contains ·) &&
  r.intentions.all IntId.wellFormed &&
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
    | .rises φ => checkFormula scope where_ φ
    | .definedWhen p φ => checkFormula scope where_ p ++ checkFormula scope where_ φ
    | .derived concept args ps =>
      let inner := ps.flatMap (checkTerm scope where_) ++ constParamErrors where_ concept ps
      match dummyArgs scope (Primitives.argSorts concept) args with
      | .error e => [s!"{where_}: {e}"] ++ inner
      | .ok ds => match Primitives.evalB concept emptyCtx ds (ps.map fun _ => Q.zero) with
        | .error w => (match isMalformed w with | some m => [s!"{where_}: `{concept}`: {m}"] | none => []) ++ inner
        | .ok _ => inner
    | .rule _ map | .ruleApplies _ map => map.flatMap fun (_, outer) =>
        if scope.binds outer .track then [] else [s!"{where_}: composition maps to `{outer}`, not a bound track"]
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
    | .aggregate _ _ φ t => futureReads reads fut φ ++ futureTerm reads fut t
    | .add a b | .sub a b | .mul a b | .div a b => futureTerm reads fut a ++ futureTerm reads fut b
    | .neg a | .abs a => futureTerm reads fut a
    | .cond φ a b => futureReads reads fut φ ++ futureTerm reads fut a ++ futureTerm reads fut b
    | _ => []
  partial def futureReads (reads : String → Bool) (fut : Bool) : Formula → List String
    | .intent id _ _ => if fut then [s!"declared intention `{id}` is read ahead of the judged observation"] else []
    | .rule id _ | .ruleApplies id _ =>
      if fut && reads id then [s!"`{id}` reads a declared intention and is read ahead of the judged observation"] else []
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
    | .existsRegion _ _ φ | .forallRegion _ _ φ | .existsDevice _ _ φ | .forallDevice _ _ φ
    | .existsUser _ φ | .forallUser _ φ => futureReads reads fut φ
    | _ => []
end

/-- Every defect a rule has before any trace. Empty for a rule the evaluator will never report
    `malformed` or `unboundVariable` on. `regions` names variables the caller binds to regions:
    the region formals of a concept's instance, which alone may then have no binder. -/
def check (rules : List Rule) (r : Rule) (regions : List String := []) : List String :=
  let scope : Scope := r.binderNames.map (fun n => (n, EntityKind.track)) ++ regions.map fun n => (n, EntityKind.region)
  let formed := if regions.isEmpty then r.wellFormed else r.wellFormedBody
  let reads (id : String) : Bool := match rules.find? (·.id == id) with
    | some r' => r'.readsIntention rules
    | none => false
  (if formed then [] else [s!"{r.id}: binders empty, duplicated or unnamed, an assumption, intention or concept undeclared, or an intention id ill-formed"]) ++
  (r.binders.flatMap fun b => checkFormula [(b.name, .track)] s!"{r.id} binder `{b.name}`" b.cls) ++
  checkFormula scope s!"{r.id} applicability" r.applicability ++
  checkFormula scope s!"{r.id} obligation" r.obligation ++
  (r.formulas.flatMap (futureReads reads false) |>.eraseDups.map fun e => s!"{r.id}: {e}") ++
  (r.formulas.flatMap Formula.compositions).flatMap (fun (id, map) =>
    match rules.find? (·.id == id) with
    | none => [s!"{r.id}: composes unknown rule `{id}`"]
    | some r' =>
      (map.filter (fun (inner, _) => !r'.binderNames.contains inner) |>.map fun (inner, _) => s!"{r.id}: composition of `{id}` maps `{inner}`, not one of its binders") ++
      (r'.binderNames.filter (fun b => !map.any (·.1 == b)) |>.map fun b => s!"{r.id}: composition of `{id}` leaves its binder `{b}` unmapped"))

/-- Parameters that the rule, or a rule it composes, names and the reading lacks. -/
def checkReading (rules : List Rule) (r : Rule) (ρ : Reading) : List String :=
  (Rule.closure rules r).flatMap fun x =>
    (x.params.filter (!ρ.has ·) |>.map fun p => s!"{x.id}: parameter `{p}` is not in the reading")
    ++ (x.formulas.flatMap Formula.aggregateIds).eraseDups.flatMap fun w =>
      match ρ.aggregate w with
      | none => [s!"{x.id}: aggregate `{w}` is not declared by the reading"]
      | some a => (a.included ++ a.unresolved).filter (fun id => !id.startsWith "ru." || (RoadUserClass.ofString (id.drop 3).toString).isNone)
          |>.map fun id => s!"{x.id}: aggregate `{w}` lists `{id}`, which is not a road-user class"

end Rule

/-- Rule composition over a library, with fuel bounding the nesting depth. The composed rule's
    binders are bound through `map` (inner binder ↦ caller variable); an unmapped binder is an
    unbound variable, an unknown id is `compositionUnknown`. `engaged` selects the composed
    rule's applicability (for an exception or a condition) over its compliance. -/
def composeWith (rules : List Rule) (d : Primitives.Ctx) :
    Nat → String → List (String × String) → Binding → Bool → Array R
  | 0, id, _, _, _ => Array.replicate d.n (R.u (.compositionUnknown id))
  | fuel + 1, id, map, β, engaged =>
    match rules.find? (·.id == id) with
    | none => Array.replicate d.n (R.u (.compositionUnknown id))
    | some r =>
      let β' : Binding := ⟨map.filterMap fun (inner, outer) => (β.lookup outer).map fun v => (inner, v)⟩
      let c : Semantics.SemCtx := { d := d, β := β', compose := composeWith rules d fuel }
      if engaged then r.engagedAll c else r.asRAll c

/-- The evaluation context for a rule set over an indexed trace: composition resolves against
    `rules`, nested at most `rules.length` deep. -/
def Rule.context (rules : List Rule) (d : Primitives.Ctx) (β : Binding) : Semantics.SemCtx :=
  { d := d, β := β, compose := composeWith rules d rules.length }

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


/-- Every defect a concept has before any trace: formals named once, parameters that are formal
    (never a reading's), no composition, every referenced concept known and no cycle, and the
    body well-formed on every admissible instantiation with its calls expanded. -/
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
    ((Formula.intentions body).eraseDups.map fun id => s!"{c.id}: a concept reads no declared intention (`{id}`)") ++
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
      callDefects cs scope c.id φ ++ Rule.checkFormula scope c.id (expand cs φ)
  structural ++ byInstance.eraseDups

end Concept

end TrafficSpec
