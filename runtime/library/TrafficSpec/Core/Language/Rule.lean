/-
  TrafficSpec.Core.Language.Rule
  What a specification is: binders with class formulas, an applicability and an obligation, and
  the declarations a reviewer needs (parameters, assumptions, declared intentions, declared facts,
  operationalizations, residues, narrowings, the rules it composes, the surrogate flag, the
  approved abstractions it uses).

  A residue is a span of the text the rule does not capture at all; the plan declares it and the
  rule repeats it verbatim. A narrowing is a reading the coder chose on a span the plan does
  carry, stated here so the review judges the rule as it is: the span it names and why. The
  coder may add narrowings and never residues.

  Applicability and obligation are two formulas because a rule whose situation never arises is
  not compliant, it is not engaged: `notApplicable` is a verdict of its own, the witness check can
  demand a scenario for it, and a monitor reads the applicability as the trigger and the
  obligation as what to verify once triggered.

  A case is a situation the rule itself provides for, under its applicability (`RuleCase`): one in
  which its duty requires a conduct of the subject (`requires`), read by another rule's
  `Formula.requiredBy` ("in compliance with law"), or one in which it permits an act (`permits`),
  read by another rule's `Formula.ruleCase` ("except as otherwise provided in …"). A permission
  rule (`permission`) states only permitted cases: its obligation is `tt`, so it is never violated.

  A surrogate rule (the whole duty is an operationalized standard) is monitored like any other,
  but its verdicts are evidence about the standard, never the law's own verdict; the flag is what
  the monitor and the export propagate so the two are never summed.

  An approved abstraction is a kind of word the ontology's catalogue lets a rule omit across the
  corpus; `abstractions` names, by catalogue id, those the rule uses. A rule that uses one is
  partial coverage: its verdicts check the conduct it states, not full compliance with the law's
  words. A verdict that reads such a rule, through a composition or a rule-set operator, is partial
  coverage too, and the monitor and the export carry the ids on every verdict.

  This file holds the declarations only and imports no evaluator: a rule file that imports it
  can state a rule but cannot read a scene, evaluate a formula or build evidence. Evaluation and
  the static check are in RuleEval.lean, which nothing under Rules/ may import.
-/
import TrafficSpec.Core.Language.Formula
import TrafficSpec.Core.Foundations.Unknown

namespace TrafficSpec

/-- A binder: a variable and the class formula (over `ru_*` atoms and class-level derived
    concepts) a track must satisfy to be bound to it. The subject comes first. -/
structure Binder where
  name : String
  cls : Formula
  deriving Repr, Inhabited

