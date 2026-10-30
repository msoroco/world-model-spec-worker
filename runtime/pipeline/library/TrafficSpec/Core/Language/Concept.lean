/-
  TrafficSpec.Core.Language.Concept
  A derived concept as data: a contract, typed formal arguments, formal parameters, and a body
  that is a `Formula` or a `Term` over atoms, primitives and other concepts. A rule names a
  concept (`Formula.derived`, `Term.quantity`) with actual arguments and parameter terms;
  `expand` replaces the name by the body with the actuals substituted, so evaluation, support
  and adequacy see atoms only.

  A body references only its formals: every free `.var` is a formal argument, every `.param` a
  formal parameter. The bound variables of a body (quantifier variables, window subjects) are
  renamed on expansion, so an actual is never captured.

  Declarations, substitution and expansion only; no evaluator. A concept file imports this
  module and nothing else. The static check is `Concept.check` in RuleEval.lean.
-/
import TrafficSpec.Core.Language.Rule

namespace TrafficSpec

/-- The sort of a formal argument. A literal formal ranges over the admissible spellings; a region
    formal is the region the caller singles out, never one the body finds for itself. -/
inductive ArgSort
  | track
  | region
  | literal (values : List String)
  | nat
  deriving Repr, DecidableEq, Inhabited

structure ConceptParam where
  name : ParamName
  unit : PUnit'
  deriving Repr, Inhabited

inductive ConceptBody
  | formula (φ : Formula)
  | quantity (t : Term)
  deriving Repr, Inhabited

structure Concept where
  id : String                          -- drv.<family>.<name>
  contract : String
  definition : Option String := none   -- the corpus definition the contract quotes, when it has one
  args : List (String × ArgSort)
  params : List ConceptParam
  body : ConceptBody
  residues : List String := []
  narrowings : List Narrowing := []
  supersedes : Option String := none
  deriving Repr, Inhabited

namespace Concept

def leanName (c : Concept) : String := c.id.replace "." "_"
def isQuantity (c : Concept) : Bool := match c.body with | .quantity _ => true | _ => false
def trackFormals (c : Concept) : List String :=
  c.args.filterMap fun (n, s) => if s == .track then some n else none
def regionFormals (c : Concept) : List String :=
  c.args.filterMap fun (n, s) => if s == .region then some n else none
def paramNames (c : Concept) : List ParamName := c.params.map (·.name)
/-- The body as a formula, for the inspectors (a quantity as a trivial comparison of itself). -/
def bodyFormula (c : Concept) : Formula :=
  match c.body with
  | .formula φ => φ
  | .quantity t => .cmp t .eq t
/-- Instantiations that cover every admissible literal: the formals as themselves, then each
    literal value once with the other literals at their first value. -/
def samples (c : Concept) : List (List Arg) :=
  let base : List Arg := c.args.map fun (n, s) => match s with
    | .track | .region => Arg.var n
    | .literal vs => Arg.lit (vs.headD "")
    | .nat => Arg.nat 0
  let variants := (List.range c.args.length).flatMap fun i =>
    match (c.args[i]? : Option (String × ArgSort)) with
    | some (_, ArgSort.literal vs) => vs.map fun v => base.set i (Arg.lit v)
    | _ => []
  (base :: variants).eraseDups

-- ---------------------------------------------------------------------------------------------
-- Substitution: formals ↦ actuals, bound variables renamed with a tag unique to the expansion.
-- ---------------------------------------------------------------------------------------------
structure Subst where
  vars : List (String × Arg)
  params : List (String × Term)
  tag : String

namespace Subst
def arg (σ : Subst) : Arg → Arg
  | .var v => match σ.vars.find? (·.1 == v) with | some (_, a) => a | none => .var v
  | a => a
/-- A variable used by name (a window subject, a composition target). -/
def name (σ : Subst) (v : String) : String :=
  match σ.vars.find? (·.1 == v) with | some (_, .var w) => w | _ => v
/-- Bind a variable of the body: renamed with the tag, shadowing any formal of the same name. -/
def bind (σ : Subst) (v : String) : Subst × String :=
  let w := v ++ "#" ++ σ.tag
  ({ σ with vars := (v, .var w) :: σ.vars }, w)
end Subst

