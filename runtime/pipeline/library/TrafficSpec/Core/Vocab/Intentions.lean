/-
  TrafficSpec.Core.Vocab.Intentions
  Declared intentions: what a source declares a road user intends at a target region.

  No camera sees an intention. It reaches a rule through this one door, three-valued and per
  scene: the source's declaration current at that scene, for one road user at one target region,
  true or false per id, or absent where the declaration does not decide the id or the source has
  no current plan for the pair. The ids are `int.*` strings declared by the plan per node and
  recorded by the harness; nothing enumerates them here.
-/
import TrafficSpec.Core.Vocab.World

namespace TrafficSpec

/-- Well-formed intention id: `int.` followed by a snake-case name. -/
def IntId.wellFormed (id : IntId) : Bool :=
  let rest := (id.drop 4).toString
  id.startsWith "int." && !rest.isEmpty && rest.all (fun c => c.isLower || c.isDigit || c == '_')

/-- The declared value of `id` for road user `x` at region `r` at this scene, or `none` where the
    pair or the id is not declared. -/
def Scene.intention (s : Scene) (id : IntId) (x : TrackId) (r : RegionId) : Option Bool :=
  (s.intents.find? fun d => d.vehicle == x && d.target == r).bind fun d => (d.values.find? (·.1 == id)).map (·.2)

end TrafficSpec
