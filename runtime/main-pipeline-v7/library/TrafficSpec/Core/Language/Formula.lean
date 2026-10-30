/-
  TrafficSpec.Core.Language.Formula
  The specification language, as data.

  A rule is an AST, not a Lean proposition, for three downstream reasons: the gate inspects it
  (which atoms, which operators, which parameters, any bare literal), the export serializes it for
  the tooling outside Lean, and the evaluator computes a three-valued verdict from it on a trace. Variables are strings bound by the grounding
  to tracks, and by the bounded quantifiers below to regions and devices of a kind.

  Atoms, primitives and concepts are referenced BY NAME (the Lean definition names of Atoms.lean
  and Primitives.lean, `family_name`; a concept's `drv_<family>_<name>`), with arguments that are variables, enumeration values spelled as in
  ATOMS.md, or naturals. Semantics.lean dispatches the names; the doctor checks every name resolves.

  A quantifier over road users ranges over every road user of the scene, the bound ones included;
  `same a b` is how a body excludes the subject from "another road user".

  The bounded quantifiers take their kind as an `Arg`: a rule spells it (`.lit "intersection"`),
  a concept fills it from a literal formal on expansion. `rises` is an edge against the previous
  observation, not a frame: it says nothing about what happened between two observations.

  `cond φ a b` selects between two quantities. A comparison over it is decided wherever both
  selections decide it alike, so an unobserved φ leaves a verdict open only where the choice
  matters (`elimCond`, applied before evaluation).

  Deliberately absent: `next` (frame-relative and meaningless under irregular sampling), any
  numeric literal without a unit, any way to call an arbitrary Lean function.
-/
import TrafficSpec.Core.Vocab.Params
import TrafficSpec.Core.Foundations.Time
import TrafficSpec.Core.Vocab.World

namespace TrafficSpec

/-- A value a formula variable can denote. -/
inductive Val
  | track (t : TrackId)
  | region (r : RegionId)
  | device (d : DeviceId)
  deriving Repr, DecidableEq, Inhabited

def Val.kind : Val → EntityKind
  | .track _ => .track
  | .region _ => .region
  | .device _ => .device

/-- Variable bindings (the grounding's output; `Env` is the world's environment record). -/
structure Binding where
  binds : List (String × Val) := []
  deriving Repr, Inhabited

namespace Binding
def lookup (e : Binding) (n : String) : Option Val := (e.binds.find? (·.1 == n)).map (·.2)
def bind (e : Binding) (n : String) (v : Val) : Binding := ⟨(n, v) :: e.binds.filter (·.1 != n)⟩
def track (e : Binding) (n : String) : Option TrackId :=
  match e.lookup n with | some (.track t) => some t | _ => none
def region (e : Binding) (n : String) : Option RegionId :=
  match e.lookup n with | some (.region r) => some r | _ => none
def device (e : Binding) (n : String) : Option DeviceId :=
  match e.lookup n with | some (.device d) => some d | _ => none
end Binding

/-- An argument to an atom or a derived concept. -/
inductive Arg
  | var (name : String)      -- a bound variable
  | lit (value : String)     -- an enumeration value, spelled as in the ontology
  | nat (n : Nat)
  deriving Repr, DecidableEq, Inhabited

inductive CmpOp
  | lt | le | eq | ge | gt
  deriving Repr, DecidableEq, Inhabited

/-- What an aggregate over road users computes. -/
inductive AggOp
  | min | max | median | count
  deriving Repr, DecidableEq, Inhabited

def AggOp.toString : AggOp → String
  | .min => "min" | .max => "max" | .median => "median" | .count => "count"
instance : ToString AggOp := ⟨AggOp.toString⟩

def CmpOp.apply : CmpOp → Q → Q → Bool
  | .lt, a, b => Q.lt a b
  | .le, a, b => Q.le a b
  | .eq, a, b => Q.eq a b
  | .ge, a, b => Q.ge a b
  | .gt, a, b => Q.gt a b

mutual
  /-- A quantity. -/
  inductive Term
    | lit (q : Q) (unit : PUnit')                            -- written through a Units constructor
    | param (name : ParamName)                               -- a reading parameter
    | measure (atom : String) (args : List Arg)              -- a measured atom (Option Q or Option Nat)
    | quantity (concept : String) (args : List Arg) (params : List Term)   -- a Q-valued derived concept
    | distanceWhile (subject : String) (φ : Formula)         -- path length over which φ has held continuously
    | sinceRise (φ : Formula)                                -- time elapsed since φ last became true
    | aggregate (op : AggOp) (var : String) (φ : Formula) (t : Term)   -- op of t over the road users var of the scene satisfying φ
    | add (a b : Term)
    | sub (a b : Term)
    | mul (a b : Term)
    | div (a b : Term)
    | neg (a : Term)
    | abs (a : Term)
    | cond (φ : Formula) (a b : Term)                        -- a where φ holds, b where it does not
  /-- A three-valued statement about the trace at an instant. -/
  inductive Formula
    | tt
    | ff
    | atom (name : String) (args : List Arg) (params : List Term)   -- a Boolean atom; params for tolerances
    | cmp (lhs : Term) (op : CmpOp) (rhs : Term)
    | asm (id : AsmId)
    | same (a b : Arg)                                        -- the two variables denote the same entity
    | not (φ : Formula)
    | and (φ ψ : Formula)
    | or (φ ψ : Formula)
    | implies (φ ψ : Formula)
    | always (φ : Formula)                                    -- from now to the end of the trace
    | eventually (φ : Formula)                                -- φ here or at some later observation, to the end of the trace
    | until (φ ψ : Formula)                                   -- strong until, future
    | since (φ ψ : Formula)                                   -- past mirror of until
    | holdsFor (m : Measure) (d : Term) (subject : String) (φ : Formula)   -- φ at every observation in the window behind
    | within (m : Measure) (d : Term) (subject : String) (φ : Formula)     -- φ at some observation in the window ahead
    | untilWithin (m : Measure) (d : Term) (subject : String) (φ ψ : Formula)   -- ψ at some observation in the window ahead, φ at every one before it
    | atLast (m : Measure) (d : Term) (subject : String) (ψ φ : Formula)   -- φ at the last observation in the window behind at which ψ held
    | count (edge : Formula) (sinceφ : Formula) (op : CmpOp) (n : Nat)   -- rising edges of `edge` since `sinceφ` became true (start of its latest run)
    | rises (φ : Formula)                                     -- φ here and not at the previous observation
    | definedWhen (pre φ : Formula)                           -- φ where `pre` holds; unknown (undefined) where it does not
    | derived (concept : String) (args : List Arg) (params : List Term)   -- a Boolean derived concept
    | rule (id : String) (map : List (String × String))       -- another rule complied with (not engaged counts as complied)
    | ruleApplies (id : String) (map : List (String × String)) -- another rule engaged (its binders' classes and applicability hold)
    | existsUser (var : String) (φ : Formula)                 -- some road user present in the scene
    | forallUser (var : String) (φ : Formula)
    | existsRegion (kind : Arg) (var : String) (φ : Formula)
    | forallRegion (kind : Arg) (var : String) (φ : Formula)
    | existsDevice (kind : Arg) (var : String) (φ : Formula)
    | forallDevice (kind : Arg) (var : String) (φ : Formula)
end

deriving instance Repr for Term
deriving instance Repr for Formula
instance : Inhabited Formula := ⟨.tt⟩
instance : Inhabited Term := ⟨.lit Q.zero .count⟩

namespace Formula
/-- The atom a window over a measure reads: the clock, or the subject's path length. -/
def measureAtom : Measure → String
  | .time => "kin_time"
  | .path => "kin_path_length"

/-- The kind atom a quantifier with a literal kind reads (`existsRegion (.lit "lane")` reads
    `st_lane`); a variable kind is a concept's literal formal, read once the instance fills it. -/
def kindAtom (prefix_ : String) : Arg → List String
  | .lit k => [prefix_ ++ k]
  | _ => []

-- The atom names a formula reads (for the gate, the manifest and the export): every leaf, the
-- measure of every window, and the kind of every quantifier with a literal kind.
mutual
  partial def termAtoms : Term → List String
    | .measure a _ => [a]
    | .quantity c _ ps => c :: (ps.flatMap termAtoms)
    | .distanceWhile _ φ => measureAtom .path :: atoms φ
    | .sinceRise φ => measureAtom .time :: atoms φ
    | .aggregate _ _ φ t => atoms φ ++ termAtoms t
    | .add a b | .sub a b | .mul a b | .div a b => termAtoms a ++ termAtoms b
    | .neg a | .abs a => termAtoms a
    | .cond φ a b => atoms φ ++ termAtoms a ++ termAtoms b
    | _ => []
  partial def atoms : Formula → List String
    | .atom n _ ps => n :: ps.flatMap termAtoms
    | .cmp l _ r => termAtoms l ++ termAtoms r
    | .not φ | .always φ | .eventually φ | .rises φ => atoms φ
    | .and φ ψ | .or φ ψ | .implies φ ψ | .until φ ψ | .since φ ψ | .definedWhen φ ψ => atoms φ ++ atoms ψ
    | .holdsFor m d _ φ | .within m d _ φ => measureAtom m :: termAtoms d ++ atoms φ
    | .untilWithin m d _ φ ψ => measureAtom m :: termAtoms d ++ atoms φ ++ atoms ψ
    | .atLast m d _ ψ φ => measureAtom m :: termAtoms d ++ atoms ψ ++ atoms φ
    | .count e s _ _ => atoms e ++ atoms s
    | .derived c _ ps => c :: ps.flatMap termAtoms
    | .existsRegion k _ φ | .forallRegion k _ φ => kindAtom "st_" k ++ atoms φ
    | .existsDevice k _ φ | .forallDevice k _ φ => kindAtom "dev_" k ++ atoms φ
    | .existsUser _ φ | .forallUser _ φ => atoms φ
    | _ => []
end

-- The reading parameters a formula names.
mutual
  partial def termParams : Term → List ParamName
    | .param n => [n]
    | .quantity _ _ ps => ps.flatMap termParams
    | .distanceWhile _ φ => params φ
    | .sinceRise φ => params φ
    | .aggregate _ _ φ t => params φ ++ termParams t
    | .add a b | .sub a b | .mul a b | .div a b => termParams a ++ termParams b
    | .neg a | .abs a => termParams a
    | .cond φ a b => params φ ++ termParams a ++ termParams b
    | _ => []
  partial def params : Formula → List ParamName
    | .atom _ _ ps => ps.flatMap termParams
    | .cmp l _ r => termParams l ++ termParams r
    | .not φ | .always φ | .eventually φ | .rises φ => params φ
    | .and φ ψ | .or φ ψ | .implies φ ψ | .until φ ψ | .since φ ψ | .definedWhen φ ψ => params φ ++ params ψ
    | .holdsFor _ d _ φ | .within _ d _ φ => termParams d ++ params φ
    | .untilWithin _ d _ φ ψ => termParams d ++ params φ ++ params ψ
    | .atLast _ d _ ψ φ => termParams d ++ params ψ ++ params φ
    | .count e s _ _ => params e ++ params s
    | .derived _ _ ps => ps.flatMap termParams
    | .existsRegion _ _ φ | .forallRegion _ _ φ | .existsDevice _ _ φ | .forallDevice _ _ φ
    | .existsUser _ φ | .forallUser _ φ => params φ
    | _ => []
end

/-- The rules a formula composes. -/
partial def composed : Formula → List String
  | .rule id _ | .ruleApplies id _ => [id]
  | .not φ | .always φ | .eventually φ | .rises φ => composed φ
  | .and φ ψ | .or φ ψ | .implies φ ψ | .until φ ψ | .since φ ψ | .definedWhen φ ψ => composed φ ++ composed ψ
  | .holdsFor _ _ _ φ | .within _ _ _ φ => composed φ
  | .untilWithin _ _ _ φ ψ => composed φ ++ composed ψ
  | .atLast _ _ _ ψ φ => composed ψ ++ composed φ
  | .count e s _ _ => composed e ++ composed s
  | .existsRegion _ _ φ | .forallRegion _ _ φ | .existsDevice _ _ φ | .forallDevice _ _ φ
  | .existsUser _ φ | .forallUser _ φ => composed φ
  | _ => []

-- Numeric literals other than zero, with their units: what the gate holds against the node's
-- declared parameters (a magnitude belongs in the reading, not in a rule).
mutual
  partial def termLiterals : Term → List (Q × PUnit')
    | .lit q u => if Q.isZero q then [] else [(q, u)]
    | .quantity _ _ ps => ps.flatMap termLiterals
    | .distanceWhile _ φ => literals φ
    | .sinceRise φ => literals φ
    | .aggregate _ _ φ t => literals φ ++ termLiterals t
    | .add a b | .sub a b | .mul a b | .div a b => termLiterals a ++ termLiterals b
    | .neg a | .abs a => termLiterals a
    | .cond φ a b => literals φ ++ termLiterals a ++ termLiterals b
    | _ => []
  partial def literals : Formula → List (Q × PUnit')
    | .atom _ _ ps => ps.flatMap termLiterals
    | .cmp l _ r => termLiterals l ++ termLiterals r
    | .not φ | .always φ | .eventually φ | .rises φ => literals φ
    | .and φ ψ | .or φ ψ | .implies φ ψ | .until φ ψ | .since φ ψ | .definedWhen φ ψ => literals φ ++ literals ψ
    | .holdsFor _ d _ φ | .within _ d _ φ => termLiterals d ++ literals φ
    | .untilWithin _ d _ φ ψ => termLiterals d ++ literals φ ++ literals ψ
    | .atLast _ d _ ψ φ => termLiterals d ++ literals ψ ++ literals φ
    | .count e s _ _ => literals e ++ literals s
    | .derived _ _ ps => ps.flatMap termLiterals
    | .existsRegion _ _ φ | .forallRegion _ _ φ | .existsDevice _ _ φ | .forallDevice _ _ φ
    | .existsUser _ φ | .forallUser _ φ => literals φ
    | _ => []
end

/-- A leaf is a subformula that reads the world or another rule: an atom, a comparison, an
    assumption, a derived concept or a composition. Leaves are numbered in traversal order. -/
def isLeaf : Formula → Bool
  | .atom .. | .cmp .. | .asm _ | .derived .. | .rule .. | .ruleApplies .. => true
  | _ => false

/-- The leaves in traversal order, as a description each. -/
partial def leaves : Formula → List String
  | .atom n args _ => [s!"atom {n} {repr args}"]
  | .cmp l _ r => [s!"cmp {repr l} {repr r}"]
  | .asm id => [s!"asm {id}"]
  | .derived n args _ => [s!"derived {n} {repr args}"]
  | .rule id _ => [s!"rule {id}"]
  | .ruleApplies id _ => [s!"ruleApplies {id}"]
  | .not φ | .always φ | .eventually φ | .rises φ => leaves φ
  | .and φ ψ | .or φ ψ | .implies φ ψ | .until φ ψ | .since φ ψ | .definedWhen φ ψ => leaves φ ++ leaves ψ
  | .holdsFor _ _ _ φ | .within _ _ _ φ => leaves φ
  | .untilWithin _ _ _ φ ψ => leaves φ ++ leaves ψ
  | .atLast _ _ _ ψ φ => leaves ψ ++ leaves φ
  | .count e s _ _ => leaves e ++ leaves s
  | .existsRegion _ _ φ | .forallRegion _ _ φ | .existsDevice _ _ φ | .forallDevice _ _ φ
  | .existsUser _ φ | .forallUser _ φ => leaves φ
  | _ => []

def leafCount (φ : Formula) : Nat := (leaves φ).length

/-- The formula with its `k`-th leaf (traversal order) replaced by `r`, and the number of leaves
    in the formula. A subformula whose leaves all precede or follow the `k`-th is returned as it is. -/
partial def replaceLeafAux (k : Nat) (r : Formula) : Formula → Formula × Nat
  | φ@(.atom ..) | φ@(.cmp ..) | φ@(.asm _) | φ@(.derived ..) | φ@(.rule ..) | φ@(.ruleApplies ..) =>
    (if k = 0 then r else φ, 1)
  | .not φ => let (φ', n) := replaceLeafAux k r φ; (.not φ', n)
  | .always φ => let (φ', n) := replaceLeafAux k r φ; (.always φ', n)
  | .eventually φ => let (φ', n) := replaceLeafAux k r φ; (.eventually φ', n)
  | .and φ ψ => let (φ', ψ', n) := two k r φ ψ; (.and φ' ψ', n)
  | .or φ ψ => let (φ', ψ', n) := two k r φ ψ; (.or φ' ψ', n)
  | .implies φ ψ => let (φ', ψ', n) := two k r φ ψ; (.implies φ' ψ', n)
  | .until φ ψ => let (φ', ψ', n) := two k r φ ψ; (.until φ' ψ', n)
  | .since φ ψ => let (φ', ψ', n) := two k r φ ψ; (.since φ' ψ', n)
  | .holdsFor m d s φ => let (φ', n) := replaceLeafAux k r φ; (.holdsFor m d s φ', n)
  | .within m d s φ => let (φ', n) := replaceLeafAux k r φ; (.within m d s φ', n)
  | .untilWithin m d s φ ψ => let (φ', ψ', n) := two k r φ ψ; (.untilWithin m d s φ' ψ', n)
  | .atLast m d s ψ φ => let (ψ', φ', n) := two k r ψ φ; (.atLast m d s ψ' φ', n)
  | .count e s op c => let (e', s', n) := two k r e s; (.count e' s' op c, n)
  | .rises φ => let (φ', n) := replaceLeafAux k r φ; (.rises φ', n)
  | .definedWhen p φ => let (p', φ', n) := two k r p φ; (.definedWhen p' φ', n)
  | .existsRegion kd v φ => let (φ', n) := replaceLeafAux k r φ; (.existsRegion kd v φ', n)
  | .forallRegion kd v φ => let (φ', n) := replaceLeafAux k r φ; (.forallRegion kd v φ', n)
  | .existsDevice kd v φ => let (φ', n) := replaceLeafAux k r φ; (.existsDevice kd v φ', n)
  | .forallDevice kd v φ => let (φ', n) := replaceLeafAux k r φ; (.forallDevice kd v φ', n)
  | .existsUser v φ => let (φ', n) := replaceLeafAux k r φ; (.existsUser v φ', n)
  | .forallUser v φ => let (φ', n) := replaceLeafAux k r φ; (.forallUser v φ', n)
  | φ => (φ, 0)
where
  /-- Two subformulas in sequence: the right one is touched only when the target leaf lies in it. -/
  two (k : Nat) (r : Formula) (φ ψ : Formula) : Formula × Formula × Nat :=
    let (φ', n) := replaceLeafAux k r φ
    if k < n then (φ', ψ, n + leafCount ψ)
    else let (ψ', m) := replaceLeafAux (k - n) r ψ; (φ', ψ', n + m)

/-- The formula with its `k`-th leaf replaced by `r`. -/
def replaceLeaf (k : Nat) (r : Formula) (φ : Formula) : Formula := (replaceLeafAux k r φ).1

/-- The assumptions a formula reads. -/
partial def assumptions : Formula → List AsmId
  | .asm id => [id]
  | .not φ | .always φ | .eventually φ | .rises φ => assumptions φ
  | .and φ ψ | .or φ ψ | .implies φ ψ | .until φ ψ | .since φ ψ | .definedWhen φ ψ => assumptions φ ++ assumptions ψ
  | .holdsFor _ _ _ φ | .within _ _ _ φ => assumptions φ
  | .untilWithin _ _ _ φ ψ => assumptions φ ++ assumptions ψ
  | .atLast _ _ _ ψ φ => assumptions ψ ++ assumptions φ
  | .count e s _ _ => assumptions e ++ assumptions s
  | .existsRegion _ _ φ | .forallRegion _ _ φ | .existsDevice _ _ φ | .forallDevice _ _ φ
  | .existsUser _ φ | .forallUser _ φ => assumptions φ
  | _ => []

/-- The aggregate ids a formula names (`ru_aggregate x "<definition id>::<term>"`), for the reading check. -/
partial def aggregateIds : Formula → List String
  | .atom "ru_aggregate" [_, .lit w] _ => [w]
  | .not φ | .always φ | .eventually φ | .rises φ => aggregateIds φ
  | .and φ ψ | .or φ ψ | .implies φ ψ | .until φ ψ | .since φ ψ | .definedWhen φ ψ => aggregateIds φ ++ aggregateIds ψ
  | .holdsFor _ _ _ φ | .within _ _ _ φ => aggregateIds φ
  | .untilWithin _ _ _ φ ψ => aggregateIds φ ++ aggregateIds ψ
  | .atLast _ _ _ ψ φ => aggregateIds ψ ++ aggregateIds φ
  | .count e s _ _ => aggregateIds e ++ aggregateIds s
  | .existsRegion _ _ φ | .forallRegion _ _ φ | .existsDevice _ _ φ | .forallDevice _ _ φ
  | .existsUser _ φ | .forallUser _ φ => aggregateIds φ
  | _ => []

/-- The first `cond` of a term reachable through arithmetic (not inside an aggregate or a window,
    whose body ranges over its own variable or instants), with the term rebuilt on each branch. -/
partial def splitCond : Term → Option (Formula × Term × Term)
  | .cond φ a b => some (φ, a, b)
  | .add x y => two .add x y
  | .sub x y => two .sub x y
  | .mul x y => two .mul x y
  | .div x y => two .div x y
  | .neg x => (splitCond x).map fun (φ, a, b) => (φ, .neg a, .neg b)
  | .abs x => (splitCond x).map fun (φ, a, b) => (φ, .abs a, .abs b)
  | _ => none
where
  two (k : Term → Term → Term) (x y : Term) : Option (Formula × Term × Term) :=
    match splitCond x with
    | some (φ, a, b) => some (φ, k a y, k b y)
    | none => (splitCond y).map fun (φ, a, b) => (φ, k x a, k x b)

/-- Every comparison over a `cond` rewritten by cases: `(φ ∧ A) ∨ (¬φ ∧ B) ∨ (A ∧ B)`, with `A` and
    `B` the comparison on each branch. Where φ is decided this is the selected branch; where φ is
    unknown it is decided exactly when both branches decide it alike. -/
partial def elimCond : Formula → Formula
  | .cmp l op r =>
    match splitCond l, splitCond r with
    | some (φ, a, b), _ => cases φ (.cmp a op r) (.cmp b op r)
    | none, some (φ, a, b) => cases φ (.cmp l op a) (.cmp l op b)
    | none, none => .cmp l op r
  | .not φ => .not (elimCond φ)
  | .and φ ψ => .and (elimCond φ) (elimCond ψ)
  | .or φ ψ => .or (elimCond φ) (elimCond ψ)
  | .implies φ ψ => .implies (elimCond φ) (elimCond ψ)
  | .always φ => .always (elimCond φ)
  | .eventually φ => .eventually (elimCond φ)
  | .until φ ψ => .until (elimCond φ) (elimCond ψ)
  | .since φ ψ => .since (elimCond φ) (elimCond ψ)
  | .holdsFor m d s φ => .holdsFor m d s (elimCond φ)
  | .within m d s φ => .within m d s (elimCond φ)
  | .untilWithin m d s φ ψ => .untilWithin m d s (elimCond φ) (elimCond ψ)
  | .atLast m d s ψ φ => .atLast m d s (elimCond ψ) (elimCond φ)
  | .count e s op n => .count (elimCond e) (elimCond s) op n
  | .rises φ => .rises (elimCond φ)
  | .definedWhen p φ => .definedWhen (elimCond p) (elimCond φ)
  | .existsUser v φ => .existsUser v (elimCond φ)
  | .forallUser v φ => .forallUser v (elimCond φ)
  | .existsRegion k v φ => .existsRegion k v (elimCond φ)
  | .forallRegion k v φ => .forallRegion k v (elimCond φ)
  | .existsDevice k v φ => .existsDevice k v (elimCond φ)
  | .forallDevice k v φ => .forallDevice k v (elimCond φ)
  | φ => φ
where
  cases (φ A B : Formula) : Formula :=
    let A := elimCond A; let B := elimCond B; let φ := elimCond φ
    .or (.or (.and φ A) (.and (.not φ) B)) (.and A B)
end Formula

end TrafficSpec
