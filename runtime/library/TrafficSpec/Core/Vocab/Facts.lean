/-
  TrafficSpec.Core.Vocab.Facts
  Declared facts: what a source declares of its subjects (one or two road users, a region, or a
  road user and a region) that no atom observes and no road-user class decides.

  A role or a duty being performed now, a permit held, an assignment, a membership, a consent
  between two road users, an emergency a road user's conduct answers to, or what a map record states
  of a region: no camera sees them, and a scene source can confirm them. They reach a rule through
  this one door, three-valued and per scene: the source's declaration for those subjects, true or
  false per id, or absent where the source does not decide the id for them. The ids are `fact.*`
  strings declared by the plan per node and recorded by the harness; nothing enumerates them here.
-/
import TrafficSpec.Core.Vocab.World

namespace TrafficSpec

/-- Well-formed fact id: `fact.` followed by a snake-case name. -/
def FactId.wellFormed (id : FactId) : Bool :=
  let rest := (id.drop 5).toString
  id.startsWith "fact." && !rest.isEmpty && rest.all (fun c => c.isLower || c.isDigit || c == '_')

/-- The declared value of `id` for the road users `users` (in order) and the regions `regions` at
    this scene, or `none` where the source does not declare it for them. -/
def Scene.fact (s : Scene) (id : FactId) (users : List TrackId) (regions : List RegionId) : Option Bool :=
  (s.facts.find? fun d => d.id == id && d.users == users && d.regions == regions).map (·.value)

end TrafficSpec
