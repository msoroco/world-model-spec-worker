/-
  TrafficSpec.Core.Runtime.Grounding
  Which assignments of tracks to binders exist over a trace, how a broken track is followed, and
  the per-grounding timeline of verdicts.

  A track is a source's identity, not an object's. When a tracker breaks and the adapter claims a
  continuation (`Scene.links`, old ↦ new), the trace is rewritten once to canonical identities
  when the break is shorter than the manifest's re-identification gap; the instants inside the gap
  are unknown (identityGap), never a fresh party. A binder whose track is not present at an
  instant outside any gap leaves the rule not engaged there: the other party has left the scene.

  Groundings are tuples of distinct candidates that are co-present at some instant; each
  grounding evaluates the rule once over the whole trace, and formulas that depend on a subset of
  the binders are shared across the groundings that agree on that subset.

  Rules never import this file: a rule that could see the census of tracks could special-case it.
-/
import TrafficSpec.Core.Language.RuleEval

namespace TrafficSpec
namespace Grounding
open Semantics

/-- An assignment of canonical tracks to binder names. -/
structure Grounding where
  assign : List (String × TrackId)
  deriving Repr, DecidableEq, Inhabited

def Grounding.render (g : Grounding) : String :=
  String.intercalate "," (g.assign.map fun (n, t) => s!"{n}={t}")
def Grounding.binding (g : Grounding) : Binding := ⟨g.assign.map fun (n, t) => (n, Val.track t)⟩

-- ---------------------------------------------------------------------------------------------
-- Identity: canonical tracks through accepted links, applied to the trace once
-- ---------------------------------------------------------------------------------------------
def firstSeen (τ : Array Scene) (t : TrackId) : Option Nat :=
  (List.range τ.size).find? fun i => τ[i]!.tracks.contains t
def lastSeen (τ : Array Scene) (t : TrackId) : Option Nat :=
  ((List.range τ.size).reverse).find? fun i => τ[i]!.tracks.contains t

/-- A link old ↦ new is accepted when `new` first appears after `old` was last seen, within `gap`. -/
def acceptedLinks (τ : Array Scene) (gap : Q) : List (TrackId × TrackId) :=
  (τ.toList.flatMap (·.links)).eraseDups.filter fun (old, new) =>
    match lastSeen τ old, firstSeen τ new with
    | some lo, some fn =>
      fn > lo && Q.le (Q.sub (Time.ofTimestamp τ[fn]!.t) (Time.ofTimestamp τ[lo]!.t)) gap
    | _, _ => false

/-- The canonical (root) track of every track, following accepted links backwards. -/
def canonMap (τ : Array Scene) (gap : Q) : List (TrackId × TrackId) :=
  let links := acceptedLinks τ gap
  let tracks := (τ.toList.flatMap (·.tracks)).eraseDups
  let rec root (t : TrackId) (fuel : Nat) : TrackId :=
    match fuel with
    | 0 => t
    | fuel + 1 =>
      match links.find? (·.2 == t) with
      | some (old, _) => root old fuel
      | none => t
  tracks.map fun t => (t, root t (links.length + 1))

def canon (cm : List (TrackId × TrackId)) (t : TrackId) : TrackId :=
  ((cm.find? (·.1 == t)).map (·.2)).getD t

/-- The scene with every track id replaced by its canonical identity. -/
def canonicalScene (cm : List (TrackId × TrackId)) (s : Scene) : Scene :=
  let c := canon cm
  { s with
    subject := s.subject.map c
    users := s.users.map fun u => { u with track := c u.track }
    devices := s.devices.map fun d => { d with onTrack := d.onTrack.map c }
    occupancyObserved := s.occupancyObserved.map c
    occupies := s.occupies.map fun (t, r) => (c t, r)
    relations := s.relations.map fun m => { m with a := c m.a, b := c m.b } }

-- ---------------------------------------------------------------------------------------------
-- Setup: the canonical, indexed trace and the rule set
-- ---------------------------------------------------------------------------------------------
structure Setup where
  rules : List Rule
  d : Primitives.Ctx
  gap : Q
  cm : List (TrackId × TrackId) := []

