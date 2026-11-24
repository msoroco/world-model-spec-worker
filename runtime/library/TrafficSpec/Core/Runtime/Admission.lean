/-
  TrafficSpec.Core.Runtime.Admission
  What a trace must satisfy, as written, before any rule is evaluated on it: the declared facts
  (assumptions, intentions and facts) name what their scene holds, each once, by well-formed ids,
  a fact of one or two distinct subjects, at most one a region, and a fact of a region alone the
  same at every scene that declares it; no
  structure is labelled with an abstract kind or lists one among the kinds its source cannot tell
  (an abstract kind is the union of the kinds refining it, read only by a formula); a sign's
  `governs_sidewalk` names only sidewalks of the scene, on a regulatory sign whose code is a riding
  prohibition, and its `governs_parking_space` only parking spaces of the scene, on an
  `angle_parking` regulatory sign; and the accepted re-identification links are one-to-one.

  The checks are exact and read no geometry, so a recorded trace, a JSON case and a Lean witness
  are held to them alike. `Grounding.Setup.admit` calls them; every evaluation builds its setup
  there.
-/
import TrafficSpec.Core.Runtime.Identity
import TrafficSpec.Core.Vocab.Assumptions
import TrafficSpec.Core.Vocab.Intentions
import TrafficSpec.Core.Vocab.Facts
import TrafficSpec.Core.Vocab.Atoms

namespace TrafficSpec
namespace Admission

private def duplicates {α : Type} [BEq α] (xs : List α) : List α :=
  (xs.filter fun x => xs.count x > 1).eraseDups

/-- The defects of the regions a device's record names under `field`: each a structure of the scene
    labelled `kind` or a kind refining it, on a device of which `onSign` holds (`sign` says which). -/
private def recordedRegionDefects (s : Scene) (d : Device) (field : String) (regions : List RegionId)
    (kind : StructureKind) (onSign : Bool) (sign : String) : List String :=
  let who := s!"scene t={s.t}: device {d.id} {field}"
  (if regions.isEmpty || onSign then [] else [s!"{who}: only {sign} carries it"]) ++
  regions.filterMap fun r => match s.structure? r with
    | none => some s!"{who}: {r} is not a structure of the scene"
    | some st => if st.kind.refines kind then none else some s!"{who}: structure {r} is `{st.kind}`, not `{kind}`"

/-- The defects of one scene's devices' sidewalk and parking-space records. -/
def deviceDefects (s : Scene) : List String :=
  s.devices.flatMap fun d =>
    let sign := d.kind == .regulatorySign
    recordedRegionDefects s d "governs_sidewalk" (d.governsSidewalk.getD []) .sidewalk
      (sign && (d.code.map SignCode.ridingProhibitions.contains) == some true)
      "a regulatory sign whose code is a riding prohibition (bicycles_prohibited, bicycle_ebike_escooter_prohibited)"
    ++ recordedRegionDefects s d "governs_parking_space" (d.governsParkingSpace.getD []) .parkingSpace
      (sign && d.code == some .angleParking) "an angle_parking regulatory sign"

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
  (s.facts.flatMap fun f =>
    let who := s!"{at_}: fact record `{f.id}` users {f.users} regions {f.regions}"
    let n := f.users.length + f.regions.length
    (if FactId.wellFormed f.id then [] else [s!"{who}: `{f.id}` is not a well-formed fact id"]) ++
    (if n == 1 || n == 2 then [] else [s!"{who}: a fact names one or two subjects"]) ++
    (if f.regions.length ≤ 1 then [] else [s!"{who}: a fact names at most one region"]) ++
    (if f.users.eraseDups.length == f.users.length then [] else [s!"{who}: a pair names two distinct road users"]) ++
    (f.users.filter (!s.tracks.contains ·) |>.map fun t => s!"{who}: {t} is not a road user of the scene") ++
    (f.regions.filter (fun r => (s.structure? r).isNone) |>.map fun r => s!"{who}: {r} is not a structure of the scene")) ++
  ((duplicates (s.facts.map fun f => (f.id, f.users, f.regions))).map fun (id, us, rs) =>
    s!"{at_}: fact `{id}` declared more than once for users {us} regions {rs}") ++
  (s.structures.flatMap fun st =>
    (if st.kind.isAbstract then [s!"{at_}: structure {st.id} is labelled `{st.kind}`, an abstract kind; label it with a kind that refines `{st.kind}`"] else []) ++
    ((st.unobservedKinds.filter (·.isAbstract)).eraseDups.map fun k =>
      s!"{at_}: structure {st.id} lists `{k}` among unobserved_kinds, an abstract kind; list the kinds refining it that the source cannot tell")) ++
  ((duplicates (s.assumptions.map (·.1))).map fun id => s!"{at_}: assumption `{id}` listed more than once") ++
  ((s.assumptions.map (·.1)).eraseDups.filter (!AsmId.wellFormed ·) |>.map fun id => s!"{at_}: `{id}` is not a well-formed assumption id")

/-- Accepted links that give a track two successors or two predecessors. -/
def linkDefects (τ : Array Scene) (gap : Q) : List String :=
  let links := Grounding.acceptedLinks τ gap
  ((duplicates (links.map (·.1))).map fun t =>
    s!"track {t} is continued by more than one accepted link: {links.filter (·.1 == t)}") ++
  ((duplicates (links.map (·.2))).map fun t =>
    s!"track {t} continues more than one accepted link: {links.filter (·.2 == t)}")

/-- A fact of a region alone is a map record's: declared with one value wherever it is declared. -/
def regionFactDefects (τ : Trace) : List String :=
  let decls := τ.flatMap fun s => (s.facts.filter (·.users.isEmpty)).map fun f => ((f.id, f.regions), f.value)
  ((decls.map (·.1)).eraseDups.filter fun k => ((decls.filter (·.1 == k)).map (·.2)).eraseDups.length > 1).map fun (id, rs) =>
    s!"fact `{id}` of region(s) {rs} is declared both true and false; a fact of a region alone is the same at every scene"

/-- Every defect of the trace as written; empty for a trace every evaluation may read. -/
def defects (τ : Trace) (gap : Q) : List String :=
  τ.flatMap sceneDefects ++ τ.flatMap deviceDefects ++ regionFactDefects τ ++ linkDefects τ.toArray gap

end Admission
end TrafficSpec
