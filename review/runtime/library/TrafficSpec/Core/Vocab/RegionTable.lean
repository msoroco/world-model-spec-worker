/-
  TrafficSpec.Core.Vocab.RegionTable
  What a region quantifier reads of a trace, computed once per trace and kind: each scene's
  structures by id, and for every kind the regions the quantifier ranges over with each one's
  membership of the kind at every instant. A table is built from the scenes alone, holds no value
  that depends on a binding, and is proved equal to the direct reading it replaces.

  `Tables.build` creates one shared `Thunk` for the index and one per kind of `StructureKind.all`;
  a thunk is computed the first time it is read and every later read of the same table returns
  that value. `Tables.rowsOf` computes the rows directly for a kind with no entry; every kind has
  one (`build_has`), so that branch is never taken by an evaluation.
-/
import TrafficSpec.Core.Foundations.Unknown
import TrafficSpec.Core.Vocab.Atoms
import Std.Data.HashMap

namespace TrafficSpec
namespace RegionTable

/-- A scene's structures by id; where several share an id, the first, as `Scene.structure?` reads. -/
def structIndex (s : Scene) : Std.HashMap RegionId Structure :=
  s.structures.foldl (fun m st => m.insertIfNew st.id st) {}

/-- Every region a quantifier over kind `k` ranges over in some scene, in order of first appearance. -/
def candidates (scenes : Array Scene) (k : StructureKind) : List RegionId :=
  (scenes.toList.flatMap fun s => regionCandidates s k).eraseDups

/-- At each instant, whether region `r` is of kind `k`; unknown where the scene lacks the region or
    cannot tell the kind. -/
def kindRow (scenes : Array Scene) (r : RegionId) (k : StructureKind) : Array R :=
  scenes.map fun s => R.ofOption (isKind s r k) (.absentAtom s!"st_{k}")

/-- The regions a quantifier over one kind ranges over, and the kind row of each, in the same order. -/
structure KindRows where
  ids : Array RegionId
  isKind : Array (Array R)

/-- The rows read directly from the scenes. -/
def KindRows.spec (scenes : Array Scene) (k : StructureKind) : KindRows :=
  let ids := (candidates scenes k).toArray
  { ids := ids, isKind := ids.map (kindRow scenes · k) }

/-- The rows with each membership read through the scenes' id indexes. -/
def KindRows.build (scenes : Array Scene) (index : Array (Std.HashMap RegionId Structure))
    (k : StructureKind) : KindRows :=
  let ids := (candidates scenes k).toArray
  let w : UnknownReason := .absentAtom s!"st_{k}"
  { ids := ids, isKind := ids.map fun r => index.map fun m => R.ofOption ((m[r]?).bind (·.isOfKind k)) w }

/-- One kind's rows, computed the first time they are read. -/
structure KindEntry (scenes : Array Scene) where
  kind : StructureKind
  rows : Thunk KindRows
  ok : rows.get = KindRows.spec scenes kind

/-- The tables of one trace: its scenes' id indexes and one entry per kind. -/
structure Tables (scenes : Array Scene) where
  index : Thunk (Array (Std.HashMap RegionId Structure))
  index_ok : index.get = scenes.map structIndex
  kinds : List (KindEntry scenes)

theorem structIndex_foldl (r : RegionId) :
    ∀ (l : List Structure) (m : Std.HashMap RegionId Structure),
      (l.foldl (fun m st => m.insertIfNew st.id st) m)[r]? = (m[r]?).or (l.find? (·.id == r))
  | [], m => by simp
  | st :: l, m => by
    rw [List.foldl_cons, structIndex_foldl r l, Std.HashMap.getElem?_insertIfNew, List.find?_cons]
    by_cases he : st.id = r
    · subst he
      cases hm : m[st.id]? <;> simp [hm, Std.HashMap.mem_iff_isSome_getElem?]
    · have : (st.id == r) = false := by simpa using he
      simp [this]

/-- The index reads a scene's structure as `Scene.structure?` does. -/
theorem structIndex_getElem? (s : Scene) (r : RegionId) : (structIndex s)[r]? = s.structure? r := by
  simp [structIndex, structIndex_foldl, Scene.structure?]

theorem build_eq (scenes : Array Scene) (k : StructureKind) :
    KindRows.build scenes (scenes.map structIndex) k = KindRows.spec scenes k := by
  simp only [KindRows.build, KindRows.spec, kindRow, Array.map_map]
  congr 1
  apply Array.map_congr_left
  intro r _
  apply Array.map_congr_left
  intro s _
  simp [structIndex_getElem?, TrafficSpec.isKind]

/-- The tables of a trace: nothing is computed until a quantifier reads it. -/
def Tables.build (scenes : Array Scene) : Tables scenes :=
  let index : Thunk (Array (Std.HashMap RegionId Structure)) := Thunk.mk fun _ => scenes.map structIndex
  { index := index, index_ok := rfl,
    kinds := StructureKind.all.map fun k =>
      { kind := k, rows := Thunk.mk fun _ => KindRows.build scenes index.get k,
        ok := build_eq scenes k } }

theorem mem_all (k : StructureKind) : k ∈ StructureKind.all := by
  cases k <;> decide

/-- Every kind has an entry in the tables `Tables.build` makes. -/
theorem build_has (scenes : Array Scene) (k : StructureKind) :
    ((Tables.build scenes).kinds.find? (·.kind == k)).isSome := by
  rw [List.find?_isSome]
  exact ⟨_, List.mem_map_of_mem (mem_all k), by simp⟩

/-- The rows of a kind: its entry's, or computed directly for a kind with no entry. -/
def Tables.rowsOf {scenes : Array Scene} (t : Tables scenes) (k : StructureKind) : KindRows :=
  match t.kinds.find? (·.kind == k) with
  | some e => e.rows.get
  | none => KindRows.spec scenes k

/-- The id index of scene `i`. -/
def Tables.indexAt {scenes : Array Scene} (t : Tables scenes) (i : Nat) : Std.HashMap RegionId Structure :=
  t.index.get[i]?.getD {}

/-- A kind's rows are those read directly from the scenes. -/
theorem rowsOf_eq {scenes : Array Scene} (t : Tables scenes) (k : StructureKind) :
    t.rowsOf k = KindRows.spec scenes k := by
  unfold Tables.rowsOf
  split
  · rename_i e h
    have hk := List.find?_some h
    simp only [beq_iff_eq] at hk
    rw [e.ok, hk]
  · rfl

/-- The quantifier's range: every candidate, in order of first appearance, without repetition. -/
theorem ids_eq {scenes : Array Scene} (t : Tables scenes) (k : StructureKind) :
    (t.rowsOf k).ids.toList = candidates scenes k := by
  simp [rowsOf_eq, KindRows.spec]

/-- Each candidate's kind row, with the reasons of an absent region and of a kind the source cannot tell. -/
theorem isKind_eq {scenes : Array Scene} (t : Tables scenes) (k : StructureKind) :
    (t.rowsOf k).isKind = (t.rowsOf k).ids.map (kindRow scenes · k) := by
  simp [rowsOf_eq, KindRows.spec]

/-- Within the trace, the index tells a region present exactly where `Scene.structure?` finds it. -/
theorem indexAt_contains {scenes : Array Scene} (t : Tables scenes) {i : Nat} (hi : i < scenes.size)
    (r : RegionId) : (t.indexAt i).contains r = (scenes[i]!.structure? r).isSome := by
  simp [Tables.indexAt, t.index_ok, hi, getElem!_pos, Std.HashMap.contains_eq_isSome_getElem?,
    structIndex_getElem?]

end RegionTable
end TrafficSpec
