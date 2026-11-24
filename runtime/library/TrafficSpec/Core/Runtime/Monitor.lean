/-
  TrafficSpec.Core.Runtime.Monitor
  The report: one row per rule and grounding, with support, episode verdict, timeline, the
  histogram of unknown reasons, residues, the surrogate flag and the approved abstractions the
  verdict rests on; rendered as tab-separated text (the gate's contract) and as JSON lines (the
  diagnosis tooling's).

  It composes everything below it and owns nothing else. The JSON lines are a contract with the
  label check's scoring and the evaluation tooling; changing a line here is a cross-artifact change.
  Surrogate rows never enter the concrete tallies. A rule whose verdict rests on an approved
  abstraction (its own, or one of a rule it composes or a rule-set operator it reads ranges over:
  `RuleSet.abstractionsOf`) is partial coverage, of kind `abstracted`: each of its lines names the
  abstractions, and its verdicts are tallied apart from the concrete ones, never as full compliance
  with the law. (`partial` in a summary counts rules the manifest only partly supports.)
  A rule whose verdict rests on `durationWithin` (its own formulas, with their concept calls
  expanded, or those of a rule it reads: `RuleSet.sampledDurationOf`) is marked `sampled_duration`
  on every line: its verdicts judge the time the trace's samples show, not a time proved between
  them. The mark is no approved abstraction and moves no tally; a summary counts the marked rules.

  Text format (tab-separated; one record per line):
    SOURCE   source  instants=N  gap=<seconds>
    RULE     rule  concrete|abstracted|surrogate|permission  support  absent-ids(,)  groundings=N  live=bool  v=N c=N na=N u=N  abstractions=ids(,)  sampled_duration=bool
    GROUND   rule  grounding  episode  abstractions=ids(,)  sampled_duration=bool
    TL       rule  grounding  t_from  t_to  verdict            (runs of equal verdict, ms timestamps)
    UNK      rule  grounding  reason  count
    RESIDUE  rule  text
    SUMMARY  concrete|abstracted|surrogate  rules=N supported=N partial=N unsupported=N live=N v=N c=N na=N u=N sampled_duration=N
-/
import Lean.Data.Json
import TrafficSpec.Core.Runtime.Grounding
import TrafficSpec.Core.Runtime.Manifest

namespace TrafficSpec
namespace Monitor
open Grounding

structure Row where
  rule : String
  surrogate : Bool
  support : Support
  grounding : Grounding
  episode : Verdict
  timeline : Array (Timestamp × Verdict)
  unknowns : List (String × Nat)
  residues : List String
  abstractions : List String := []   -- the approved abstractions its verdict rests on
  sampledDuration : Bool := false    -- its verdict rests on a duration read from the samples
  deriving Repr, Inhabited

structure RuleLine where
  rule : String
  surrogate : Bool
  permission : Bool := false     -- never violated: its verdicts are counted in no total
  abstractions : List String := []   -- the approved abstractions its verdicts rest on: partial coverage
  sampledDuration : Bool := false    -- its verdicts rest on a duration read from the samples
  support : Support
  groundings : Nat
  live : Bool
  violated : Nat
  compliant : Nat
  notApplicable : Nat
  unknown : Nat
  deriving Repr, Inhabited

structure Report where
  source : String
  instants : Nat
  gap : Q
  rules : List RuleLine
  rows : List Row
  deriving Repr, Inhabited

def histogram (tl : List Verdict) : List (String × Nat) :=
  let tags := tl.flatMap fun v => (v.reasons.map UnknownReason.tag).eraseDups
  tags.eraseDups.map fun t => (t, tags.count t)

def countVerdict (vs : List Verdict) (p : Verdict → Bool) : Nat := (vs.filter p).length
def isUnknown : Verdict → Bool | .unknown _ => true | _ => false

/-- Evaluate a rule set over one trace as the source would have produced it, the rules' concept
    calls expanded over `cs`. Unsupported rules are reported without groundings: nothing they
    say could be decided. A permission is never violated: its line counts no episode as violated or
    compliant, and the summaries leave it out. Each line and row carries the approved abstractions
    its verdicts rest on (`RuleSet.abstractionsOf` over the registered rules) and whether they rest
    on a sampled duration (`RuleSet.sampledDurationOf`). A trace the admission rejects is not evaluated: its defects are returned. -/
def check (rules : List Rule) (τ : Trace) (ρ : Reading) (m : Manifest) (cs : List Concept := [])
    (incomplete : List String := []) : Except (List String) Report := do
  let rules := rules.map (Concept.expandRule cs)
  let S ← (Setup.admit rules (maskTrace m τ) ρ m.reidGap).map fun S => { S with incomplete := incomplete }
  let per := rules.map fun r =>
    let sup := support rules r m
    let abs := RuleSet.abstractionsOf rules r
    let sd := RuleSet.sampledDurationOf rules r
    match sup with
    | .unsupported _ => ({ rule := r.id, surrogate := r.surrogate, permission := r.permission, abstractions := abs, sampledDuration := sd, support := sup, groundings := 0, live := false,
                           violated := 0, compliant := 0, notApplicable := 0, unknown := 0 : RuleLine }, ([] : List Row))
    | _ =>
      let evaluated : List (Grounding × Grounding.Timeline × Verdict) := Grounding.check S r
      let rows : List Row := evaluated.map fun (e : Grounding × Grounding.Timeline × Verdict) =>
        let g := e.1; let tl := e.2.1; let ep := e.2.2
        let vs : List Verdict := tl.verdicts.toList.map Prod.snd
        { rule := r.id, surrogate := r.surrogate, support := sup, grounding := g, episode := ep,
          timeline := tl.verdicts, unknowns := histogram vs, residues := r.residues, abstractions := abs, sampledDuration := sd }
      let eps : List Verdict := rows.map Row.episode
      ({ rule := r.id, surrogate := r.surrogate, permission := r.permission, abstractions := abs, sampledDuration := sd, support := sup, groundings := rows.length,
         live := evaluated.any (fun e => e.2.1.live),
         violated := if r.permission then 0 else countVerdict eps (· == Verdict.violated),
         compliant := if r.permission then 0 else countVerdict eps (· == Verdict.compliant),
         notApplicable := countVerdict eps (· == Verdict.notApplicable), unknown := countVerdict eps isUnknown : RuleLine }, rows)
  pure { source := m.source, instants := τ.length, gap := m.reidGap, rules := per.map (·.1), rows := per.flatMap (·.2) }

-- ---------------------------------------------------------------------------------------------
-- Text
-- ---------------------------------------------------------------------------------------------
def qText (q : Q) : String :=
  let g := Nat.gcd q.num.natAbs q.den
  let g := if g == 0 then 1 else g
  let n := q.num / (Int.ofNat g)
  let d := q.den / g
  if d == 1 then toString n else s!"{n}/{d}"
def tabs (xs : List String) : String := String.intercalate "\t" xs
def ids (xs : List String) : String := String.intercalate "," xs

/-- The tally a rule line enters: a permission none; a surrogate its own; a rule whose verdicts rest
    on an approved abstraction `abstracted`; every other rule `concrete`. -/
def kind (l : RuleLine) : String :=
  if l.permission then "permission" else if l.surrogate then "surrogate"
  else if !l.abstractions.isEmpty then "abstracted" else "concrete"

/-- Runs of equal verdicts: (from, to, verdict). -/
def runs (tl : Array (Timestamp × Verdict)) : List (Timestamp × Timestamp × Verdict) :=
  tl.toList.foldl (fun acc (t, v) =>
    match acc with
    | (a, _, v') :: rest => if v' == v then (a, t, v) :: rest else (t, t, v) :: acc
    | [] => [(t, t, v)]) [] |>.reverse

def rowLines (row : Row) : List String :=
  let g := row.grounding.render
  [tabs ["GROUND", row.rule, g, row.episode.tag, s!"abstractions={ids row.abstractions}", s!"sampled_duration={row.sampledDuration}"]] ++
  ((runs row.timeline).map fun (a, b', v) => tabs ["TL", row.rule, g, toString a, toString b', v.tag]) ++
  (row.unknowns.map fun (t, n) => tabs ["UNK", row.rule, g, t, toString n])

def ruleLine (l : RuleLine) : String :=
  tabs ["RULE", l.rule, kind l, l.support.tag, String.intercalate "," l.support.absent,
        s!"groundings={l.groundings}", s!"live={l.live}",
        s!"v={l.violated}", s!"c={l.compliant}", s!"na={l.notApplicable}", s!"u={l.unknown}",
        s!"abstractions={ids l.abstractions}", s!"sampled_duration={l.sampledDuration}"]

/-- The tally of the rule lines of one kind (`concrete`, `abstracted` or `surrogate`). -/
def summaryLine (k : String) (ls : List RuleLine) : String :=
  let ls := ls.filter fun l => kind l == k
  let n (p : RuleLine → Bool) := (ls.filter p).length
  let sum (f : RuleLine → Nat) := ls.foldl (fun a l => a + f l) 0
  tabs ["SUMMARY", k, s!"rules={ls.length}",
        s!"supported={n (·.support == .supported)}",
        s!"partial={n fun l => match l.support with | .partially _ => true | _ => false}",
        s!"unsupported={n fun l => match l.support with | .unsupported _ => true | _ => false}",
        s!"live={n (·.live)}", s!"v={sum (·.violated)}", s!"c={sum (·.compliant)}",
        s!"na={sum (·.notApplicable)}", s!"u={sum (·.unknown)}", s!"sampled_duration={n (·.sampledDuration)}"]

def renderText (rep : Report) : String :=
  let header := tabs ["SOURCE", rep.source, s!"instants={rep.instants}", s!"gap={qText rep.gap}"]
  let ruleBlocks := rep.rules.flatMap fun l =>
    let residues : List String := ((rep.rows.find? (·.rule == l.rule)).map (·.residues)).getD []
    [ruleLine l] ++
    (rep.rows.filter (·.rule == l.rule)).flatMap rowLines ++
    residues.map fun t => tabs ["RESIDUE", l.rule, t]
  String.intercalate "\n" ([header] ++ ruleBlocks ++ ["concrete", "abstracted", "surrogate"].map (summaryLine · rep.rules)) ++ "\n"

-- ---------------------------------------------------------------------------------------------
-- JSON lines
-- ---------------------------------------------------------------------------------------------
open Lean in
def verdictJson (v : Verdict) : Json :=
  Json.mkObj [("verdict", v.tag), ("reasons", Json.arr (v.reasons.map fun r => Json.str r.tag).toArray)]

open Lean in
def rowJson (row : Row) : Json :=
  Json.mkObj [
    ("kind", "grounding"), ("rule", row.rule), ("surrogate", row.surrogate), ("support", row.support.tag),
    ("abstractions", Json.arr (row.abstractions.map Json.str).toArray), ("partial_coverage", !row.abstractions.isEmpty),
    ("sampled_duration", row.sampledDuration),
    ("grounding", Json.mkObj (row.grounding.assign.map fun (n, t) => (n, Json.num t))),
    ("episode", verdictJson row.episode),
    ("timeline", Json.arr ((runs row.timeline).map fun (a, b', v) =>
        Json.mkObj [("from", Json.num a), ("to", Json.num b'), ("verdict", v.tag)]).toArray),
    ("unknowns", Json.mkObj (row.unknowns.map fun (t, n) => (t, Json.num n))),
    ("residues", Json.arr (row.residues.map Json.str).toArray)]

open Lean in
def ruleJson (l : RuleLine) : Json :=
  Json.mkObj [
    ("kind", "rule"), ("rule", l.rule), ("surrogate", l.surrogate), ("permission", l.permission), ("support", l.support.tag),
    ("abstractions", Json.arr (l.abstractions.map Json.str).toArray), ("partial_coverage", !l.abstractions.isEmpty),
    ("sampled_duration", l.sampledDuration),
    ("absent", Json.arr (l.support.absent.map Json.str).toArray), ("groundings", Json.num l.groundings),
    ("live", l.live), ("violated", Json.num l.violated), ("compliant", Json.num l.compliant),
    ("not_applicable", Json.num l.notApplicable), ("unknown", Json.num l.unknown)]

open Lean in
def renderJsonLines (rep : Report) : String :=
  let header := Json.mkObj [("kind", "source"), ("source", rep.source), ("instants", Json.num rep.instants), ("gap", qText rep.gap)]
  String.intercalate "\n" ((header :: rep.rules.map ruleJson ++ rep.rows.map rowJson).map (·.compress)) ++ "\n"

end Monitor
end TrafficSpec
