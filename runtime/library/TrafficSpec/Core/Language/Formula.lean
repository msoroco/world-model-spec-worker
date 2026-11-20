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

  `requiredBy` and `lawful` read the body of the library's other rules rather than one named rule:
  the words "in compliance with law", "lawfully", "obey the regulations applicable to …". They reach
  the library through the composition callback under an id no node has (`RuleSet`).

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

/-- A conduct a rule's case declares its duty requires of its subject (`Rule.cases`), and that
    `requiredBy` asks about. -/
inductive Conduct
  /-- The road user at rest. -/
  | halt
  deriving Repr, DecidableEq, Inhabited

def Conduct.all : List Conduct := [.halt]
def Conduct.toString : Conduct → String
  | .halt => "halt"
instance : ToString Conduct := ⟨Conduct.toString⟩
def Conduct.ofString (s : String) : Option Conduct := Conduct.all.find? (·.toString == s)

/-- What a rule is for, declared by the rule and held by the gate to what the rule reads
    (`Rule.purposes`): the members of a `lawful` scope chosen by purpose. -/
inductive Purpose
  /-- The rule states an instruction a traffic-control device governing the road user gives it. -/
  | deviceInstruction
  /-- The rule constrains where, when or how long a road user may stand or be parked. -/
  | standingOrParking
  deriving Repr, DecidableEq, Inhabited

def Purpose.all : List Purpose := [.deviceInstruction, .standingOrParking]
def Purpose.toString : Purpose → String
  | .deviceInstruction => "device_instruction"
  | .standingOrParking => "standing_or_parking"
instance : ToString Purpose := ⟨Purpose.toString⟩
def Purpose.ofString (s : String) : Option Purpose := Purpose.all.find? (·.toString == s)

/-- The rules of the library a `lawful` ranges over. -/
inductive RuleScope
  /-- Every rule. -/
  | every
  /-- The rules whose subject binder's class names the aggregate id. -/
  | subjectClass (aggregate : String)
  /-- The rules whose subject binder's class names the aggregate id, each read with that class not
      required of the road user: their duties bind a road user of another class. -/
  | asClass (aggregate : String)
  /-- The rules that declare the purpose. -/
  | purpose (p : Purpose)
  /-- The rules whose subject binder's class names the aggregate id and that declare the purpose,
      each read with that class not required of the road user. -/
  | asClassPurpose (aggregate : String) (p : Purpose)
  deriving Repr, DecidableEq, Inhabited

