/-
  TrafficSpec.Core.Language.RuleEval
  Evaluating a rule over a trace, and checking it before any trace.

  `verdicts` combines the binder classes, the applicability and the obligation per instant
  (Kleene, `verdictAt`). `check` finds from the syntax every defect the evaluator would otherwise
  report as `malformed` or `unboundVariable`: unknown names, arities, literals no codec decodes,
  variables of the wrong sort, non-constant parameters, undeclared assumptions, compositions of
  rules not in the set or mapping to names that are not the composed rule's binders. `checkReading`
  names the parameters the reading lacks, over the rule and the rules it composes.

  `Concept.check` holds a concept to the same standard on every admissible instantiation of
  its formals, with its calls expanded.

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

/-- Structural well-formedness: binders named and distinct, the id set, every assumption used
    declared, every operationalization bounding its standard by atoms, primitives or concepts. -/
def wellFormed (r : Rule) : Bool :=
  !r.binders.isEmpty &&
  r.binderNames.eraseDups.length == r.binders.length &&
  r.binders.all (fun b => !b.name.isEmpty) &&
  !r.id.isEmpty &&
  r.usedAssumptions.all (r.assumptions.contains ·) &&
  r.operationalizations.all (fun o => !o.concepts.isEmpty && o.concepts.all fun c =>
    c.startsWith "drv." || Primitives.primitiveNames.contains (defName c) || knowsAtom (defName c))

-- ---------------------------------------------------------------------------------------------
-- Static check
-- ---------------------------------------------------------------------------------------------
/-- Variables in scope with their sorts. -/
abbrev Scope := List (String × EntityKind)

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
      (if scope.any (fun (v, so) => v == subj && so == .track) then [] else [s!"{where_}: subject `{subj}` is not a bound track"]) ++
      checkFormula scope where_ φ
    | .sinceRise φ => checkFormula scope where_ φ
    | .aggregate _ v φ t => checkFormula ((v, .track) :: scope) where_ φ ++ checkTerm ((v, .track) :: scope) where_ t
    | .add a b | .sub a b | .mul a b | .div a b => checkTerm scope where_ a ++ checkTerm scope where_ b
    | .neg a | .abs a => checkTerm scope where_ a
    | .cond φ a b => checkFormula scope where_ φ ++ checkTerm scope where_ a ++ checkTerm scope where_ b

  partial def checkFormula (scope : Scope) (where_ : String) : Formula → List String
    | .tt | .ff | .asm _ => []
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
        if scope.any (fun (v, so) => v == outer && so == .track) then [] else [s!"{where_}: composition maps to `{outer}`, not a bound track"]
    | .existsRegion k v φ | .forallRegion k v φ =>
      kindErrors where_ k "region" (fun s => (StructureKind.ofString s).isSome) ++ checkFormula ((v, .region) :: scope) where_ φ
    | .existsDevice k v φ | .forallDevice k v φ =>
      kindErrors where_ k "device" (fun s => (DeviceKind.ofString s).isSome) ++ checkFormula ((v, .device) :: scope) where_ φ
    | .existsUser v φ | .forallUser v φ => checkFormula ((v, .track) :: scope) where_ φ

  partial def windowErrors (scope : Scope) (where_ : String) (m : Measure) (d : Term) (subj : String) : List String :=
    (if m = .path && !scope.any (fun (v, so) => v == subj && so == .track) then [s!"{where_}: window subject `{subj}` is not a bound track"] else []) ++
    (if Term.isConstant d then [] else [s!"{where_}: window length is not a constant term"])
end

/-- Every defect a rule has before any trace. Empty for a rule the evaluator will never report
    `malformed` or `unboundVariable` on. -/
def check (rules : List Rule) (r : Rule) : List String :=
  let scope : Scope := r.binderNames.map fun n => (n, .track)
  (if r.wellFormed then [] else [s!"{r.id}: binders empty, duplicated or unnamed, or an assumption or concept undeclared"]) ++
  (r.binders.flatMap fun b => checkFormula [(b.name, .track)] s!"{r.id} binder `{b.name}`" b.cls) ++
  checkFormula scope s!"{r.id} applicability" r.applicability ++
  checkFormula scope s!"{r.id} obligation" r.obligation ++
  (r.formulas.flatMap compositions).flatMap (fun (id, map) =>
    match rules.find? (·.id == id) with
    | none => [s!"{r.id}: composes unknown rule `{id}`"]
    | some r' =>
      (map.filter (fun (inner, _) => !r'.binderNames.contains inner) |>.map fun (inner, _) => s!"{r.id}: composition of `{id}` maps `{inner}`, not one of its binders") ++
      (r'.binderNames.filter (fun b => !map.any (·.1 == b)) |>.map fun b => s!"{r.id}: composition of `{id}` leaves its binder `{b}` unmapped"))
where
  compositions : Formula → List (String × List (String × String))
    | .rule id map | .ruleApplies id map => [(id, map)]
    | .not φ | .always φ | .eventually φ | .rises φ => compositions φ
    | .and φ ψ | .or φ ψ | .implies φ ψ | .until φ ψ | .since φ ψ | .definedWhen φ ψ => compositions φ ++ compositions ψ
    | .holdsFor _ _ _ φ | .within _ _ _ φ => compositions φ
    | .untilWithin _ _ _ φ ψ => compositions φ ++ compositions ψ
    | .atLast _ _ _ ψ φ => compositions ψ ++ compositions φ
    | .count e s _ _ => compositions e ++ compositions s
    | .existsRegion _ _ φ | .forallRegion _ _ φ | .existsDevice _ _ φ | .forallDevice _ _ φ
    | .existsUser _ φ | .forallUser _ φ => compositions φ
    | _ => []

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
    (c.refs.filter (fun n => !cs.any (·.leanName == n))
      |>.map fun n => s!"{c.id}: references unknown concept `{n}`") ++
    (if (onCycle cs).contains c.id then [s!"{c.id}: on a reference cycle"] else [])
  let scope : Rule.Scope := (trackFormals c).map fun n => (n, EntityKind.track)
  let ps : List Term := c.params.map fun p => Term.param p.name
  let byInstance := (samples c).flatMap fun args =>
    match instantiate c args ps "check" with
    | none => [s!"{c.id}: arity"]
    | some b =>
      let φ := match b with | .formula φ => φ | .quantity t => Formula.cmp t .eq t
      Rule.checkFormula scope c.id (expand cs φ)
  structural ++ byInstance.eraseDups

end Concept

end TrafficSpec