/-- A reading chosen on a span the record carries, declared where it is made: the span (a
    segmentation id for a rule, a run of the contract's words for a concept) and what the formulas
    state more narrowly than the words. `kind` is `reading` where the words leave the choice open,
    `observable_reading` where a word with no observable counterpart is read through the conduct
    or the feature it refers to, `no_atom` or `no_operator` where the vocabulary or the language
    cannot state the words — a declaration the gate returns for a gap, never a reading the rule
    stands on. -/
structure Narrowing where
  span : String
  why : String
  kind : String := "reading"
  deriving Repr, Inhabited, DecidableEq

/-- What a case states: that the duty requires a conduct of the subject there, or that the rule
    permits an act there. -/
inductive CaseKind
  | requires (conduct : Conduct)
  | permits
  deriving Repr, DecidableEq, Inhabited

/-- A case the rule provides for: it holds at an instant at which the binders' classes, the
    rule's applicability and `when` hold: a case never exceeds the rule's applicability.
    `shown` is the formula, over the binders, of the subject showing the conduct (`requires`) or
    the permitted act (`permits`): the gate holds the case to the rule's own verdicts through it.
    Neither formula reads a rule-set operator. -/
structure RuleCase where
  name : String
  kind : CaseKind
  shown : Formula
  when : Formula := .tt
  deriving Repr, Inhabited

structure Rule where
  id : String                                   -- the node id, derived from the law id
  laws : List String                            -- the corpus ids this rule formalizes
  binders : List Binder
  applicability : Formula
  obligation : Formula
  cases : List RuleCase := []                       -- the situations it provides for, under its applicability
  permission : Bool := false                    -- it only permits: its obligation is `tt`
  purposes : List Purpose := []                 -- what it is for, the members of a `lawful` scope by purpose
  assumptions : List AsmId := []
  intentions : List IntId := []                 -- the declared intentions its formulas read
  facts : List FactId := []                     -- the declared facts its formulas read
  operationalizations : List Operationalization := []
  residues : List String := []                  -- what the text says and the rule does not capture
  narrowings : List Narrowing := []             -- readings the coder chose on carried spans
  surrogate : Bool := false
  abstractions : List String := []              -- the approved abstractions it uses: partial coverage
  deriving Repr, Inhabited

inductive Verdict
  | violated
  | compliant
  | notApplicable
  | unknown (why : List UnknownReason)
  deriving Repr, DecidableEq, Inhabited

namespace Verdict
def tag : Verdict → String
  | .violated => "violated"
  | .compliant => "compliant"
  | .notApplicable => "not_applicable"
  | .unknown _ => "unknown"
def reasons : Verdict → List UnknownReason
  | .unknown w => w
  | _ => []
instance : ToString Verdict := ⟨tag⟩
end Verdict

/-- Kleene combination of the two formulas: not engaged ↦ notApplicable, engaged and the
    obligation decided ↦ compliant/violated, anything undecided ↦ unknown with its reasons. -/
def verdictAt (app obl : R) : Verdict :=
  match app.v with
  | .f => .notApplicable
  | .u => .unknown app.why
  | .t =>
    match obl.v with
    | .t => .compliant
    | .f => .violated
    | .u => .unknown obl.why

theorem verdictAt_notApplicable (app obl : R) (h : app.v = .f) : verdictAt app obl = .notApplicable := by
  unfold verdictAt; rw [h]
theorem verdictAt_violated (app obl : R) (ha : app.v = .t) (ho : obl.v = .f) : verdictAt app obl = .violated := by
  unfold verdictAt; rw [ha, ho]
theorem verdictAt_compliant (app obl : R) (ha : app.v = .t) (ho : obl.v = .t) : verdictAt app obl = .compliant := by
  unfold verdictAt; rw [ha, ho]

namespace Rule
/-- The formulas a rule consists of, class formulas first, its cases last. -/
def formulas (r : Rule) : List Formula :=
  r.binders.map (·.cls) ++ [r.applicability, r.obligation] ++ r.cases.flatMap fun c => [c.shown, c.when]
/-- Atom, primitive and concept names the rule reads. -/
def atoms (r : Rule) : List String := (r.formulas.flatMap Formula.atoms).eraseDups
/-- Reading parameters the rule names. -/
def params (r : Rule) : List ParamName := (r.formulas.flatMap Formula.params).eraseDups
/-- Rules the rule composes. -/
def composes (r : Rule) : List String := (r.formulas.flatMap Formula.composed).eraseDups
/-- Assumptions the formulas read. -/
def usedAssumptions (r : Rule) : List AsmId := (r.formulas.flatMap Formula.assumptions).eraseDups
/-- Declared intentions the formulas read. -/
def usedIntentions (r : Rule) : List IntId := (r.formulas.flatMap Formula.intentions).eraseDups
/-- Declared facts the formulas read. -/
def usedFacts (r : Rule) : List FactId := (r.formulas.flatMap Formula.facts).eraseDups
def binderNames (r : Rule) : List String := r.binders.map (·.name)
def subject (r : Rule) : Option String := r.binders.head?.map (·.name)

/-- The rule and, transitively, the rules it composes (each once). -/
def closure (rules : List Rule) (r : Rule) : List Rule :=
  let rec go (fuel : Nat) (seen : List String) (todo : List Rule) : List Rule :=
    match fuel, todo with
    | 0, _ | _, [] => []
    | fuel + 1, x :: rest =>
      let next := x.composes.filterMap fun id =>
        if seen.contains id then none else rules.find? (·.id == id)
      x :: go fuel (seen ++ next.map (·.id)) (rest ++ next)
  go (rules.length + 1) [r.id] [r]

/-- Whether the rule reads a declared intention, in its own formulas or through a rule it
    composes at any depth. -/
def readsIntention (rules : List Rule) (r : Rule) : Bool :=
  (closure rules r).any fun x => !x.usedIntentions.isEmpty
end Rule

end TrafficSpec
