/-
  TrafficSpec.Core.Foundations.Unknown
  Typed reasons for an unknown verdict, and the three-valued result that carries them.

  A monitor that says `unknown` without saying why is useless for diagnosis. Every place that
  produces `u` attaches a reason; the connectives keep the reasons of their unknown operands and
  drop them once a value is decided.
-/
import TrafficSpec.Core.Foundations.Tri
import TrafficSpec.Core.Foundations.Units
import TrafficSpec.Core.Foundations.Handles

namespace TrafficSpec

inductive UnknownReason
  | absentAtom (name : String)            -- the source did not observe this atom for this entity
  | samplingGap (op : String)             -- observations too sparse for the window
  | windowTruncated (op : String)         -- the window reaches past the start or end of the trace
  | identityGap (track : TrackId)         -- a bound track is not present and no link continues it
  | assumptionMissing (id : AsmId)        -- an `asm.*` the scene did not supply
  | parameterMissing (name : String)      -- a reading parameter the rule names but the reading lacks
  | unboundVariable (name : String)       -- a formula variable with no binding
  | compositionUnknown (rule : String)    -- a composed rule reported unknown or does not exist
  | outOfRange                            -- an index outside the trace
  | divisionByZero (what : String)
  | malformed (what : String)             -- a literal that names no enumeration value, wrong arity
  | undefined (concept : String)          -- the concept's precondition does not hold here (e.g. a multi-lane configuration)
  | aggregateUnresolved (id : String)     -- the posted definition of the aggregate decides neither inclusion nor exclusion of the road user's class
  deriving Repr, DecidableEq, Inhabited

namespace UnknownReason
/-- A stable spelling for reports and histograms. -/
def tag : UnknownReason → String
  | .absentAtom n => s!"absent_atom:{n}"
  | .samplingGap op => s!"sampling_gap:{op}"
  | .windowTruncated op => s!"window_truncated:{op}"
  | .identityGap t => s!"identity_gap:{t}"
  | .assumptionMissing id => s!"assumption_missing:{id}"
  | .parameterMissing n => s!"parameter_missing:{n}"
  | .unboundVariable n => s!"unbound_variable:{n}"
  | .compositionUnknown r => s!"composition_unknown:{r}"
  | .outOfRange => "out_of_range"
  | .divisionByZero w => s!"division_by_zero:{w}"
  | .malformed w => s!"malformed:{w}"
  | .undefined c => s!"undefined:{c}"
  | .aggregateUnresolved id => s!"aggregate_unresolved:{id}"
instance : ToString UnknownReason := ⟨tag⟩
end UnknownReason

/-- A three-valued result with the reasons behind an unknown one. -/
structure R where
  v : Tri
  why : List UnknownReason := []
  deriving Repr, Inhabited

namespace R
def t : R := ⟨.t, []⟩
def f : R := ⟨.f, []⟩
def u (w : UnknownReason) : R := ⟨.u, [w]⟩
def ofBool (b : Bool) : R := ⟨Tri.ofBool b, []⟩
def ofOption (o : Option Bool) (w : UnknownReason) : R :=
  match o with
  | some b => ofBool b
  | none => u w
/-- Reasons are kept only while the value is undecided. -/
def settle (v : Tri) (why : List UnknownReason) : R := ⟨v, if v = .u then why.eraseDups else []⟩
@[simp] theorem settle_v (v : Tri) (why : List UnknownReason) : (settle v why).v = v := rfl
def and (a b : R) : R := settle (Tri.and a.v b.v) (a.why ++ b.why)
def or (a b : R) : R := settle (Tri.or a.v b.v) (a.why ++ b.why)
def not (a : R) : R := ⟨Tri.not a.v, a.why⟩
@[simp] theorem and_v (a b : R) : (and a b).v = Tri.and a.v b.v := rfl
@[simp] theorem or_v (a b : R) : (or a b).v = Tri.or a.v b.v := rfl
@[simp] theorem not_v (a : R) : (not a).v = Tri.not a.v := rfl
def implies (a b : R) : R := or (not a) b
def all (xs : List R) : R := xs.foldl and t
def any (xs : List R) : R := xs.foldl or f
/-- Lift an `Option α` into a computation that is unknown when the option is empty. -/
def bindOpt {α : Type} (o : Option α) (w : UnknownReason) (k : α → R) : R :=
  match o with
  | some a => k a
  | none => u w
end R

/-- A quantity that may be unknown, with the reason. -/
abbrev QR := Except UnknownReason Q

/-- Kleene conjunction and disjunction over index ranges of a per-instant array in O(1) each,
    from prefix counts and next-unknown pointers. Reasons come from the earliest unknown in range. -/
structure RangeAgg where
  vals : Array R
  prefF : Array Nat      -- prefF[i] = number of false values before index i
  prefT : Array Nat
  prefU : Array Nat
  nextU : Array Nat      -- nextU[i] = smallest k ≥ i with an unknown value (size when none)

namespace RangeAgg
def build (vals : Array R) : RangeAgg :=
  let n := vals.size
  let count (p : Tri → Bool) : Array Nat :=
    (List.range n).foldl (fun (acc : Array Nat) i => acc.push (acc[i]! + (if p vals[i]!.v then 1 else 0))) #[0]
  let nextU := (List.range n).reverse.foldl (fun (acc : Array Nat) i =>
    acc.set! i (if vals[i]!.v = .u then i else acc[i + 1]!)) (Array.replicate (n + 1) n)
  ⟨vals, count (· = .f), count (· = .t), count (· = .u), nextU⟩

private def cnt (pref : Array Nat) (lo hi : Nat) : Nat := pref[hi + 1]! - pref[lo]!
private def firstUnknown (a : RangeAgg) (lo hi : Nat) : List UnknownReason :=
  let k := a.nextU[lo]!
  if k ≤ hi then a.vals[k]!.why else []

/-- ∧ over `lo … hi` inclusive; true on an empty range. -/
def all (a : RangeAgg) (lo hi : Nat) : R :=
  if hi < lo then R.t
  else if cnt a.prefF lo hi > 0 then R.f
  else if cnt a.prefU lo hi > 0 then ⟨.u, a.firstUnknown lo hi⟩
  else R.t
/-- ∨ over `lo … hi` inclusive; false on an empty range. -/
def any (a : RangeAgg) (lo hi : Nat) : R :=
  if hi < lo then R.f
  else if cnt a.prefT lo hi > 0 then R.t
  else if cnt a.prefU lo hi > 0 then ⟨.u, a.firstUnknown lo hi⟩
  else R.f
end RangeAgg

end TrafficSpec
