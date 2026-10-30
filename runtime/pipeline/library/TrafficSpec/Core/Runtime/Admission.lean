/-
  TrafficSpec.Core.Runtime.Admission
  What a trace must satisfy, as written, before any rule is evaluated on it: the declared facts
  (assumptions and intentions) name what their scene holds, each once, by well-formed ids, and the
  accepted re-identification links are one-to-one.

  The checks are exact and read no geometry, so a recorded trace, a JSON case and a Lean witness
  are held to them alike. `Grounding.Setup.admit` calls them; every evaluation builds its setup
  there.
-/
import TrafficSpec.Core.Runtime.Identity
import TrafficSpec.Core.Vocab.Assumptions
import TrafficSpec.Core.Vocab.Intentions

namespace TrafficSpec
namespace Admission

private def duplicates {α : Type} [BEq α] (xs : List α) : List α :=
  (xs.filter fun x => xs.count x > 1).eraseDups

/-- The defects of one scene's declared facts. -/
def sceneDefects (s : Scene) : List String :=
  let at_ := s!"scene t={s.t}"
  (s.intents.flatMap fun d =>
    let who := s!"{at_}: intent record ({d.vehicle}, {d.target})"
    (if s.tracks.contains d.vehicle then [] else [s!"{who}: vehicle {d.vehicle} is not a road user of the scene"]) ++
    (if (s.structure? d.target).isSome then [] else [s!"{who}: target {d.target} is not a structure of the scene"]) ++
    ((duplicates (d.values.map (·.1))).map fun id => s!"{who}: `{id}` listed more than once") ++
    ((d.values.map (·.1)).eraseDups.filter (!IntId.wellFormed ·) |>.map fun id => s!"{who}: `{id}` is not a well-formed intention id")) ++
  ((duplicates (s.intents.map fun d => (d.vehicle, d.target))).map fun (v, r) => s!"{at_}: more than one intent record for ({v}, {r})") ++
  ((duplicates (s.assumptions.map (·.1))).map fun id => s!"{at_}: assumption `{id}` listed more than once") ++
  ((s.assumptions.map (·.1)).eraseDups.filter (!AsmId.wellFormed ·) |>.map fun id => s!"{at_}: `{id}` is not a well-formed assumption id")

/-- Accepted links that give a track two successors or two predecessors. -/
def linkDefects (τ : Array Scene) (gap : Q) : List String :=
  let links := Grounding.acceptedLinks τ gap
  ((duplicates (links.map (·.1))).map fun t =>
    s!"track {t} is continued by more than one accepted link: {links.filter (·.1 == t)}") ++
  ((duplicates (links.map (·.2))).map fun t =>
    s!"track {t} continues more than one accepted link: {links.filter (·.2 == t)}")

/-- Every defect of the trace as written; empty for a trace every evaluation may read. -/
def defects (τ : Trace) (gap : Q) : List String :=
  τ.flatMap sceneDefects ++ linkDefects τ.toArray gap

end Admission
end TrafficSpec
