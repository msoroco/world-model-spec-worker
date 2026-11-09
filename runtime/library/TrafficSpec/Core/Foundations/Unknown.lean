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
  | intentionMissing (id : IntId)         -- an `int.*` the scene did not declare for the road user at the region
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
  | .intentionMissing id => s!"intention_missing:{id}"
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

/-- The number of values among the first `m` that satisfy `p`: what `build` stores at `m`. -/
def countTo (vals : Array R) (p : Tri → Bool) : Nat → Nat
  | 0 => 0
  | m + 1 => countTo vals p m + (if p vals[m]!.v then 1 else 0)

private theorem count_fold (vals : Array R) (p : Tri → Bool) (k : Nat) :
    ((List.range k).foldl (fun (acc : Array Nat) i => acc.push (acc[i]! + (if p vals[i]!.v then 1 else 0))) #[0]).size = k + 1 ∧
    ∀ m, m ≤ k → ((List.range k).foldl (fun (acc : Array Nat) i =>
      acc.push (acc[i]! + (if p vals[i]!.v then 1 else 0))) #[0])[m]! = countTo vals p m := by
  induction k with
  | zero => simp [countTo]
  | succ k ih =>
    obtain ⟨hs, hv⟩ := ih
    simp only [List.range_succ, List.foldl_append, List.foldl_cons, List.foldl_nil]
    refine ⟨by simp [hs], fun m hm => ?_⟩
    rw [getElem!_pos _ m (by simp; omega), Array.getElem_push]
    split
    · rw [← getElem!_pos _ m (by omega)]; exact hv m (by omega)
    · obtain rfl : m = k + 1 := by omega
      simp only [countTo]; rw [hv k (Nat.le_refl _)]

theorem countTo_mono (vals : Array R) (p : Tri → Bool) {a b : Nat} (h : a ≤ b) :
    countTo vals p a ≤ countTo vals p b := by
  induction b with
  | zero => cases h; exact Nat.le_refl _
  | succ b ih =>
    rcases Nat.lt_or_ge a (b + 1) with h' | h'
    · exact Nat.le_trans (ih (by omega)) (by simp only [countTo]; omega)
    · obtain rfl : a = b + 1 := by omega
      exact Nat.le_refl _

/-- The count rises between `lo` and `n` exactly when a value at an index in `[lo, n)` satisfies `p`. -/
theorem countTo_lt_iff (vals : Array R) (p : Tri → Bool) (lo n : Nat) :
    countTo vals p lo < countTo vals p n ↔ ∃ j, lo ≤ j ∧ j < n ∧ p vals[j]!.v := by
  constructor
  · intro h
    induction n with
    | zero => simp [countTo] at h
    | succ n ih =>
      by_cases hp : p vals[n]!.v
      · rcases Nat.lt_or_ge n lo with h' | h'
        · have := countTo_mono vals p (show n + 1 ≤ lo by omega); omega
        · exact ⟨n, h', Nat.lt_succ_self _, hp⟩
      · simp only [countTo, hp] at h
        obtain ⟨j, h1, h2, h3⟩ := ih (by simpa using h)
        exact ⟨j, h1, by omega, h3⟩
  · rintro ⟨j, h1, h2, h3⟩
    have a := countTo_mono vals p h1
    have b := countTo_mono vals p (show j + 1 ≤ n by omega)
    have c : countTo vals p (j + 1) = countTo vals p j + 1 := by simp [countTo, h3]
    omega

private theorem cnt_build_f (vals : Array R) (lo hi : Nat) (hl : lo ≤ hi) (h : hi < vals.size) :
    cnt (build vals).prefF lo hi = countTo vals (· = .f) (hi + 1) - countTo vals (· = .f) lo := by
  have hf := count_fold vals (· = .f) vals.size
  simp only [cnt, build]
  rw [hf.2 (hi + 1) (by omega), hf.2 lo (by omega)]

/-- `all` is false only on a definite false in the range. -/
theorem all_f_witness (vals : Array R) (lo hi : Nat) (h : ((build vals).all lo hi).v = .f) :
    ∃ j, lo ≤ j ∧ j ≤ hi ∧ j < vals.size ∧ vals[j]!.v = .f := by
  have hl : lo ≤ hi := by
    refine Nat.le_of_not_lt fun hn => ?_
    simp only [all, hn, if_true] at h
    exact absurd h (by decide)
  have hc : cnt (build vals).prefF lo hi > 0 := by
    refine Nat.pos_of_ne_zero fun hn => ?_
    simp only [all, show ¬ hi < lo by omega, if_false, hn, Nat.lt_irrefl] at h
    split at h <;> simp [R.t] at h
  have hhi : hi < vals.size := by
    refine Nat.lt_of_not_le fun hn => ?_
    have hf := count_fold vals (· = .f) vals.size
    have : (build vals).prefF[hi + 1]! = 0 := by
      simp only [build]; rw [getElem!_neg]; · rfl
      rw [hf.1]; omega
    simp only [cnt, this] at hc
    omega
  rw [cnt_build_f vals lo hi hl hhi] at hc
  obtain ⟨j, h1, h2, h3⟩ := (countTo_lt_iff vals (· = .f) lo (hi + 1)).1 (by omega)
  exact ⟨j, h1, by omega, by omega, by simpa using h3⟩

/-- A definite false in a range inside the array makes `all` false. -/
theorem all_f_of_witness (vals : Array R) (lo hi j : Nat) (hhi : hi < vals.size) (hlo : lo ≤ j) (hj : j ≤ hi)
    (hf : vals[j]!.v = .f) : (build vals).all lo hi = R.f := by
  have hc : cnt (build vals).prefF lo hi > 0 := by
    rw [cnt_build_f vals lo hi (by omega) hhi]
    have := (countTo_lt_iff vals (· = .f) lo (hi + 1)).2 ⟨j, hlo, by omega, by simp [hf]⟩
    omega
  simp only [all, show ¬ hi < lo by omega, if_false, hc, if_true]
end RangeAgg

end TrafficSpec
