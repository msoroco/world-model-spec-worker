/-
  TrafficSpec.Core.Vocab.Assumptions
  Legal region classes and calendar classes: facts a rule needs that no source observes.

  A district, a school day, an administrative designation are facts a rule needs and no camera
  sees. They reach a rule through this one door, three-valued: supplied true or false by the
  adapter per scene, or absent. The ids are `asm.*` strings declared by the plan per node and
  recorded by the harness; nothing enumerates them here, so nothing here goes stale.
-/
import TrafficSpec.Core.Vocab.World

namespace TrafficSpec

/-- Well-formed assumption id: `asm.` followed by a snake-case name. -/
def AsmId.wellFormed (id : AsmId) : Bool :=
  let rest := (id.drop 4).toString
  id.startsWith "asm." && !rest.isEmpty && rest.all (fun c => c.isLower || c.isDigit || c == '_')

/-- The assumption's value at this scene, or `none` when the source did not supply it. -/
def Scene.assumption (s : Scene) (id : AsmId) : Option Bool :=
  (s.assumptions.find? (·.1 == id)).map (·.2)

end TrafficSpec
