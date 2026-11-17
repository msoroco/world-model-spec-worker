/-
  TrafficSpec.Core.Foundations.Accumulate
  A rate integrated since a condition last became true, over the whole trace in one forward pass,
  and its specification over Lean's `Rat`.

  The start at observation `i` is `Temporal.runStartAll`'s: the latest observation `j ≤ i` at which
  the condition rose definitely (false at `j − 1`, true at `j`), with the condition known at every
  observation of `(j, i]`. The value is Σ_{k ∈ (j, i]} rate_k · (t_k − t_{k−1}): zero at the start,
  the rate at an observation covering the interval that ends there. It is unknown, never a value,
  at every observation when the step bound is not positive; where the start is unknown or none is
  observed (`windowTruncated op`, or the condition's reason); where an interval ending at an
  observation of `[j, i]`, the one ending at the start included, is longer than the step bound
  (`samplingGap op`); where a rate of `(j, i]` is missing (`missing`).

  Proved here: the start is exactly the latest definite rise with the condition known since; a
  decided value comes from such a start, a positive bound, intervals within the bound, present rates,
  and equals the discrete sum; each unknown case gives its reason; the value at `i` depends only on
  the inputs at observations `≤ i`; the sum splits at any intermediate observation.
-/
import TrafficSpec.Core.Foundations.Temporal

namespace TrafficSpec

/-- A rational's value in Lean's `Rat`. -/
def Q.val (q : Q) : Rat := mkRat q.num q.den

namespace Accumulate
open Temporal

-- ---------------------------------------------------------------------------------------------
-- The operator
-- ---------------------------------------------------------------------------------------------
/-- The running state at an observation: the sum of rate × interval since the trace start (a
    missing rate adds nothing), the latest observation whose rate is missing, and the latest
    observation reached across an interval longer than the step bound. -/
structure Run where
  sum : Q
  lastMissing : Option Nat
  lastWide : Option Nat
  deriving Inhabited

def Run.init : Run := ⟨Q.zero, none, none⟩

/-- The interval ending at observation `i`; zero at the first. -/
def dt (times : Array Q) (i : Nat) : Q := if i = 0 then Q.zero else Q.sub times[i]! times[i - 1]!

/-- The state at observation `i` from the state at the observation before. -/
def runStep (times : Array Q) (rate : Array (Option Q)) (maxStep : Q) (prev : Run) (i : Nat) : Run :=
  { sum := match rate[i]! with | some ω => Q.add prev.sum (Q.mul ω (dt times i)) | none => prev.sum
    lastMissing := if (rate[i]!).isNone then some i else prev.lastMissing
    lastWide := if i != 0 && Q.gt (dt times i) maxStep then some i else prev.lastWide }

/-- The state at each of the first `n` observations, in one forward pass. -/
def runs (n : Nat) (times : Array Q) (rate : Array (Option Q)) (maxStep : Q) : Array Run :=
  (List.range n).foldl (fun (acc : Array Run) i =>
    acc.push (runStep times rate maxStep (if i = 0 then Run.init else acc[i - 1]!) i)) #[]

/-- The value at `i` from the starts and the states. -/
def valueAt (starts : Array (Except UnknownReason (Option Nat))) (rs : Array Run) (op : String)
    (missing : UnknownReason) (i : Nat) : QR :=
  match starts[i]! with
  | .error e => .error e
  | .ok none => .error (.windowTruncated op)
  | .ok (some j) =>
    if (rs[i]!).lastWide.any (j ≤ ·) then .error (.samplingGap op)
    else if (rs[i]!).lastMissing.any (j < ·) then .error missing
    else .ok (Q.sub (rs[i]!).sum (rs[j]!).sum)

/-- Rate × interval accumulated since ψ last became true, per observation. -/
def sinceRiseIntegralAll (times : Array Q) (rate : Array (Option Q)) (maxStep : Q) (op : String)
    (missing : UnknownReason) (ψ : Array R) : Array QR :=
  if Q.lt Q.zero maxStep then
    (Array.range ψ.size).map (valueAt (runStartAll op ψ) (runs ψ.size times rate maxStep) op missing)
  else Array.replicate ψ.size (.error (.malformed s!"{op} step bound is not positive"))

-- ---------------------------------------------------------------------------------------------
-- The specification
-- ---------------------------------------------------------------------------------------------
/-- Σ_{k ∈ (j, i]} rate_k · (t_k − t_{k−1}) over `Rat`; none where a rate of `(j, i]` is missing;
    zero where `i ≤ j`. -/
def integral (times : Array Q) (rate : Array (Option Q)) (j : Nat) : Nat → Option Rat
  | 0 => some 0
  | i + 1 => if i + 1 ≤ j then some 0 else do
      let acc ← integral times rate j i
      let ω ← rate[i + 1]!
      pure (acc + ω.val * ((times[i + 1]!).val - (times[i]!).val))

/-- ψ rises definitely at `j`: false at the observation before, true there. -/
def RisesAt (ψ : Array R) (j : Nat) : Prop := 0 < j ∧ ψ[j - 1]!.v = .f ∧ ψ[j]!.v = .t

/-- `j` is the start at `i`: a definite rise at `j ≤ i`, ψ known and rising nowhere in `(j, i]`. -/
def AnchorAt (ψ : Array R) (j i : Nat) : Prop :=
  j ≤ i ∧ RisesAt ψ j ∧ ∀ k, j < k → k ≤ i → ψ[k]!.v ≠ .u ∧ ¬ RisesAt ψ k

-- ---------------------------------------------------------------------------------------------
-- `Q` in `Rat`
-- ---------------------------------------------------------------------------------------------
section QVal

private theorem Q.ext' {a b : Q} (h₁ : a.num = b.num) (h₂ : a.den = b.den) : a = b := by
  cases a; cases b; simp_all

theorem Q.val_mk' (a : Int) (b : Nat) (hb : 0 < b) : (Q.mk' a b).val = mkRat a b := by
  unfold Q.mk' Q.val
  rw [dif_pos hb]
  simp only
  have hg : 0 < Nat.gcd a.natAbs b := Nat.gcd_pos_of_pos_right _ hb
  have ha : ((Nat.gcd a.natAbs b : Nat) : Int) ∣ a := Int.ofNat_dvd_left.mpr (Nat.gcd_dvd_left _ _)
  have hbd : Nat.gcd a.natAbs b ∣ b := Nat.gcd_dvd_right _ _
  generalize Nat.gcd a.natAbs b = G at hg ha hbd ⊢
  obtain ⟨a', rfl⟩ := ha
  obtain ⟨b', rfl⟩ := hbd
  rw [Int.mul_ediv_cancel_left _ (by omega), Nat.mul_div_cancel_left _ hg, Rat.mkRat_mul_left (Nat.ne_of_gt hg)]