mutual
  /-- A quantity. -/
  inductive Term
    | lit (q : Q) (unit : PUnit')                            -- written through a Units constructor
    | param (name : ParamName)                               -- a reading parameter
    | measure (atom : String) (args : List Arg)              -- a measured atom (Option Q or Option Nat)
    | quantity (concept : String) (args : List Arg) (params : List Term)   -- a Q-valued derived concept
    | distanceWhile (subject : String) (φ : Formula)         -- path length over which φ has held continuously
    | sinceRise (φ : Formula)                                -- time elapsed since φ last became true
    /-- The signed heading change (degrees, left positive) of `subject`, integrated from its yaw
        rate, since ψ last became true: from the latest observation at which ψ rose definitely (false
        at the observation before, true there), counted from zero at that observation. ψ turning false
        does not end it, nor does a stop; only the next definite rise of ψ starts it again. Unknown
        where no such rise is observed with ψ known at every observation since (an onset before the
        recording, or one an unknown value of ψ could hide), where an interval between consecutive
        observations from the one before the rise onwards is longer than `maxStep`, or where a yaw
        rate since the rise is missing. `maxStep` is a literal or a reading parameter, a time,
        strictly positive: the sampling standard of the integration, not a window and not a bound on
        how far back the onset may lie. -/
    | headingSince (subject : String) (maxStep : Term) (ψ : Formula)   -- the heading change of subject since ψ last became true
    | aggregate (op : AggOp) (var : String) (φ : Formula) (t : Term)   -- op of t over the road users var of the scene satisfying φ
    | add (a b : Term)
    | sub (a b : Term)
    | mul (a b : Term)
    /-- `a / b`, unknown wherever `b` is zero. Its divisor reads no measured atom: a measurement can
        be zero (a straight way's curvature, a halted road user's speed), so a bound on a ratio is
        written as a bound on a product (a ratio below a bound is the dividend below the bound
        times the divisor). -/
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
    | intent (id : IntId) (who target : Arg)                 -- the declaration current here: road user `who` intends `id` at region `target`
    | fact (id : FactId) (subjects : List Arg)               -- the source's declaration here of `id` for its subjects: road users in order, a region
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
    | count (edge : Formula) (sinceφ : Formula) (op : CmpOp) (n : Nat)   -- rising edges of `edge` since `sinceφ` became true (start of its latest run); `n` is a literal in unit count
    /-- The time φ held in the window of length `w` behind the judged observation, as the trace's
        samples show it, compared by `op` with `bound`. Observation `k` stands for the interval
        since the observation before it (the first observation for nothing): that interval counts
        as held where φ is true at `k` and the interval is at most `step`, as not held where φ is
        false at `k` and the interval is at most `step`, and as either where φ is unknown at `k` or
        the interval is longer than `step`; the part of the window before the first observation
        counts as either. True where every such reading satisfies the comparison, false where none
        does, unknown otherwise (`samplingGap`, `windowTruncated`, φ's reasons). `w`, `step` and
        `bound` are times; `step` is a literal or a reading parameter, strictly positive: the
        longest interval taken as one sample, not evidence that no observation is missing. Every
        verdict that reads it, directly or through another rule, is marked `sampled_duration`. -/
    | durationWithin (w : Term) (step : Term) (φ : Formula) (op : CmpOp) (bound : Term)
    | rises (φ : Formula)                                     -- φ here and not at the previous observation
    | definedWhen (pre φ : Formula)                           -- φ where `pre` holds; unknown (undefined) where it does not
    | derived (concept : String) (args : List Arg) (params : List Term)   -- a Boolean derived concept
    | rule (id : String) (map : List (String × String))       -- another rule complied with (not engaged counts as complied)
    | ruleApplies (id : String) (map : List (String × String)) -- another rule engaged (its binders' classes and applicability hold)
    /-- Some rule of the library requires `conduct` of road user `who` here: a case of that rule
        requiring that conduct holds (its binders' classes, its applicability and the case's
        situation), with `who` its subject and its other binders any other road users of the
        scene, pairwise distinct. The library is the run's rules that are no surrogate and use no
        `requiredBy` or `lawful`, themselves or through a rule they compose. False where no such
        case holds; unknown where the library declares no case requiring `conduct`, where the run
        declares the set incomplete, or where a case that could hold is unknown. -/
    | requiredBy (conduct : Conduct) (who : String)
    /-- Road user `who` complies here with every rule of `scope` engaged for it: each rule's
        verdict here, with `who` its subject and its other binders any other road users of the
        scene, pairwise distinct, is compliant or not applicable. The scope is drawn from the run's
        rules that are no surrogate and no permission. Never true where that is not known: unknown
        where the scope holds no rule, where the run declares the scope incomplete, or where a rule
        of the scope whose subject class `who` meets is left out because it uses `lawful` itself. -/
    | lawful (scope : RuleScope) (who : String)
    /-- The case `name` that rule `id` declares holds (its binders' classes, its applicability and
        the case's situation), its binders mapped as for `ruleApplies`: the specific situation a
        rule provides for, read where another rule's words except it. -/
    | ruleCase (id : String) (name : String) (map : List (String × String))
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
    | .headingSince _ g ψ => "kin_yaw_rate" :: measureAtom .time :: (termAtoms g ++ atoms ψ)
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
    | .durationWithin w g φ _ b => measureAtom .time :: termAtoms w ++ termAtoms g ++ atoms φ ++ termAtoms b
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
    | .headingSince _ g ψ => termParams g ++ params ψ
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
    | .durationWithin w g φ _ b => termParams w ++ termParams g ++ params φ ++ termParams b
    | .derived _ _ ps => ps.flatMap termParams
    | .existsRegion _ _ φ | .forallRegion _ _ φ | .existsDevice _ _ φ | .forallDevice _ _ φ
    | .existsUser _ φ | .forallUser _ φ => params φ
    | _ => []
end

-- The rules a formula composes, with each call's binder map, at any depth of formulas and terms.
mutual
  partial def termCompositions : Term → List (String × List (String × String))
    | .quantity _ _ ps => ps.flatMap termCompositions
    | .distanceWhile _ φ | .sinceRise φ => compositions φ
    | .headingSince _ g ψ => termCompositions g ++ compositions ψ
    | .aggregate _ _ φ t => compositions φ ++ termCompositions t
    | .add a b | .sub a b | .mul a b | .div a b => termCompositions a ++ termCompositions b
    | .neg a | .abs a => termCompositions a
    | .cond φ a b => compositions φ ++ termCompositions a ++ termCompositions b
    | _ => []
  partial def compositions : Formula → List (String × List (String × String))
    | .rule id map | .ruleApplies id map | .ruleCase id _ map => [(id, map)]
    | .atom _ _ ps | .derived _ _ ps => ps.flatMap termCompositions
    | .cmp l _ r => termCompositions l ++ termCompositions r
    | .not φ | .always φ | .eventually φ | .rises φ => compositions φ
    | .and φ ψ | .or φ ψ | .implies φ ψ | .until φ ψ | .since φ ψ | .definedWhen φ ψ => compositions φ ++ compositions ψ
    | .holdsFor _ d _ φ | .within _ d _ φ => termCompositions d ++ compositions φ
    | .untilWithin _ d _ φ ψ => termCompositions d ++ compositions φ ++ compositions ψ
    | .atLast _ d _ ψ φ => termCompositions d ++ compositions ψ ++ compositions φ
    | .count e s _ _ => compositions e ++ compositions s
    | .durationWithin w g φ _ b => termCompositions w ++ termCompositions g ++ compositions φ ++ termCompositions b
    | .existsRegion _ _ φ | .forallRegion _ _ φ | .existsDevice _ _ φ | .forallDevice _ _ φ
    | .existsUser _ φ | .forallUser _ φ => compositions φ
    | _ => []
end

/-- The rules a formula composes. -/
def composed (φ : Formula) : List String := (compositions φ).map (·.1)

-- The leaves that read the library by a set or a case (`requiredBy`, `lawful`, `ruleCase`), at any
-- depth of formulas and terms.
mutual
  partial def termRefLeaves : Term → List Formula
    | .quantity _ _ ps => ps.flatMap termRefLeaves
    | .distanceWhile _ φ | .sinceRise φ => refLeaves φ
    | .headingSince _ g ψ => termRefLeaves g ++ refLeaves ψ
    | .aggregate _ _ φ t => refLeaves φ ++ termRefLeaves t
    | .add a b | .sub a b | .mul a b | .div a b => termRefLeaves a ++ termRefLeaves b
    | .neg a | .abs a => termRefLeaves a
    | .cond φ a b => refLeaves φ ++ termRefLeaves a ++ termRefLeaves b
    | _ => []
  partial def refLeaves : Formula → List Formula
    | φ@(.requiredBy ..) | φ@(.lawful ..) | φ@(.ruleCase ..) => [φ]
    | .atom _ _ ps | .derived _ _ ps => ps.flatMap termRefLeaves
    | .cmp l _ r => termRefLeaves l ++ termRefLeaves r
    | .not φ | .always φ | .eventually φ | .rises φ => refLeaves φ
    | .and φ ψ | .or φ ψ | .implies φ ψ | .until φ ψ | .since φ ψ | .definedWhen φ ψ => refLeaves φ ++ refLeaves ψ
    | .holdsFor _ d _ φ | .within _ d _ φ => termRefLeaves d ++ refLeaves φ
    | .untilWithin _ d _ φ ψ => termRefLeaves d ++ refLeaves φ ++ refLeaves ψ
    | .atLast _ d _ ψ φ => termRefLeaves d ++ refLeaves ψ ++ refLeaves φ
    | .count e s _ _ => refLeaves e ++ refLeaves s
    | .durationWithin w g φ _ b => termRefLeaves w ++ termRefLeaves g ++ refLeaves φ ++ termRefLeaves b
    | .existsRegion _ _ φ | .forallRegion _ _ φ | .existsDevice _ _ φ | .forallDevice _ _ φ
    | .existsUser _ φ | .forallUser _ φ => refLeaves φ
    | _ => []
end

-- Whether a formula reads `durationWithin`, at any depth of formulas and terms.
mutual
  partial def termReadsDuration : Term → Bool
    | .quantity _ _ ps => ps.any termReadsDuration
    | .distanceWhile _ φ | .sinceRise φ => readsDuration φ
    | .headingSince _ g ψ => termReadsDuration g || readsDuration ψ
    | .aggregate _ _ φ t => readsDuration φ || termReadsDuration t
    | .add a b | .sub a b | .mul a b | .div a b => termReadsDuration a || termReadsDuration b
    | .neg a | .abs a => termReadsDuration a
    | .cond φ a b => readsDuration φ || termReadsDuration a || termReadsDuration b
    | _ => false
  partial def readsDuration : Formula → Bool
    | .durationWithin .. => true
    | .atom _ _ ps | .derived _ _ ps => ps.any termReadsDuration
    | .cmp l _ r => termReadsDuration l || termReadsDuration r
    | .not φ | .always φ | .eventually φ | .rises φ => readsDuration φ
    | .and φ ψ | .or φ ψ | .implies φ ψ | .until φ ψ | .since φ ψ | .definedWhen φ ψ | .count φ ψ _ _ =>
      readsDuration φ || readsDuration ψ
    | .holdsFor _ d _ φ | .within _ d _ φ => termReadsDuration d || readsDuration φ
    | .untilWithin _ d _ φ ψ | .atLast _ d _ φ ψ => termReadsDuration d || readsDuration φ || readsDuration ψ
    | .existsRegion _ _ φ | .forallRegion _ _ φ | .existsDevice _ _ φ | .forallDevice _ _ φ
    | .existsUser _ φ | .forallUser _ φ => readsDuration φ
    | _ => false
end

/-- The rule-set operators a formula reads (`requiredBy`, `lawful`). -/
def ruleSets (φ : Formula) : List Formula := (refLeaves φ).filter fun | .ruleCase .. => false | _ => true
/-- The rule cases a formula reads, as (rule, case). -/
def caseRefs (φ : Formula) : List (String × String) := (refLeaves φ).filterMap fun | .ruleCase id n _ => some (id, n) | _ => none

-- Numeric literals other than zero, with their units, a `count`'s bound among them in unit count:
-- what the gate holds against the node's declared parameters (a magnitude belongs in the reading,
-- not in a rule).
mutual
  partial def termLiterals : Term → List (Q × PUnit')
    | .lit q u => if Q.isZero q then [] else [(q, u)]
    | .quantity _ _ ps => ps.flatMap termLiterals
    | .distanceWhile _ φ => literals φ
    | .sinceRise φ => literals φ
    | .headingSince _ g ψ => termLiterals g ++ literals ψ
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
    | .count e s _ n => literals e ++ literals s ++ (if n = 0 then [] else [(Q.ofInt (Int.ofNat n), .count)])
    | .durationWithin w g φ _ b => termLiterals w ++ termLiterals g ++ literals φ ++ termLiterals b
    | .derived _ _ ps => ps.flatMap termLiterals
    | .existsRegion _ _ φ | .forallRegion _ _ φ | .existsDevice _ _ φ | .forallDevice _ _ φ
    | .existsUser _ φ | .forallUser _ φ => literals φ
    | _ => []
end

/-- A leaf is a subformula that reads the world or another rule: an atom, a comparison, an
    assumption, a declared intention or fact, a derived concept or a composition. Leaves are
    numbered in traversal order. -/
def isLeaf : Formula → Bool
  | .atom .. | .cmp .. | .asm _ | .intent .. | .fact .. | .derived .. | .rule .. | .ruleApplies .. | .requiredBy .. | .lawful .. | .ruleCase .. => true
  | _ => false

/-- The leaves in traversal order, as a description each. -/
partial def leaves : Formula → List String
  | .atom n args _ => [s!"atom {n} {repr args}"]
  | .cmp l _ r => [s!"cmp {repr l} {repr r}"]
  | .asm id => [s!"asm {id}"]
  | .intent id who target => [s!"intent {id} {repr who} {repr target}"]
  | .fact id xs => [s!"fact {id} {repr xs}"]
  | .derived n args _ => [s!"derived {n} {repr args}"]
  | .rule id _ => [s!"rule {id}"]
  | .ruleApplies id _ => [s!"ruleApplies {id}"]
  | .requiredBy k who => [s!"requiredBy {k} {who}"]
  | .lawful s who => [s!"lawful {repr s} {who}"]
  | .ruleCase id n _ => [s!"ruleCase {id} {n}"]
  | .not φ | .always φ | .eventually φ | .rises φ => leaves φ
  | .and φ ψ | .or φ ψ | .implies φ ψ | .until φ ψ | .since φ ψ | .definedWhen φ ψ => leaves φ ++ leaves ψ
  | .holdsFor _ _ _ φ | .within _ _ _ φ => leaves φ
  | .untilWithin _ _ _ φ ψ => leaves φ ++ leaves ψ
  | .atLast _ _ _ ψ φ => leaves ψ ++ leaves φ
  | .count e s _ _ => leaves e ++ leaves s
  | .durationWithin _ _ φ _ _ => leaves φ
  | .existsRegion _ _ φ | .forallRegion _ _ φ | .existsDevice _ _ φ | .forallDevice _ _ φ
  | .existsUser _ φ | .forallUser _ φ => leaves φ
  | _ => []

def leafCount (φ : Formula) : Nat := (leaves φ).length

/-- The formula with its `k`-th leaf (traversal order) replaced by `r`, and the number of leaves
    in the formula. A subformula whose leaves all precede or follow the `k`-th is returned as it is. -/
partial def replaceLeafAux (k : Nat) (r : Formula) : Formula → Formula × Nat
  | φ@(.atom ..) | φ@(.cmp ..) | φ@(.asm _) | φ@(.intent ..) | φ@(.fact ..) | φ@(.derived ..) | φ@(.rule ..) | φ@(.ruleApplies ..)
  | φ@(.requiredBy ..) | φ@(.lawful ..) | φ@(.ruleCase ..) =>
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
  | .durationWithin w g φ op b => let (φ', n) := replaceLeafAux k r φ; (.durationWithin w g φ' op b, n)
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

/-- A fact the trace declares and a formula reads: an assumption, a declared intention or a
    declared fact, by its id. -/
inductive Declared
  | asm (id : AsmId)
  | int (id : IntId)
  | fact (id : FactId)
  deriving Repr, DecidableEq, Inhabited

-- The assumptions, declared intentions and declared facts a formula reads, at any depth of
-- formulas and terms.
mutual
  partial def termDeclared : Term → List Declared
    | .quantity _ _ ps => ps.flatMap termDeclared
    | .distanceWhile _ φ | .sinceRise φ => declared φ
    | .headingSince _ g ψ => termDeclared g ++ declared ψ
    | .aggregate _ _ φ t => declared φ ++ termDeclared t
    | .add a b | .sub a b | .mul a b | .div a b => termDeclared a ++ termDeclared b
    | .neg a | .abs a => termDeclared a
    | .cond φ a b => declared φ ++ termDeclared a ++ termDeclared b
    | _ => []
  partial def declared : Formula → List Declared
    | .asm id => [.asm id]
    | .intent id _ _ => [.int id]
    | .fact id _ => [.fact id]
    | .atom _ _ ps | .derived _ _ ps => ps.flatMap termDeclared
    | .cmp l _ r => termDeclared l ++ termDeclared r
    | .not φ | .always φ | .eventually φ | .rises φ => declared φ
    | .and φ ψ | .or φ ψ | .implies φ ψ | .until φ ψ | .since φ ψ | .definedWhen φ ψ => declared φ ++ declared ψ
    | .holdsFor _ d _ φ | .within _ d _ φ => termDeclared d ++ declared φ
    | .untilWithin _ d _ φ ψ => termDeclared d ++ declared φ ++ declared ψ
    | .atLast _ d _ ψ φ => termDeclared d ++ declared ψ ++ declared φ
    | .count e s _ _ => declared e ++ declared s
    | .durationWithin w g φ _ b => termDeclared w ++ termDeclared g ++ declared φ ++ termDeclared b
    | .existsRegion _ _ φ | .forallRegion _ _ φ | .existsDevice _ _ φ | .forallDevice _ _ φ
    | .existsUser _ φ | .forallUser _ φ => declared φ
    | _ => []
end

/-- The assumptions a formula reads. -/
def assumptions (φ : Formula) : List AsmId := (declared φ).filterMap fun | .asm a => some a | _ => none
/-- The declared intentions a formula reads. -/
def intentions (φ : Formula) : List IntId := (declared φ).filterMap fun | .int i => some i | _ => none
/-- The declared facts a formula reads. -/
def facts (φ : Formula) : List FactId := (declared φ).filterMap fun | .fact f => some f | _ => none

-- The aggregate ids a formula names (`ru_aggregate x "<definition id>::<term>"`), at any depth of
-- formulas and terms, for the reading check.
mutual
  partial def termAggregateIds : Term → List String
    | .quantity _ _ ps => ps.flatMap termAggregateIds
    | .distanceWhile _ φ | .sinceRise φ => aggregateIds φ
    | .headingSince _ g ψ => termAggregateIds g ++ aggregateIds ψ
    | .aggregate _ _ φ t => aggregateIds φ ++ termAggregateIds t
    | .add a b | .sub a b | .mul a b | .div a b => termAggregateIds a ++ termAggregateIds b
    | .neg a | .abs a => termAggregateIds a
    | .cond φ a b => aggregateIds φ ++ termAggregateIds a ++ termAggregateIds b
    | _ => []
  partial def aggregateIds : Formula → List String
    | .atom "ru_aggregate" [_, .lit w] ps => w :: ps.flatMap termAggregateIds
    | .atom _ _ ps | .derived _ _ ps => ps.flatMap termAggregateIds
    | .cmp l _ r => termAggregateIds l ++ termAggregateIds r
    | .not φ | .always φ | .eventually φ | .rises φ => aggregateIds φ
    | .and φ ψ | .or φ ψ | .implies φ ψ | .until φ ψ | .since φ ψ | .definedWhen φ ψ => aggregateIds φ ++ aggregateIds ψ
    | .holdsFor _ d _ φ | .within _ d _ φ => termAggregateIds d ++ aggregateIds φ
    | .untilWithin _ d _ φ ψ => termAggregateIds d ++ aggregateIds φ ++ aggregateIds ψ
    | .atLast _ d _ ψ φ => termAggregateIds d ++ aggregateIds ψ ++ aggregateIds φ
    | .count e s _ _ => aggregateIds e ++ aggregateIds s
    | .durationWithin w g φ _ b => termAggregateIds w ++ termAggregateIds g ++ aggregateIds φ ++ termAggregateIds b
    | .existsRegion _ _ φ | .forallRegion _ _ φ | .existsDevice _ _ φ | .forallDevice _ _ φ
    | .existsUser _ φ | .forallUser _ φ => aggregateIds φ
    | _ => []
end

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
  | .durationWithin w g φ op b => .durationWithin w g (elimCond φ) op b
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

namespace RuleSet
/-- The composition id under which `requiredBy` and `lawful` reach the library through the
    composition callback, with `who` as the one mapped variable. No node id begins with `#`. -/
def requiredId (k : Conduct) : String := "#requiredBy:" ++ k.toString
def lawfulId : RuleScope → String
  | .every => "#lawful:every"
  | .subjectClass a => "#lawful:class:" ++ a
  | .asClass a => "#lawful:as:" ++ a
  | .purpose p => "#lawful:purpose:" ++ p.toString
  | .asClassPurpose a p => "#lawful:aspurpose:" ++ p.toString ++ ":" ++ a
/-- The operator a composition id names, as the leaf with `who` for its road user. -/
def ofId (id : String) : Option Formula :=
  match Conduct.all.find? (requiredId · == id) with
  | some k => some (.requiredBy k "who")
  | none =>
    if id == lawfulId .every then some (.lawful .every "who")
    else if id.startsWith "#lawful:class:" then some (.lawful (.subjectClass (id.drop 14).toString) "who")
    else if id.startsWith "#lawful:as:" then some (.lawful (.asClass (id.drop 11).toString) "who")
    else if id.startsWith "#lawful:purpose:" then (Purpose.ofString (id.drop 16).toString).map fun p => .lawful (.purpose p) "who"
    else if id.startsWith "#lawful:aspurpose:" then
      Purpose.all.findSome? fun p =>
        let pre := "#lawful:aspurpose:" ++ p.toString ++ ":"
        if id.startsWith pre then some (.lawful (.asClassPurpose (id.drop pre.length).toString p) "who") else none
    else none
/-- The composition id under which `ruleCase id name` reaches its rule's case. -/
def caseId (id name : String) : String := s!"#case:{id}:{name}"
/-- The rule and the case a case id names. -/
def ofCaseId (cid : String) : Option (String × String) :=
  if cid.startsWith "#case:" then
    match ((cid.drop 6).toString.splitOn ":") with
    | [id, name] => some (id, name)
    | _ => none
  else none
/-- The id of a rule-set leaf; none for any other formula. -/
def idOf : Formula → Option String
  | .requiredBy k _ => some (requiredId k)
  | .lawful s _ => some (lawfulId s)
  | _ => none
end RuleSet

end TrafficSpec