mutual
  partial def substT (σ : Subst) : Term → Term
    | .lit q u => .lit q u
    | .param p => match σ.params.find? (·.1 == p) with | some (_, t) => t | none => .param p
    | .measure a args => .measure a (args.map σ.arg)
    | .quantity c args ps => .quantity c (args.map σ.arg) (ps.map (substT σ))
    | .distanceWhile s φ => .distanceWhile (σ.name s) (substF σ φ)
    | .sinceRise φ => .sinceRise (substF σ φ)
    | .aggregate op v φ t => let (σ', w) := σ.bind v; .aggregate op w (substF σ' φ) (substT σ' t)
    | .add a b => .add (substT σ a) (substT σ b)
    | .sub a b => .sub (substT σ a) (substT σ b)
    | .mul a b => .mul (substT σ a) (substT σ b)
    | .div a b => .div (substT σ a) (substT σ b)
    | .neg a => .neg (substT σ a)
    | .abs a => .abs (substT σ a)
    | .cond φ a b => .cond (substF σ φ) (substT σ a) (substT σ b)
  partial def substF (σ : Subst) : Formula → Formula
    | .tt => .tt
    | .ff => .ff
    | .atom n args ps => .atom n (args.map σ.arg) (ps.map (substT σ))
    | .cmp l op r => .cmp (substT σ l) op (substT σ r)
    | .asm id => .asm id
    | .intent id who target => .intent id (σ.arg who) (σ.arg target)
    | .same a b => .same (σ.arg a) (σ.arg b)
    | .not φ => .not (substF σ φ)
    | .and φ ψ => .and (substF σ φ) (substF σ ψ)
    | .or φ ψ => .or (substF σ φ) (substF σ ψ)
    | .implies φ ψ => .implies (substF σ φ) (substF σ ψ)
    | .always φ => .always (substF σ φ)
    | .eventually φ => .eventually (substF σ φ)
    | .until φ ψ => .until (substF σ φ) (substF σ ψ)
    | .since φ ψ => .since (substF σ φ) (substF σ ψ)
    | .holdsFor m d s φ => .holdsFor m (substT σ d) (σ.name s) (substF σ φ)
    | .within m d s φ => .within m (substT σ d) (σ.name s) (substF σ φ)
    | .untilWithin m d s φ ψ => .untilWithin m (substT σ d) (σ.name s) (substF σ φ) (substF σ ψ)
    | .atLast m d s ψ φ => .atLast m (substT σ d) (σ.name s) (substF σ ψ) (substF σ φ)
    | .count e s op n => .count (substF σ e) (substF σ s) op n
    | .rises φ => .rises (substF σ φ)
    | .definedWhen p φ => .definedWhen (substF σ p) (substF σ φ)
    | .derived c args ps => .derived c (args.map σ.arg) (ps.map (substT σ))
    | .rule id map => .rule id (map.map fun (i, o) => (i, σ.name o))
    | .ruleApplies id map => .ruleApplies id (map.map fun (i, o) => (i, σ.name o))
    | .existsUser v φ => let (σ', w) := σ.bind v; .existsUser w (substF σ' φ)
    | .forallUser v φ => let (σ', w) := σ.bind v; .forallUser w (substF σ' φ)
    | .existsRegion k v φ => let (σ', w) := σ.bind v; .existsRegion (σ.arg k) w (substF σ' φ)
    | .forallRegion k v φ => let (σ', w) := σ.bind v; .forallRegion (σ.arg k) w (substF σ' φ)
    | .existsDevice k v φ => let (σ', w) := σ.bind v; .existsDevice (σ.arg k) w (substF σ' φ)
    | .forallDevice k v φ => let (σ', w) := σ.bind v; .forallDevice (σ.arg k) w (substF σ' φ)
end

/-- The body with the actuals substituted; `none` when an arity differs. -/
def instantiate (c : Concept) (args : List Arg) (ps : List Term) (tag : String) : Option ConceptBody :=
  if args.length != c.args.length || ps.length != c.params.length then none
  else
    let σ : Subst := { vars := (c.args.map (·.1)).zip args, params := (c.paramNames).zip ps, tag := tag }
    some (match c.body with
      | .formula φ => .formula (substF σ φ)
      | .quantity t => .quantity (substT σ t))

/-- Atom, primitive and concept names the body reads, over every sample instantiation, so a
    quantifier whose kind is a literal formal reads every admissible kind. -/
def atoms (c : Concept) : List String :=
  let ps : List Term := c.params.map fun p => Term.param p.name
  ((samples c).flatMap fun args =>
    match instantiate c args ps "atoms" with
    | some (.formula φ) => Formula.atoms φ
    | some (.quantity t) => Formula.termAtoms t
    | none => Formula.atoms c.bodyFormula).eraseDups
/-- The concepts the body references, by Lean name. -/
def refs (c : Concept) : List String := (atoms c).filter (·.startsWith "drv_")

-- ---------------------------------------------------------------------------------------------
-- Expansion: every concept call replaced by its body, `fuel` levels deep; a counter gives each
-- expansion its own tag. A name no concept carries, or a call of the wrong arity, is left as
-- it is for the static check to report.
-- ---------------------------------------------------------------------------------------------
private def nextTag : StateM Nat String := modifyGet fun k => (toString k, k + 1)

mutual
  partial def expandT (cs : List Concept) (fuel : Nat) : Term → StateM Nat Term
    | .quantity n args ps => do
      let ps' ← ps.mapM (expandT cs fuel)
      match cs.find? (·.leanName == n), fuel with
      | some c, fuel' + 1 =>
        let tag ← nextTag
        match instantiate c args ps' tag with
        | some (.quantity t) => expandT cs fuel' t
        | _ => pure (.quantity n args ps')
      | _, _ => pure (.quantity n args ps')
    | .distanceWhile s φ => do pure (.distanceWhile s (← expandF cs fuel φ))
    | .sinceRise φ => do pure (.sinceRise (← expandF cs fuel φ))
    | .aggregate op v φ t => do pure (.aggregate op v (← expandF cs fuel φ) (← expandT cs fuel t))
    | .add a b => do pure (.add (← expandT cs fuel a) (← expandT cs fuel b))
    | .sub a b => do pure (.sub (← expandT cs fuel a) (← expandT cs fuel b))
    | .mul a b => do pure (.mul (← expandT cs fuel a) (← expandT cs fuel b))
    | .div a b => do pure (.div (← expandT cs fuel a) (← expandT cs fuel b))
    | .neg a => do pure (.neg (← expandT cs fuel a))
    | .abs a => do pure (.abs (← expandT cs fuel a))
    | .cond φ a b => do pure (.cond (← expandF cs fuel φ) (← expandT cs fuel a) (← expandT cs fuel b))
    | t => pure t
  partial def expandF (cs : List Concept) (fuel : Nat) : Formula → StateM Nat Formula
    | .derived n args ps => do
      let ps' ← ps.mapM (expandT cs fuel)
      match cs.find? (·.leanName == n), fuel with
      | some c, fuel' + 1 =>
        let tag ← nextTag
        match instantiate c args ps' tag with
        | some (.formula φ) => expandF cs fuel' φ
        | _ => pure (.derived n args ps')
      | _, _ => pure (.derived n args ps')
    | .atom n args ps => do pure (.atom n args (← ps.mapM (expandT cs fuel)))
    | .cmp l op r => do pure (.cmp (← expandT cs fuel l) op (← expandT cs fuel r))
    | .not φ => do pure (.not (← expandF cs fuel φ))
    | .and φ ψ => do pure (.and (← expandF cs fuel φ) (← expandF cs fuel ψ))
    | .or φ ψ => do pure (.or (← expandF cs fuel φ) (← expandF cs fuel ψ))
    | .implies φ ψ => do pure (.implies (← expandF cs fuel φ) (← expandF cs fuel ψ))
    | .always φ => do pure (.always (← expandF cs fuel φ))
    | .eventually φ => do pure (.eventually (← expandF cs fuel φ))
    | .until φ ψ => do pure (.until (← expandF cs fuel φ) (← expandF cs fuel ψ))
    | .since φ ψ => do pure (.since (← expandF cs fuel φ) (← expandF cs fuel ψ))
    | .holdsFor m d s φ => do pure (.holdsFor m (← expandT cs fuel d) s (← expandF cs fuel φ))
    | .within m d s φ => do pure (.within m (← expandT cs fuel d) s (← expandF cs fuel φ))
    | .untilWithin m d s φ ψ => do
      pure (.untilWithin m (← expandT cs fuel d) s (← expandF cs fuel φ) (← expandF cs fuel ψ))
    | .atLast m d s ψ φ => do
      pure (.atLast m (← expandT cs fuel d) s (← expandF cs fuel ψ) (← expandF cs fuel φ))
    | .count e s op n => do pure (.count (← expandF cs fuel e) (← expandF cs fuel s) op n)
    | .rises φ => do pure (.rises (← expandF cs fuel φ))
    | .definedWhen p φ => do pure (.definedWhen (← expandF cs fuel p) (← expandF cs fuel φ))
    | .existsUser v φ => do pure (.existsUser v (← expandF cs fuel φ))
    | .forallUser v φ => do pure (.forallUser v (← expandF cs fuel φ))
    | .existsRegion k v φ => do pure (.existsRegion k v (← expandF cs fuel φ))
    | .forallRegion k v φ => do pure (.forallRegion k v (← expandF cs fuel φ))
    | .existsDevice k v φ => do pure (.existsDevice k v (← expandF cs fuel φ))
    | .forallDevice k v φ => do pure (.forallDevice k v (← expandF cs fuel φ))
    | φ => pure φ
end

/-- Every concept call expanded, to any depth the library allows. -/
def expand (cs : List Concept) (φ : Formula) : Formula := (expandF cs (cs.length + 1) φ).run' 0
def expandTerm (cs : List Concept) (t : Term) : Term := (expandT cs (cs.length + 1) t).run' 0
/-- The outermost calls only: a concept's witnesses exercise its own body, not the bodies of
    the concepts it uses. -/
def expandOnce (cs : List Concept) (φ : Formula) : Formula := (expandF cs 1 φ).run' 0

def expandRule (cs : List Concept) (r : Rule) : Rule :=
  { r with binders := r.binders.map fun b => { b with cls := expand cs b.cls }
           applicability := expand cs r.applicability
           obligation := expand cs r.obligation }

-- ---------------------------------------------------------------------------------------------
-- Reference cycles
-- ---------------------------------------------------------------------------------------------
/-- Every concept name reachable from `start` through the references, `start` included. -/
def reachable (cs : List Concept) (start : List String) : List String :=
  let step (seen : List String) : List String :=
    (seen ++ seen.flatMap fun n => match cs.find? (·.leanName == n) with
      | some c => c.refs
      | none => []).eraseDups
  (List.range (cs.length + 1)).foldl (fun acc _ => step acc) start

/-- The ids of the concepts that reach themselves. -/
def onCycle (cs : List Concept) : List String :=
  cs.filterMap fun c => if (reachable cs c.refs).contains c.leanName then some c.id else none

-- ---------------------------------------------------------------------------------------------
-- Witness instances: a concept applied to named tracks, chosen literals and parameter terms,
-- as a rule the witness machinery can run. Track formals are the rule's binders, by name; region
-- formals stay variables, which each scenario of the instance binds to a region of its trace.
-- ---------------------------------------------------------------------------------------------
structure Instance where
  name : String
  concept : String                          -- the concept id
  literals : List (String × String) := []   -- literal formal ↦ spelling
  nats : List (String × Nat) := []
  params : List (String × Term) := []       -- formal parameter ↦ a constant term
  bounds : Option (Term × Term) := none     -- a quantity: the value lies in [lo, hi]
  deriving Repr, Inhabited

/-- The instance as a rule: every track formal a binder of class `tt`, applicability `tt`, the
    body (its own calls expanded once) as the obligation. `none` when the concept is not in the
    list or the instance leaves a formal unfilled. -/
def asRule (cs : List Concept) (i : Instance) : Option Rule := do
  let c ← cs.find? (·.id == i.concept)
  let args : List Arg ← c.args.mapM fun (n, s) => match s with
    | .track | .region => some (.var n)
    | .literal _ => (i.literals.find? (·.1 == n)).map fun (_, v) => Arg.lit v
    | .nat => (i.nats.find? (·.1 == n)).map fun (_, k) => Arg.nat k
  let ps : List Term ← c.params.mapM fun p => (i.params.find? (·.1 == p.name)).map (·.2)
  let value : Term := .quantity c.leanName args ps
  let call : Formula ← match c.body, i.bounds with
    | .formula _, _ => some (Formula.derived c.leanName args ps)
    | .quantity _, some (lo, hi) => some (Formula.and (Formula.cmp lo .le value) (Formula.cmp value .le hi))
    | .quantity _, none => none
  pure { id := i.name
         laws := []
         binders := (trackFormals c).map fun n => ⟨n, .tt⟩
         applicability := .tt
         obligation := expandOnce cs call }

/-- Each formal named exactly once among the names given, and no name that is not a formal. -/
private def givenOnce (where_ what : String) (formals given : List String) : List String :=
  (formals.filter (fun f => given.count f != 1)).map (fun f => s!"{where_}: {what} formal `{f}` given {given.count f} times") ++
  (given.eraseDups.filter (!formals.contains ·)).map fun g => s!"{where_}: `{g}` is no {what} formal"

/-- What is wrong with an instance's values: a concept the list lacks, a literal, nat or
    parameter formal not given exactly once, a name that is no formal of its sort, a literal
    outside its admissible values. -/
def Instance.defects (cs : List Concept) (i : Instance) : List String :=
  match cs.find? (·.id == i.concept) with
  | none => [s!"{i.name}: concept `{i.concept}` is not in the list"]
  | some c =>
    let lits := c.args.filterMap fun (n, s) => match s with | .literal _ => some n | _ => none
    let nats := c.args.filterMap fun (n, s) => if s == .nat then some n else none
    givenOnce i.name "literal" lits (i.literals.map (·.1)) ++
    givenOnce i.name "nat" nats (i.nats.map (·.1)) ++
    givenOnce i.name "parameter" c.paramNames (i.params.map (·.1)) ++
    i.literals.filterMap fun (n, v) => match c.args.find? (·.1 == n) with
      | some (_, .literal vs) => if vs.contains v then none else some s!"{i.name}: literal `{n}` is `{v}`, not one of {vs}"
      | _ => none

/-- What is wrong with the regions a scenario or a challenge gives an instance: each region formal
    given exactly once, and no name that is not one. -/
def regionDefects (c : Concept) (where_ : String) (regions : List (String × RegionId)) : List String :=
  givenOnce where_ "region" c.regionFormals (regions.map (·.1))

end Concept
end TrafficSpec