private theorem den_ne (q : Q) : q.den ≠ 0 := Nat.ne_of_gt q.den_pos

theorem Q.val_add (a b : Q) : (Q.add a b).val = a.val + b.val := by
  unfold Q.add
  rw [Q.val_mk' _ _ (Nat.mul_pos a.den_pos b.den_pos)]
  unfold Q.val
  rw [Rat.mkRat_add_mkRat _ _ (den_ne a) (den_ne b)]

theorem Q.val_mul (a b : Q) : (Q.mul a b).val = a.val * b.val := by
  unfold Q.mul
  rw [Q.val_mk' _ _ (Nat.mul_pos a.den_pos b.den_pos)]
  unfold Q.val
  rw [Rat.mkRat_mul_mkRat]

theorem Q.val_sub (a b : Q) : (Q.sub a b).val = a.val - b.val := by
  unfold Q.sub
  rw [Q.val_mk' _ _ (Nat.mul_pos a.den_pos b.den_pos)]
  unfold Q.val
  rw [Rat.sub_eq_add_neg, Rat.neg_mkRat, Rat.mkRat_add_mkRat _ _ (den_ne a) (den_ne b), Int.neg_mul,
    ← Int.sub_eq_add_neg]

theorem Q.eq_iff_val (a b : Q) : Q.eq a b = true ↔ a.val = b.val := by
  unfold Q.eq Q.val
  rw [Rat.mkRat_eq_iff (den_ne a) (den_ne b)]
  simp

theorem Q.sub_self (a : Q) : Q.sub a a = Q.zero := by
  unfold Q.sub Q.mk'
  have hp : a.den * a.den > 0 := Nat.mul_pos a.den_pos a.den_pos
  rw [dif_pos hp]
  apply Q.ext' <;> simp [Q.zero, Q.ofInt, Int.sub_self, Nat.div_self hp]

theorem Q.le_iff_not_gt (a b : Q) : Q.le a b = true ↔ Q.gt a b = false := by
  unfold Q.le Q.gt Q.lt
  simp [Int.not_lt]

end QVal

-- ---------------------------------------------------------------------------------------------
-- The passes, by observation
-- ---------------------------------------------------------------------------------------------
section Passes
variable (times : Array Q) (rate : Array (Option Q)) (g : Q) (op : String) (missing : UnknownReason)

/-- One step of `runStartAll`, as its forward pass computes it. -/
def startStep (vals : Array R) (prev : Except UnknownReason (Option Nat)) (i : Nat) :
    Except UnknownReason (Option Nat) :=
  match vals[i]!.v with
  | .t =>
    if i = 0 then .error (.windowTruncated op)
    else match vals[i - 1]!.v with
      | .t => prev
      | .f => .ok (some i)
      | .u => .error (vals[i - 1]!.why.head?.getD (.malformed op))
  | .f => prev
  | .u => .error (vals[i]!.why.head?.getD (.malformed op))

/-- The state of `runStartAll` at observation `i`. -/
def startAt (vals : Array R) : Nat → Except UnknownReason (Option Nat)
  | 0 => startStep op vals (.ok none) 0
  | i + 1 => startStep op vals (startAt vals i) (i + 1)

/-- The running state at observation `i`. -/
def runAt : Nat → Run
  | 0 => runStep times rate g Run.init 0
  | i + 1 => runStep times rate g (runAt i) (i + 1)

/-- An array built by pushing, one observation at a time, a value that depends only on the values
    already pushed: its size, and each element as `v` gives it. -/
theorem build_get {α : Type} [Inhabited α] (f : Array α → Nat → α) (v : Nat → α) (N : Nat)
    (hf : ∀ acc i, i < N → acc.size = i → (∀ m, m < i → acc[m]! = v m) → f acc i = v i) :
    ∀ n, n ≤ N → ((List.range n).foldl (fun acc i => acc.push (f acc i)) #[]).size = n ∧
      ∀ k, k < n → ((List.range n).foldl (fun acc i => acc.push (f acc i)) #[])[k]! = v k := by
  intro n hn
  induction n with
  | zero => simp
  | succ n ih =>
    obtain ⟨hs, hk⟩ := ih (by omega)
    rw [List.range_succ, List.foldl_append]
    simp only [List.foldl_cons, List.foldl_nil]
    refine ⟨by simp [hs], fun k hk' => ?_⟩
    rcases Nat.lt_succ_iff_lt_or_eq.mp hk' with h | h
    · rw [getElem!_pos _ _ (by simp [hs]; omega), Array.getElem_push_lt (by omega), ← getElem!_pos _ _ (by omega)]
      exact hk k h
    · subst h
      rw [getElem!_pos _ _ (by simp [hs]), Array.getElem_push]
      simp only [hs, Nat.lt_irrefl, dite_false]
      exact hf _ _ (by omega) hs hk

theorem runs_get (n i : Nat) (hi : i < n) : (runs n times rate g)[i]! = runAt times rate g i := by
  unfold runs
  refine (build_get _ (runAt times rate g) n ?_ n (Nat.le_refl _)).2 i hi
  intro acc k _ hs hm
  cases k with
  | zero => rfl
  | succ k => simp only [Nat.add_one_ne_zero, if_false, Nat.add_sub_cancel]; rw [hm k (by omega)]; rfl

/-- A forward pass whose state is pushed at each observation, one value at a time: its size and each
    element as `v` gives it. -/
theorem pairs_get {β : Type} [Inhabited β] (s : β → Nat → β) (init : β) (v : Nat → β)
    (h0 : s init 0 = v 0) (hs : ∀ m, s (v m) (m + 1) = v (m + 1)) : ∀ n,
    ((List.range n).foldl (fun (acc : Array β × β) i => (acc.1.push (s acc.2 i), s acc.2 i)) (#[], init)).1.size = n ∧
    (∀ k, k < n → ((List.range n).foldl (fun (acc : Array β × β) i => (acc.1.push (s acc.2 i), s acc.2 i)) (#[], init)).1[k]! = v k) ∧
    (∀ m, n = m + 1 → ((List.range n).foldl (fun (acc : Array β × β) i => (acc.1.push (s acc.2 i), s acc.2 i)) (#[], init)).2 = v m) := by
  intro n
  induction n with
  | zero => simp
  | succ n ih =>
    obtain ⟨hsz, hk, h2⟩ := ih
    rw [List.range_succ, List.foldl_append]
    simp only [List.foldl_cons, List.foldl_nil]
    have hst : s ((List.range n).foldl (fun (acc : Array β × β) i => (acc.1.push (s acc.2 i), s acc.2 i)) (#[], init)).2 n = v n := by
      cases n with
      | zero => simpa using h0
      | succ m => rw [h2 m rfl]; exact hs m
    refine ⟨by simp [hsz], fun k hk' => ?_, fun m hm => by cases hm; exact hst⟩
    rcases Nat.lt_succ_iff_lt_or_eq.mp hk' with h | h
    · rw [getElem!_pos _ _ (by simp [hsz]; omega), Array.getElem_push_lt (by omega), ← getElem!_pos _ _ (by omega)]
      exact hk k h
    · subst h
      rw [getElem!_pos _ _ (by simp [hsz]), Array.getElem_push]
      simp only [hsz, Nat.lt_irrefl, dite_false]
      exact hst

theorem runStartAll_get (vals : Array R) (i : Nat) (hi : i < vals.size) :
    (runStartAll op vals)[i]! = startAt op vals i := by
  unfold runStartAll
  dsimp only
  rw [Array.mkEmpty_eq]
  exact (pairs_get (startStep op vals) (.ok none) (startAt op vals) rfl (fun _ => rfl) vals.size).2.1 i hi

end Passes

-- ---------------------------------------------------------------------------------------------
-- The start
-- ---------------------------------------------------------------------------------------------
section Start
variable {op : String} {ψ : Array R}

theorem AnchorAt.mono {j i i' : Nat} (h : AnchorAt ψ j i') (hji : j ≤ i) (hii : i ≤ i') : AnchorAt ψ j i :=
  ⟨hji, h.2.1, fun k h1 h2 => h.2.2 k h1 (Nat.le_trans h2 hii)⟩

/-- T2: the start is `j` exactly where `j` is the latest definite rise with ψ known since. -/
theorem startAt_some_iff (i j : Nat) : startAt op ψ i = .ok (some j) ↔ AnchorAt ψ j i := by
  constructor
  · intro h
    induction i with
    | zero =>
      simp only [startAt, startStep] at h
      cases hv : ψ[0]!.v <;> simp [hv] at h
    | succ i ih =>
      simp only [startAt, startStep] at h
      cases hv : ψ[i + 1]!.v <;> simp only [hv, Nat.add_one_ne_zero, if_false, Nat.add_sub_cancel] at h
      · cases hp : ψ[i]!.v <;> simp only [hp] at h
        · obtain ⟨h1, h2, h3⟩ := ih h
          refine ⟨by omega, h2, fun k hk1 hk2 => ?_⟩
          rcases Nat.lt_succ_iff_lt_or_eq.mp (Nat.lt_succ_of_le hk2) with hk | hk
          · exact h3 k hk1 (by omega)
          · subst hk; refine ⟨by simp [hv], fun ⟨_, hf, _⟩ => ?_⟩
            simp [hp] at hf
        · cases h
          exact ⟨Nat.le_refl _, ⟨by omega, by simpa using hp, hv⟩, fun k h1 h2 => absurd h2 (by omega)⟩
        · cases h
      · obtain ⟨h1, h2, h3⟩ := ih h
        refine ⟨by omega, h2, fun k hk1 hk2 => ?_⟩
        rcases Nat.lt_succ_iff_lt_or_eq.mp (Nat.lt_succ_of_le hk2) with hk | hk
        · exact h3 k hk1 (by omega)
        · subst hk; exact ⟨by simp [hv], fun ⟨_, _, ht⟩ => by simp [hv] at ht⟩
      · cases h
  · intro ⟨hji, hr, hk⟩
    induction i with
    | zero => exact absurd hr.1 (by omega)
    | succ m ih =>
      rcases Nat.lt_succ_iff_lt_or_eq.mp (Nat.lt_succ_of_le hji) with hlt | heq
      · have ih' := ih (by omega) (fun k h1 h2 => hk k h1 (by omega))
        obtain ⟨hu, hnr⟩ := hk (m + 1) (by omega) (Nat.le_refl _)
        simp only [startAt, startStep, Nat.add_one_ne_zero, if_false, Nat.add_sub_cancel]
        cases hv : ψ[m + 1]!.v with
        | u => exact absurd hv hu
        | f => exact ih'
        | t =>
          have hp : ψ[m]!.v = .t := by
            cases hp : ψ[m]!.v with
            | t => rfl
            | f => exact absurd ⟨by omega, by simpa using hp, hv⟩ hnr
            | u =>
              rcases Nat.lt_or_eq_of_le (Nat.le_of_lt_succ hlt) with h | h
              · exact absurd hp (hk m h (by omega)).1
              · subst h; have := hr.2.2; rw [hp] at this; cases this
          simp only [hp]; exact ih'
      · subst heq
        obtain ⟨_, hf, ht⟩ := hr
        simp only [startAt, startStep, ht, Nat.add_one_ne_zero, if_false, Nat.add_sub_cancel]
        simp only [Nat.add_sub_cancel] at hf
        simp [hf]

/-- T3: no start observed exactly where ψ has been false at every observation so far. -/
theorem startAt_none_iff (i : Nat) : startAt op ψ i = .ok none ↔ ∀ k, k ≤ i → ψ[k]!.v = .f := by
  constructor
  · intro h
    induction i with
    | zero =>
      intro k hk; have hk0 : k = 0 := by omega
      subst hk0
      simp only [startAt, startStep] at h
      cases hv : ψ[0]!.v <;> simp [hv] at h ⊢
    | succ i ih =>
      simp only [startAt, startStep] at h
      cases hv : ψ[i + 1]!.v <;> simp only [hv, Nat.add_one_ne_zero, if_false, Nat.add_sub_cancel] at h
      · cases hp : ψ[i]!.v <;> simp only [hp] at h
        · have := ih h i (Nat.le_refl _); rw [hp] at this; cases this
        · cases h
        · cases h
      · intro k hk
        rcases Nat.lt_succ_iff_lt_or_eq.mp (Nat.lt_succ_of_le hk) with hk' | hk'
        · exact ih h k (by omega)
        · subst hk'; exact hv
      · cases h
  · intro h
    induction i with
    | zero => simp [startAt, startStep, h 0 (Nat.le_refl _)]
    | succ i ih =>
      simp only [startAt, startStep, h (i + 1) (Nat.le_refl _)]
      exact ih (fun k hk => h k (by omega))

/-- A run of true values reaching the first observation, with ψ known and rising nowhere since,
    leaves the start truncated: the onset may lie before the recording. -/
theorem startAt_truncated (i : Nat) (h0 : ψ[0]!.v = .t)
    (h : ∀ k, 0 < k → k ≤ i → ψ[k]!.v ≠ .u ∧ ¬ RisesAt ψ k) :
    startAt op ψ i = .error (.windowTruncated op) := by
  induction i with
  | zero => simp [startAt, startStep, h0]
  | succ m ih =>
    have ih' := ih (fun k h1 h2 => h k h1 (by omega))
    obtain ⟨hu, hnr⟩ := h (m + 1) (by omega) (Nat.le_refl _)
    simp only [startAt, startStep, Nat.add_one_ne_zero, if_false, Nat.add_sub_cancel]
    cases hv : ψ[m + 1]!.v with
    | u => exact absurd hv hu
    | f => exact ih'
    | t =>
      have hp : ψ[m]!.v = .t := by
        cases hp : ψ[m]!.v with
        | t => rfl
        | f => exact absurd ⟨by omega, by simpa using hp, hv⟩ hnr
        | u =>
          cases m with
          | zero => rw [h0] at hp; cases hp
          | succ m' => exact absurd hp (h (m' + 1) (by omega) (by omega)).1
      simp only [hp]; exact ih'

theorem startAt_congr {ψ' : Array R} (i : Nat) (h : ∀ k, k ≤ i → ψ[k]! = ψ'[k]!) :
    startAt op ψ i = startAt op ψ' i := by
  induction i with
  | zero => simp only [startAt, startStep, h 0 (Nat.le_refl _)]
  | succ m ih =>
    simp only [startAt, startStep, Nat.add_one_ne_zero, if_false, Nat.add_sub_cancel,
      h (m + 1) (Nat.le_refl _), h m (by omega), ih (fun k hk => h k (by omega))]

end Start

-- ---------------------------------------------------------------------------------------------
-- The running state
-- ---------------------------------------------------------------------------------------------
section RunState
variable {times : Array Q} {rate : Array (Option Q)} {g : Q}

theorem lastWide_any_iff (i j : Nat) :
    (runAt times rate g i).lastWide.any (j ≤ ·) = true ↔
      ∃ k, j ≤ k ∧ k ≤ i ∧ k ≠ 0 ∧ Q.gt (dt times k) g = true := by
  induction i with
  | zero => simp [runAt, runStep, Run.init]; intro k _ hk h; omega
  | succ i ih =>
    simp only [runAt, runStep]
    by_cases hw : Q.gt (dt times (i + 1)) g = true
    · have hc : (i + 1 != 0 && Q.gt (dt times (i + 1)) g) = true := by simp [hw]
      rw [if_pos hc]
      simp only [Option.any_some, decide_eq_true_eq]
      constructor
      · intro h; exact ⟨i + 1, h, Nat.le_refl _, by omega, hw⟩
      · intro ⟨k, h1, h2, _, _⟩; omega
    · simp only [hw, Bool.and_false, Bool.false_eq_true, if_false]
      rw [ih]
      constructor
      · intro ⟨k, h1, h2, h3, h4⟩; exact ⟨k, h1, by omega, h3, h4⟩
      · intro ⟨k, h1, h2, h3, h4⟩
        rcases Nat.lt_succ_iff_lt_or_eq.mp (Nat.lt_succ_of_le h2) with hk | hk
        · exact ⟨k, h1, by omega, h3, h4⟩
        · subst hk; exact absurd h4 hw

theorem lastMissing_any_iff (i j : Nat) :
    (runAt times rate g i).lastMissing.any (j < ·) = true ↔ ∃ k, j < k ∧ k ≤ i ∧ rate[k]! = none := by
  induction i with
  | zero =>
    simp only [runAt, runStep]
    cases hr : rate[0]! <;> simp [Run.init] <;> intro k h1 h2 <;> omega
  | succ i ih =>
    simp only [runAt, runStep]
    cases hr : rate[i + 1]! with
    | none =>
      simp only [Option.isNone_none, if_true, Option.any_some, decide_eq_true_eq]
      constructor
      · intro h; exact ⟨i + 1, h, Nat.le_refl _, hr⟩
      · intro ⟨k, h1, h2, _⟩; omega
    | some ω =>
      simp only [Option.isNone_some, Bool.false_eq_true, if_false]
      rw [ih]
      constructor
      · intro ⟨k, h1, h2, h3⟩; exact ⟨k, h1, by omega, h3⟩
      · intro ⟨k, h1, h2, h3⟩
        rcases Nat.lt_succ_iff_lt_or_eq.mp (Nat.lt_succ_of_le h2) with hk | hk
        · exact ⟨k, h1, by omega, h3⟩
        · subst hk; rw [hr] at h3; cases h3

theorem integral_le (j i : Nat) (h : i ≤ j) : integral times rate j i = some 0 := by
  cases i with
  | zero => rfl
  | succ i => simp [integral, h]

/-- With every rate of `(j, i]` present, the specification is the difference of the running sums. -/
theorem integral_eq_sum (j i : Nat) (hji : j ≤ i) (hr : ∀ k, j < k → k ≤ i → (rate[k]!).isSome) :
    integral times rate j i = some ((runAt times rate g i).sum.val - (runAt times rate g j).sum.val) := by
  induction i with
  | zero =>
    have : j = 0 := by omega
    subst this; simp only [integral]; congr 1; grind
  | succ i ih =>
    rcases Nat.lt_succ_iff_lt_or_eq.mp (Nat.lt_succ_of_le hji) with hlt | heq
    · have hj : ¬ (i + 1 ≤ j) := by omega
      have ih' := ih (by omega) (fun k h1 h2 => hr k h1 (by omega))
      obtain ⟨ω, hω⟩ := Option.isSome_iff_exists.mp (hr (i + 1) hlt (Nat.le_refl _))
      simp only [integral, hj, if_false, ih', hω, Option.bind_eq_bind, Option.bind_some, Option.pure_def]
      simp only [runAt, runStep, hω, dt, Nat.add_one_ne_zero, if_false, Nat.add_sub_cancel]
      rw [Q.val_add, Q.val_mul, Q.val_sub]
      congr 1
      grind
    · subst heq; rw [integral_le _ _ (Nat.le_refl _)]; congr 1; grind

theorem runAt_congr {times' : Array Q} {rate' : Array (Option Q)} (i : Nat)
    (ht : ∀ k, k ≤ i → times[k]! = times'[k]!) (hr : ∀ k, k ≤ i → rate[k]! = rate'[k]!) :
    runAt times rate g i = runAt times' rate' g i := by
  induction i with
  | zero => simp only [runAt, runStep, dt, hr 0 (Nat.le_refl _), if_true]
  | succ m ih =>
    simp only [runAt, runStep, dt, Nat.add_one_ne_zero, if_false, Nat.add_sub_cancel,
      hr (m + 1) (Nat.le_refl _), ht (m + 1) (Nat.le_refl _), ht m (by omega),
      ih (fun k hk => ht k (by omega)) (fun k hk => hr k (by omega))]

end RunState

-- ---------------------------------------------------------------------------------------------
-- The theorems of the operator. `F` below is `sinceRiseIntegralAll times rate g op missing ψ`.
-- ---------------------------------------------------------------------------------------------
section Operator
variable {times : Array Q} {rate : Array (Option Q)} {g : Q} {op : String} {missing : UnknownReason} {ψ : Array R}

/-- T1: one value per observation. -/
theorem size_sinceRiseIntegralAll : (sinceRiseIntegralAll times rate g op missing ψ).size = ψ.size := by
  unfold sinceRiseIntegralAll; split <;> simp

theorem get_pos (hg : Q.lt Q.zero g = true) (i : Nat) (hi : i < ψ.size) :
    (sinceRiseIntegralAll times rate g op missing ψ)[i]! =
      match startAt op ψ i with
      | .error e => .error e
      | .ok none => .error (.windowTruncated op)
      | .ok (some j) =>
        if (runAt times rate g i).lastWide.any (j ≤ ·) then .error (.samplingGap op)
        else if (runAt times rate g i).lastMissing.any (j < ·) then .error missing
        else .ok (Q.sub (runAt times rate g i).sum (runAt times rate g j).sum) := by
  unfold sinceRiseIntegralAll
  rw [if_pos hg, getElem!_pos _ _ (by simpa using hi)]
  simp only [Array.getElem_map, Array.getElem_range, valueAt]
  rw [runStartAll_get op ψ i hi, runs_get times rate g _ i hi]
  cases hs : startAt op ψ i with
  | error e => rfl
  | ok o =>
    cases o with
    | none => rfl
    | some j =>
      simp only [runs_get times rate g _ j (Nat.lt_of_le_of_lt ((startAt_some_iff i j).mp hs).1 hi)]

/-- Under a step bound that is not positive, every observation is unknown, malformed. -/
theorem not_positive (hg : Q.lt Q.zero g = false) (i : Nat) (hi : i < ψ.size) :
    (sinceRiseIntegralAll times rate g op missing ψ)[i]! = .error (.malformed s!"{op} step bound is not positive") := by
  unfold sinceRiseIntegralAll
  rw [if_neg (by simp [hg]), getElem!_pos _ _ (by simpa using hi)]
  simp

private theorem gap_of_le {j i : Nat}
    (hgap : ∀ k, j ≤ k → k ≤ i → Q.le (Q.sub times[k]! times[k - 1]!) g = true) :
    (runAt times rate g i).lastWide.any (j ≤ ·) = false := by
  cases h : (runAt times rate g i).lastWide.any (j ≤ ·) with
  | false => rfl
  | true =>
    obtain ⟨k, h1, h2, h3, h4⟩ := (lastWide_any_iff i j).mp h
    have := (Q.le_iff_not_gt _ _).mp (hgap k h1 h2)
    simp only [dt, h3, if_false] at h4
    rw [this] at h4; cases h4

private theorem rate_of_some {j i : Nat} (hrate : ∀ k, j < k → k ≤ i → (rate[k]!).isSome) :
    (runAt times rate g i).lastMissing.any (j < ·) = false := by
  cases h : (runAt times rate g i).lastMissing.any (j < ·) with
  | false => rfl
  | true =>
    obtain ⟨k, h1, h2, h3⟩ := (lastMissing_any_iff i j).mp h
    have := hrate k h1 h2; rw [h3] at this; cases this

/-- T4: at an observed start with a positive bound, intervals within the bound from the one ending
    at the start, and every rate since present, the value is decided and is the discrete sum. -/
theorem at_anchor (hg : Q.lt Q.zero g = true) (i j : Nat) (hi : i < ψ.size) (ha : AnchorAt ψ j i)
    (hgap : ∀ k, j ≤ k → k ≤ i → Q.le (Q.sub times[k]! times[k - 1]!) g = true)
    (hrate : ∀ k, j < k → k ≤ i → (rate[k]!).isSome) :
    ∃ q, (sinceRiseIntegralAll times rate g op missing ψ)[i]! = .ok q ∧ integral times rate j i = some q.val := by
  rw [get_pos hg i hi, (startAt_some_iff i j).mpr ha]
  simp only [gap_of_le hgap, rate_of_some hrate, Bool.false_eq_true, if_false]
  exact ⟨_, rfl, by rw [integral_eq_sum j i ha.1 hrate, Q.val_sub]⟩

/-- The value at a start whose bracket interval is within the bound is zero. -/
theorem zero_at_anchor (hg : Q.lt Q.zero g = true) (j : Nat) (hj : j < ψ.size) (ha : AnchorAt ψ j j)
    (hgap : Q.le (Q.sub times[j]! times[j - 1]!) g = true) :
    (sinceRiseIntegralAll times rate g op missing ψ)[j]! = .ok Q.zero := by
  rw [get_pos hg j hj, (startAt_some_iff j j).mpr ha]
  have hw := gap_of_le (times := times) (rate := rate) (j := j) (i := j)
    (fun k h1 h2 => by have : k = j := by omega
                       subst this; exact hgap)
  have hm := rate_of_some (times := times) (rate := rate) (g := g) (j := j) (i := j)
    (fun k h1 h2 => absurd h2 (by omega))
  simp only [hw, hm, Bool.false_eq_true, if_false, Q.sub_self]

/-- T5: a decided value comes from a positive bound and an observed start, intervals within the
    bound from the one ending at the start, every rate since present, and is the discrete sum. -/
theorem decided_anchored (i : Nat) (hi : i < ψ.size) (q : Q)
    (h : (sinceRiseIntegralAll times rate g op missing ψ)[i]! = .ok q) :
    Q.lt Q.zero g = true ∧ ∃ j, AnchorAt ψ j i ∧
      (∀ k, j ≤ k → k ≤ i → Q.le (Q.sub times[k]! times[k - 1]!) g = true) ∧
      (∀ k, j < k → k ≤ i → (rate[k]!).isSome) ∧
      integral times rate j i = some q.val := by
  cases hg : Q.lt Q.zero g with
  | false => rw [not_positive hg i hi] at h; cases h
  | true =>
    refine ⟨rfl, ?_⟩
    rw [get_pos hg i hi] at h
    cases hs : startAt op ψ i with
    | error e => simp only [hs] at h; cases h
    | ok o =>
      cases o with
      | none => simp only [hs] at h; cases h
      | some j =>
        simp only [hs] at h
        have ha := (startAt_some_iff i j).mp hs
        cases hw : (runAt times rate g i).lastWide.any (j ≤ ·) with
        | true => simp [hw] at h
        | false =>
          cases hm : (runAt times rate g i).lastMissing.any (j < ·) with
          | true => simp [hw, hm] at h
          | false =>
            simp only [hw, hm, Bool.false_eq_true, if_false, Except.ok.injEq] at h
            have hgap : ∀ k, j ≤ k → k ≤ i → Q.le (Q.sub times[k]! times[k - 1]!) g = true := by
              intro k h1 h2
              have hk0 : k ≠ 0 := by have := ha.2.1.1; omega
              cases hgt : Q.gt (dt times k) g with
              | false => simp only [dt, hk0, if_false] at hgt; exact (Q.le_iff_not_gt _ _).mpr hgt
              | true =>
                have := (lastWide_any_iff (rate := rate) i j).mpr ⟨k, h1, h2, hk0, hgt⟩
                rw [hw] at this; cases this
            have hrate : ∀ k, j < k → k ≤ i → (rate[k]!).isSome := by
              intro k h1 h2
              cases hr : rate[k]! with
              | some _ => rfl
              | none =>
                have := (lastMissing_any_iff (times := times) (g := g) i j).mpr ⟨k, h1, h2, hr⟩
                rw [hm] at this; cases this
            refine ⟨j, ha, hgap, hrate, ?_⟩
            rw [integral_eq_sum j i ha.1 hrate, ← h, Q.val_sub]

/-- T6: ψ false at every observation so far: unknown, truncated. -/
theorem none_observed (hg : Q.lt Q.zero g = true) (i : Nat) (hi : i < ψ.size) (h : ∀ k, k ≤ i → ψ[k]!.v = .f) :
    (sinceRiseIntegralAll times rate g op missing ψ)[i]! = .error (.windowTruncated op) := by
  rw [get_pos hg i hi, (startAt_none_iff i).mpr h]

/-- T6: ψ true at the first observation and known with no definite rise since: unknown, truncated. -/
theorem onset_before_recording (hg : Q.lt Q.zero g = true) (i : Nat) (hi : i < ψ.size) (h0 : ψ[0]!.v = .t)
    (h : ∀ k, 0 < k → k ≤ i → ψ[k]!.v ≠ .u ∧ ¬ RisesAt ψ k) :
    (sinceRiseIntegralAll times rate g op missing ψ)[i]! = .error (.windowTruncated op) := by
  rw [get_pos hg i hi, startAt_truncated i h0 h]

/-- T6: no observed start: unknown. -/
theorem no_anchor_unknown (i : Nat) (hi : i < ψ.size) (h : ¬ ∃ j, AnchorAt ψ j i) :
    ∃ e, (sinceRiseIntegralAll times rate g op missing ψ)[i]! = .error e := by
  cases hd : (sinceRiseIntegralAll times rate g op missing ψ)[i]! with
  | error e => exact ⟨e, rfl⟩
  | ok q => obtain ⟨_, j, ha, _⟩ := decided_anchored i hi q hd; exact absurd ⟨j, ha⟩ h

/-- T7: an interval longer than the bound ending at an observation of `[j, i]`: a sampling gap. -/
theorem wide_interval (hg : Q.lt Q.zero g = true) (i j : Nat) (hi : i < ψ.size) (ha : AnchorAt ψ j i)
    (hk : ∃ k, j ≤ k ∧ k ≤ i ∧ Q.gt (Q.sub times[k]! times[k - 1]!) g = true) :
    (sinceRiseIntegralAll times rate g op missing ψ)[i]! = .error (.samplingGap op) := by
  rw [get_pos hg i hi, (startAt_some_iff i j).mpr ha]
  obtain ⟨k, h1, h2, h3⟩ := hk
  have hk0 : k ≠ 0 := by have := ha.2.1.1; omega
  have : (runAt times rate g i).lastWide.any (j ≤ ·) = true :=
    (lastWide_any_iff i j).mpr ⟨k, h1, h2, hk0, by simpa [dt, hk0] using h3⟩
  simp only [this, if_true]

/-- T7: the bracket of the start (the interval ending at it) longer than the bound: a sampling gap. -/
theorem bracket_wide (hg : Q.lt Q.zero g = true) (i j : Nat) (hi : i < ψ.size) (ha : AnchorAt ψ j i)
    (hb : Q.gt (Q.sub times[j]! times[j - 1]!) g = true) :
    (sinceRiseIntegralAll times rate g op missing ψ)[i]! = .error (.samplingGap op) :=
  wide_interval hg i j hi ha ⟨j, Nat.le_refl _, ha.1, hb⟩

/-- T7: a missing rate since the start, with every interval within the bound: `missing`. -/
theorem missing_rate (hg : Q.lt Q.zero g = true) (i j : Nat) (hi : i < ψ.size) (ha : AnchorAt ψ j i)
    (hgap : ∀ k, j ≤ k → k ≤ i → Q.le (Q.sub times[k]! times[k - 1]!) g = true)
    (hk : ∃ k, j < k ∧ k ≤ i ∧ rate[k]! = none) :
    (sinceRiseIntegralAll times rate g op missing ψ)[i]! = .error missing := by
  rw [get_pos hg i hi, (startAt_some_iff i j).mpr ha]
  have : (runAt times rate g i).lastMissing.any (j < ·) = true := (lastMissing_any_iff i j).mpr hk
  simp only [gap_of_le hgap, this, Bool.false_eq_true, if_false, if_true]

/-- T8: the value at `i` depends only on the times, rates and ψ at observations `≤ i`. -/
theorem causal {times' : Array Q} {rate' : Array (Option Q)} {ψ' : Array R} (i : Nat)
    (hi : i < ψ.size) (hi' : i < ψ'.size)
    (ht : ∀ k, k ≤ i → times[k]! = times'[k]!) (hr : ∀ k, k ≤ i → rate[k]! = rate'[k]!)
    (hψ : ∀ k, k ≤ i → ψ[k]! = ψ'[k]!) :
    (sinceRiseIntegralAll times rate g op missing ψ)[i]! = (sinceRiseIntegralAll times' rate' g op missing ψ')[i]! := by
  cases hg : Q.lt Q.zero g with
  | false => rw [not_positive hg i hi, not_positive hg i hi']
  | true =>
    rw [get_pos hg i hi, get_pos hg i hi', startAt_congr i hψ, runAt_congr i ht hr]
    cases hs : startAt op ψ' i with
    | error e => rfl
    | ok o =>
      cases o with
      | none => rfl
      | some j =>
        have hj : j ≤ i := ((startAt_some_iff i j).mp hs).1
        simp only [runAt_congr j (fun k hk => ht k (by omega)) (fun k hk => hr k (by omega))]

/-- T9: the sum splits at any intermediate observation. -/
theorem integral_split (j m i : Nat) (hjm : j ≤ m) (hmi : m ≤ i) :
    integral times rate j i = (do let a ← integral times rate j m; let b ← integral times rate m i; pure (a + b)) := by
  induction i with
  | zero =>
    have h1 : m = 0 := by omega
    have h2 : j = 0 := by omega
    subst h1; subst h2; simp [integral, Rat.add_zero]
  | succ i ih =>
    rcases Nat.lt_succ_iff_lt_or_eq.mp (Nat.lt_succ_of_le hmi) with hlt | heq
    · have hj : ¬ (i + 1 ≤ j) := by omega
      have hm : ¬ (i + 1 ≤ m) := by omega
      simp only [integral, hj, hm, if_false, ih (by omega)]
      cases integral times rate j m <;> cases integral times rate m i <;> cases rate[i + 1]! <;>
        simp [Rat.add_assoc]
    · subst heq
      rw [integral_le _ _ (Nat.le_refl _)]
      cases integral times rate j (i + 1) <;> simp [Rat.add_zero]

/-- T9: between two decided observations of one start, the sum is the difference of the values. -/
theorem accumulates (i i' j : Nat) (hi' : i' < ψ.size) (ha : AnchorAt ψ j i') (hji : j ≤ i) (hii : i ≤ i')
    (a b : Q) (h1 : (sinceRiseIntegralAll times rate g op missing ψ)[i]! = .ok a)
    (h2 : (sinceRiseIntegralAll times rate g op missing ψ)[i']! = .ok b) :
    integral times rate i i' = some (b.val - a.val) := by
  obtain ⟨_, j₁, ha₁, _, _, hI₁⟩ := decided_anchored i (Nat.lt_of_le_of_lt hii hi') a h1
  obtain ⟨_, j₂, ha₂, _, _, hI₂⟩ := decided_anchored i' hi' b h2
  have e₁ : j₁ = j := by
    have := ((startAt_some_iff (op := op) i j₁).mpr ha₁).symm.trans ((startAt_some_iff i j).mpr (ha.mono hji hii))
    cases this; rfl
  have e₂ : j₂ = j := by
    have := ((startAt_some_iff (op := op) i' j₂).mpr ha₂).symm.trans ((startAt_some_iff i' j).mpr ha)
    cases this; rfl
  rw [e₁] at hI₁; rw [e₂] at hI₂
  have hs := integral_split (times := times) (rate := rate) j i i' hji hii
  rw [hI₂, hI₁] at hs
  cases hx : integral times rate i i' with
  | none => rw [hx] at hs; simp at hs
  | some x =>
    rw [hx] at hs
    simp only [Option.bind_eq_bind, Option.bind_some, Option.pure_def, Option.some.injEq] at hs
    congr 1; grind

end Operator

end Accumulate
end TrafficSpec