def Setup.mk' (rules : List Rule) (τ : Trace) (ρ : Reading) (gap : Q) : Setup :=
  let arr := τ.toArray
  let cm := canonMap arr gap
  { rules := rules, d := Primitives.Ctx.mk' (τ.map (canonicalScene cm)) ρ, gap := gap, cm := cm }

def Setup.n (S : Setup) : Nat := S.d.n
def Setup.scenes (S : Setup) : Array Scene := S.d.scenes
def Setup.ctx (S : Setup) (β : Binding) : SemCtx := Rule.context S.rules S.d β
def Setup.tracks (S : Setup) : List TrackId := (S.scenes.toList.flatMap (·.tracks)).eraseDups
/-- First and last instant at which a canonical identity is present. -/
def Setup.span (S : Setup) (t : TrackId) : Option (Nat × Nat) :=
  match firstSeen S.scenes t, lastSeen S.scenes t with
  | some a, some b => some (a, b)
  | _, _ => none

-- ---------------------------------------------------------------------------------------------
-- Enumeration
-- ---------------------------------------------------------------------------------------------
/-- Tracks that satisfy a binder's class at some instant (evaluated once per track). -/
def candidates (S : Setup) (b : Binder) : List TrackId :=
  S.tracks.filter fun t =>
    (Rule.evalRuleFormula (S.ctx ⟨[(b.name, .track t)]⟩) b.cls).any fun r => r.v == .t

def spansOverlap (S : Setup) (a b : TrackId) : Bool :=
  match S.span a, S.span b with
  | some (a0, a1), some (b0, b1) => a0 ≤ b1 && b0 ≤ a1
  | _, _ => false

/-- All assignments of distinct, pairwise co-present candidates to the binders, subject first.
    Each binder's candidates are computed once. -/
def groundings (S : Setup) (r : Rule) : List Grounding :=
  let cands := r.binders.map fun b => (b.name, candidates S b)
  let rec go (bs : List (String × List TrackId)) (used : List TrackId) : List (List (String × TrackId)) :=
    match bs with
    | [] => [[]]
    | (name, cs) :: rest =>
      cs.filter (fun c => !used.contains c && used.all (spansOverlap S c)) |>.flatMap fun c =>
        (go rest (c :: used)).map fun tail => (name, c) :: tail
  (go cands []).map Grounding.mk

/-- Predicted grounding count without enumerating: the product of candidate counts (an upper
    bound when candidates overlap). -/
def predictedGroundings (S : Setup) (r : Rule) : Nat :=
  r.binders.foldl (fun acc b => acc * (candidates S b).length) 1

-- ---------------------------------------------------------------------------------------------
-- Timelines
-- ---------------------------------------------------------------------------------------------
/-- One evaluation of a rule for a grounding: the verdict per instant, whether the rule was
    engaged at some instant with every party present, and whether every party was present at
    some instant at all. -/
structure Timeline where
  verdicts : Array (Timestamp × Verdict)
  live : Bool
  present : Bool
  deriving Repr

/-- Evaluate a rule for a grounding once. A binder absent inside its identity's span is an
    identity gap (unknown); absent outside it, the rule is not engaged. -/
def evaluate (S : Setup) (r : Rule) (g : Grounding) : Timeline :=
  let c := S.ctx g.binding
  let engaged := r.engagedAll c
  let obl := Rule.evalRuleFormula c r.obligation
  let spans := g.assign.map fun (_, t) => (t, S.span t)
  let rows := (Array.range S.n).map fun i =>
    let s := S.scenes[i]!
    let missing := spans.filter fun (t, _) => !s.tracks.contains t
    let v : Verdict :=
      if missing.isEmpty then verdictAt engaged[i]! obl[i]!
      else
        let inGap := missing.filter fun (_, sp) => match sp with
          | some (a, b) => a < i && i < b
          | none => false
        if inGap.isEmpty then .notApplicable
        else .unknown (inGap.map fun (t, _) => .identityGap t)
    (s.t, v, missing.isEmpty && engaged[i]!.v == .t, missing.isEmpty)
  ⟨rows.map fun (t, v, _, _) => (t, v), rows.any fun (_, _, l, _) => l, rows.any fun (_, _, _, p) => p⟩

def timeline (S : Setup) (r : Rule) (g : Grounding) : Array (Timestamp × Verdict) := (evaluate S r g).verdicts

/-- The verdict of a grounding at one instant. -/
def verdictAt (S : Setup) (r : Rule) (g : Grounding) (i : Nat) : Verdict :=
  ((timeline S r g)[i]?).map (·.2) |>.getD (.unknown [.outOfRange])

/-- The episode verdict: a violation anywhere is a violation; else any unknown is unknown (with
    every reason); else engaged anywhere is compliant; else not applicable. -/
def episode (tl : List Verdict) : Verdict :=
  if tl.any (· == .violated) then .violated
  else
    let unknowns := tl.flatMap Verdict.reasons
    if tl.any (fun v => match v with | .unknown _ => true | _ => false) then .unknown unknowns.eraseDups
    else if tl.any (· == .compliant) then .compliant
    else .notApplicable

/-- Every grounding evaluated once: its episode verdict and timeline. -/
def check (S : Setup) (r : Rule) : List (Grounding × Timeline × Verdict) :=
  (groundings S r).map fun g =>
    let tl := evaluate S r g
    (g, tl, episode (tl.verdicts.toList.map (·.2)))

/-- Engaged (applicability true) at some instant for some grounding: the rule says something on
    this trace. -/
def live (S : Setup) (r : Rule) : Bool := (check S r).any fun (_, tl, _) => tl.live

end Grounding
end TrafficSpec
