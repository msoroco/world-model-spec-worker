/-
  TrafficSpec.Core.Foundations.SampledDuration
  The time a condition held in the window behind each observation, read from the trace's samples,
  as a lower and an upper bound, for the whole trace in one forward pass; and its specification
  over Lean's `Rat`.

  The sampled convention is `Accumulate.dt`'s: observation `k ≥ 1` stands for its cell
  `(t_{k−1}, t_k]`, the first observation for nothing. The window behind observation `i` of length
  `w` is `(t_i − w, t_i]`; a cell crossing its start counts for the part inside it. A cell counts
  toward both bounds where the condition is true at its observation and the cell is no longer than
  the step bound; toward neither where the condition is false there and the cell is no longer than
  the step bound; toward the upper bound only where the condition is unknown there (an unobserved
  atom, a bound road user missing inside its own span) or the cell is longer than the step bound.
  The part of the window before the first observation counts toward the upper bound only.

  The step bound is the longest cell integrated as one sample: a sampling standard, not evidence
  that no observation is missing. The result is the duration the samples show, not a proof of the
  duration in continuous time.

  Proved here, for observation times in order:
  - `bounds_val`: the computed bounds are the specification's (`inWindow` of the cells' counts);
  - `completion_within`: every completion of the samples (on each cell the time the condition held,
    growing no faster than time, all of it where the cell counts toward both bounds and none where
    it counts toward neither; before the first observation anything that grows no faster than time)
    held, in every window, a time within the bounds;
  - `worst_at_observation`: every window ending between the first and the last observation counts,
    toward either bound, at most what the window ending at some observation counts, so judging the
    windows that end at observations decides every window;
  - `agrees_integral`: where the window starts at an observation and every cell in it is decided,
    both bounds are `Accumulate.integral` of the condition's indicator.
-/
import TrafficSpec.Core.Foundations.Accumulate

namespace TrafficSpec

theorem Q.le_iff_val (a b : Q) : Q.le a b = true ↔ a.val ≤ b.val := by
  rw [Rat.le_iff_sub_nonneg, ← Accumulate.Q.val_sub]
  unfold Q.sub
  rw [Accumulate.Q.val_mk' _ _ (Nat.mul_pos b.den_pos a.den_pos), ← Rat.divInt_ofNat,
    Rat.divInt_nonneg_iff_of_pos_right (by have := Nat.mul_pos b.den_pos a.den_pos; omega)]
  unfold Q.le
  simp [Int.sub_nonneg]

theorem Q.lt_iff_val (a b : Q) : Q.lt a b = true ↔ a.val < b.val := by
  rw [← Rat.not_le, ← Q.le_iff_val]
  unfold Q.lt Q.le
  simp [Int.not_le]

theorem Q.val_zero : Q.zero.val = 0 := by simp [Q.val, Q.zero, Q.ofInt]

namespace SampledDuration

-- ---------------------------------------------------------------------------------------------
-- The specification
-- ---------------------------------------------------------------------------------------------
section Spec

/-- `x` held within `[a, b]`. -/
def clamp (x a b : Rat) : Rat := if x ≤ a then a else if x ≤ b then x else b

/-- A cumulative count at instant `x`: cell `k` (`1 ≤ k ≤ m`) counts `f k` of `x` held within it,
    the part before the first observation `f0` of `x` held below it. -/
def cum (t : Nat → Rat) (f : Nat → Rat → Rat) (f0 : Rat → Rat) (x : Rat) : Nat → Rat
  | 0 => f0 (if x ≤ t 0 then x else t 0)
  | m + 1 => cum t f f0 x m + f (m + 1) (clamp x (t m) (t (m + 1)))

/-- The count in the window `(τ − w, τ]`, over the cells of the observations `0 … N`. -/
def inWindow (t : Nat → Rat) (f : Nat → Rat → Rat) (f0 : Rat → Rat) (N : Nat) (w τ : Rat) : Rat :=
  cum t f f0 τ N - cum t f f0 (τ - w) N

/-- One cell's count: all of its elapsed time where `b`, none otherwise. -/
def lin (t : Nat → Rat) (b : Nat → Bool) (k : Nat) (y : Rat) : Rat := if b k then y - t (k - 1) else 0

/-- Observation times in order up to `N`. -/
def Sorted (t : Nat → Rat) (N : Nat) : Prop := ∀ a b, a ≤ b → b ≤ N → t a ≤ t b

/-- Σ_{k=1}^{m} of the cells' whole counts where `b`. -/
def sumR (t : Nat → Rat) (b : Nat → Bool) : Nat → Rat
  | 0 => 0
  | m + 1 => sumR t b m + (if b (m + 1) then t (m + 1) - t m else 0)

theorem clamp_mono {x y a b : Rat} (hab : a ≤ b) (h : x ≤ y) : clamp x a b ≤ clamp y a b := by
  unfold clamp; split <;> split <;> (try split) <;> (try split) <;> grind

theorem clamp_mem (x a b : Rat) (hab : a ≤ b) : a ≤ clamp x a b ∧ clamp x a b ≤ b := by
  unfold clamp; split <;> (try split) <;> grind

/-- A count whose cells and whose part before the first observation never decrease never
    decreases. -/
theorem cum_mono (t : Nat → Rat) (f : Nat → Rat → Rat) (f0 : Rat → Rat) (N : Nat) (ht : Sorted t N)
    (hf : ∀ k, 1 ≤ k → k ≤ N → ∀ y z, t (k - 1) ≤ y → y ≤ z → z ≤ t k → f k y ≤ f k z)
    (hf0 : ∀ y z, y ≤ z → z ≤ t 0 → f0 y ≤ f0 z) :
    ∀ m, m ≤ N → ∀ x y, x ≤ y → cum t f f0 x m ≤ cum t f f0 y m := by
  intro m
  induction m with
  | zero =>
    intro _ x y hxy
    simp only [cum]
    apply hf0
    · split <;> split <;> grind
    · split <;> grind
  | succ m ih =>
    intro hm x y hxy
    simp only [cum]
    have h1 := ih (by omega) x y hxy
    have hab : t m ≤ t (m + 1) := ht m (m + 1) (by omega) hm
    have hc := clamp_mono (a := t m) (b := t (m + 1)) hab hxy
    have hx := clamp_mem x (t m) (t (m + 1)) hab
    have hy := clamp_mem y (t m) (t (m + 1)) hab
    have h2 := hf (m + 1) (by omega) hm (clamp x (t m) (t (m + 1))) (clamp y (t m) (t (m + 1)))
      (by simpa using hx.1) hc (by simpa using hy.2)
    grind

theorem cum_sub (t : Nat → Rat) (f g : Nat → Rat → Rat) (f0 g0 : Rat → Rat) (x : Rat) :
    ∀ m, cum t (fun k y => f k y - g k y) (fun y => f0 y - g0 y) x m = cum t f f0 x m - cum t g g0 x m := by
  intro m
  induction m with
  | zero => simp [cum]
  | succ m ih => simp only [cum, ih]; grind

/-- Every cell and the part before the first observation counting all of their time: the count at
    `x` is `x` capped at the last observation. -/
theorem cum_id (t : Nat → Rat) (N : Nat) (ht : Sorted t N) (x : Rat) :
    ∀ m, m ≤ N → cum t (fun k y => y - t (k - 1)) (fun y => y) x m = if x ≤ t m then x else t m := by
  intro m
  induction m with
  | zero => intro _; simp [cum]
  | succ m ih =>
    intro hm
    simp only [cum, ih (by omega), Nat.add_sub_cancel]
    have hab : t m ≤ t (m + 1) := ht m (m + 1) (by omega) hm
    unfold clamp
    split <;> split <;> (try split) <;> (try split) <;> grind

/-- A count whose cells and whose part before the first observation each grow no faster than time
    grows no faster than time. -/
theorem cum_lip (t : Nat → Rat) (f : Nat → Rat → Rat) (f0 : Rat → Rat) (N : Nat) (ht : Sorted t N)
    (hf : ∀ k, 1 ≤ k → k ≤ N → ∀ y z, t (k - 1) ≤ y → y ≤ z → z ≤ t k → f k z - f k y ≤ z - y)
    (hf0 : ∀ y z, y ≤ z → z ≤ t 0 → f0 z - f0 y ≤ z - y) (x y : Rat) (hxy : x ≤ y) :
    cum t f f0 y N - cum t f f0 x N ≤ y - x := by
  have hm := cum_mono t (fun k y => (y - t (k - 1)) - f k y) (fun y => y - f0 y) N ht
    (fun k h1 h2 a b ha hab hb => by have := hf k h1 h2 a b ha hab hb; grind)
    (fun a b hab hb => by have := hf0 a b hab hb; grind) N (Nat.le_refl _) x y hxy
  rw [cum_sub, cum_sub, cum_id t N ht x N (Nat.le_refl _), cum_id t N ht y N (Nat.le_refl _)] at hm
  split at hm <;> split at hm <;> grind

/-- Between two instants of cell `i` only that cell's count changes. -/
theorem cum_cell (t : Nat → Rat) (f : Nat → Rat → Rat) (f0 : Rat → Rat) (N : Nat) (ht : Sorted t N)
    (i : Nat) (hi1 : 1 ≤ i) (hiN : i ≤ N) (x y : Rat) (hx : t (i - 1) ≤ x) (hxi : x ≤ t i)
    (hy : t (i - 1) ≤ y) (hyi : y ≤ t i) :
    ∀ m, m ≤ N → cum t f f0 y m - cum t f f0 x m = if i ≤ m then f i y - f i x else 0 := by
  intro m
  induction m with
  | zero =>
    intro _
    have h0 : t 0 ≤ t (i - 1) := ht 0 (i - 1) (by omega) (by omega)
    simp only [cum]
    have e1 : (if x ≤ t 0 then x else t 0) = t 0 := by split <;> grind
    have e2 : (if y ≤ t 0 then y else t 0) = t 0 := by split <;> grind
    rw [e1, e2, if_neg (by omega)]; grind
  | succ m ih =>
    intro hm
    have ih' := ih (by omega)
    simp only [cum]
    by_cases him : i = m + 1
    · subst him
      have hx' : t m ≤ x := by simpa using hx
      have hy' : t m ≤ y := by simpa using hy
      have e1 : clamp x (t m) (t (m + 1)) = x := by unfold clamp; split <;> (try split) <;> grind
      have e2 : clamp y (t m) (t (m + 1)) = y := by unfold clamp; split <;> (try split) <;> grind
      rw [e1, e2, if_pos (Nat.le_refl _)]; rw [if_neg (by omega)] at ih'; grind
    · by_cases hlt : i ≤ m
      · have h1 : t i ≤ t m := ht i m hlt (by omega)
        have e1 : clamp x (t m) (t (m + 1)) = t m := by unfold clamp; split <;> grind
        have e2 : clamp y (t m) (t (m + 1)) = t m := by unfold clamp; split <;> grind
        rw [e1, e2, if_pos (by omega)]; rw [if_pos hlt] at ih'; grind
      · have h1 : t (m + 1) ≤ t (i - 1) := ht (m + 1) (i - 1) (by omega) (by omega)
        have h2 : t m ≤ t (m + 1) := ht m (m + 1) (by omega) hm
        have e1 : clamp x (t m) (t (m + 1)) = t (m + 1) := by unfold clamp; split <;> (try split) <;> grind
        have e2 : clamp y (t m) (t (m + 1)) = t (m + 1) := by unfold clamp; split <;> (try split) <;> grind
        rw [e1, e2, if_neg (by omega)]; rw [if_neg hlt] at ih'; grind

/-- Every instant from the first to the last observation is the first observation or lies in a
    cell. -/
theorem cell_of (t : Nat → Rat) (N : Nat) (ht : Sorted t N) (τ : Rat) (h0 : t 0 ≤ τ) (hN : τ ≤ t N) :
    τ = t 0 ∨ ∃ i, 1 ≤ i ∧ i ≤ N ∧ t (i - 1) ≤ τ ∧ τ ≤ t i := by
  induction N with
  | zero => left; grind
  | succ N ih =>
    by_cases h : τ ≤ t N
    · rcases ih (fun a b hab hb => ht a b hab (by omega)) h with e | ⟨i, h1, h2, h3, h4⟩
      · exact Or.inl e
      · exact Or.inr ⟨i, h1, by omega, h3, h4⟩
    · exact Or.inr ⟨N + 1, by omega, Nat.le_refl _, by simp; grind, hN⟩

/-- The worst window ends at an observation: where every cell counts all or none of its elapsed
    time, and the part before the first observation grows by at least nothing and at most the time
    elapsed, every window ending between the first and the last observation counts at most what the
    window ending at some observation counts. It holds for both bounds (`worst_lower`,
    `worst_upper`), the windows that reach before the first observation included. -/
theorem worst_at_observation (t : Nat → Rat) (b : Nat → Bool) (f0 : Rat → Rat) (N : Nat) (ht : Sorted t N)
    (hf0 : ∀ y z, y ≤ z → z ≤ t 0 → 0 ≤ f0 z - f0 y ∧ f0 z - f0 y ≤ z - y)
    (w τ : Rat) (h0 : t 0 ≤ τ) (hN : τ ≤ t N) :
    ∃ i, i ≤ N ∧ inWindow t (lin t b) f0 N w τ ≤ inWindow t (lin t b) f0 N w (t i) := by
  have hmono := cum_mono t (lin t b) f0 N ht
    (fun k _ _ y z _ hyz _ => by unfold lin; split <;> grind)
    (fun y z hyz hz => by have := hf0 y z hyz hz; grind) N (Nat.le_refl _)
  have hlip := cum_lip t (lin t b) f0 N ht
    (fun k _ _ y z _ hyz _ => by unfold lin; split <;> grind)
    (fun y z hyz hz => (hf0 y z hyz hz).2)
  rcases cell_of t N ht τ h0 hN with e | ⟨i, h1, h2, h3, h4⟩
  · exact ⟨0, Nat.zero_le _, by rw [e]; exact Rat.le_refl⟩
  · unfold inWindow
    cases hb : b i with
    | true =>
      refine ⟨i, h2, ?_⟩
      have e := cum_cell t (lin t b) f0 N ht i h1 h2 τ (t i) h3 h4 (Rat.le_trans h3 h4) Rat.le_refl N (Nat.le_refl _)
      rw [if_pos h2] at e
      have el : lin t b i (t i) - lin t b i τ = t i - τ := by unfold lin; rw [hb]; grind
      rw [el] at e
      have l := hlip (τ - w) (t i - w) (by grind)
      generalize cum t (lin t b) f0 (t i) N = A at *
      generalize cum t (lin t b) f0 τ N = B at *
      generalize cum t (lin t b) f0 (t i - w) N = C at *
      generalize cum t (lin t b) f0 (τ - w) N = D at *
      grind
    | false =>
      refine ⟨i - 1, by omega, ?_⟩
      have e := cum_cell t (lin t b) f0 N ht i h1 h2 (t (i - 1)) τ Rat.le_refl (Rat.le_trans h3 h4) h3 h4 N (Nat.le_refl _)
      rw [if_pos h2] at e
      have el : lin t b i τ - lin t b i (t (i - 1)) = 0 := by unfold lin; rw [hb]; grind
      rw [el] at e
      have l := hmono (t (i - 1) - w) (τ - w) (by grind)
      generalize cum t (lin t b) f0 (t (i - 1)) N = A at *
      generalize cum t (lin t b) f0 τ N = B at *
      generalize cum t (lin t b) f0 (t (i - 1) - w) N = C at *
      generalize cum t (lin t b) f0 (τ - w) N = D at *
      grind

theorem worst_lower (t : Nat → Rat) (b : Nat → Bool) (N : Nat) (ht : Sorted t N) (w τ : Rat)
    (h0 : t 0 ≤ τ) (hN : τ ≤ t N) :
    ∃ i, i ≤ N ∧ inWindow t (lin t b) (fun _ => 0) N w τ ≤ inWindow t (lin t b) (fun _ => 0) N w (t i) :=
  worst_at_observation t b _ N ht (fun _ _ hyz _ => by grind) w τ h0 hN

theorem worst_upper (t : Nat → Rat) (b : Nat → Bool) (N : Nat) (ht : Sorted t N) (w τ : Rat)
    (h0 : t 0 ≤ τ) (hN : τ ≤ t N) :
    ∃ i, i ≤ N ∧ inWindow t (lin t b) (fun y => y - t 0) N w τ ≤ inWindow t (lin t b) (fun y => y - t 0) N w (t i) :=
  worst_at_observation t b _ N ht (fun _ _ hyz _ => by grind) w τ h0 hN

/-- A completion of the samples: what the condition did between them, as the time it held. On cell
    `k` (`1 ≤ k ≤ N`) `m k y` is the time held up to instant `y` of the cell, growing by at least
    nothing and at most the time elapsed; by exactly the time elapsed where the cell counts toward
    both bounds (`lo`), by nothing where it counts toward neither (`hi` false). Before the first
    observation `m0` grows likewise, freely. -/
structure Completion (t : Nat → Rat) (lo hi : Nat → Bool) (N : Nat) where
  m : Nat → Rat → Rat
  m0 : Rat → Rat
  grows : ∀ k, 1 ≤ k → k ≤ N → ∀ y z, t (k - 1) ≤ y → y ≤ z → z ≤ t k → 0 ≤ m k z - m k y ∧ m k z - m k y ≤ z - y
  sure : ∀ k, 1 ≤ k → k ≤ N → lo k = true → ∀ y z, t (k - 1) ≤ y → y ≤ z → z ≤ t k → m k z - m k y = z - y
  excluded : ∀ k, 1 ≤ k → k ≤ N → hi k = false → ∀ y z, t (k - 1) ≤ y → y ≤ z → z ≤ t k → m k z - m k y = 0
  grows0 : ∀ y z, y ≤ z → z ≤ t 0 → 0 ≤ m0 z - m0 y ∧ m0 z - m0 y ≤ z - y

/-- The time a completion held in the window `(τ − w, τ]`. -/
def Completion.held {t : Nat → Rat} {lo hi : Nat → Bool} {N : Nat} (c : Completion t lo hi N) (w τ : Rat) : Rat :=
  inWindow t c.m c.m0 N w τ

/-- Soundness: every completion held, in every window, at least the lower bound (the cells counting
    toward both bounds, nothing before the first observation) and at most the upper bound (every
    cell not counting toward neither, all of the part before the first observation). -/
theorem completion_within (t : Nat → Rat) (lo hi : Nat → Bool) (N : Nat) (ht : Sorted t N)
    (c : Completion t lo hi N) (w τ : Rat) (hw : 0 ≤ w) :
    inWindow t (lin t lo) (fun _ => 0) N w τ ≤ c.held w τ ∧
      c.held w τ ≤ inWindow t (lin t hi) (fun y => y - t 0) N w τ := by
  unfold Completion.held inWindow
  have dlo := cum_mono t (fun k y => c.m k y - lin t lo k y) (fun y => c.m0 y - 0) N ht
    (fun k h1 h2 y z hy hyz hz => by
      have g := c.grows k h1 h2 y z hy hyz hz
      unfold lin
      cases hl : lo k with
      | true => have := c.sure k h1 h2 hl y z hy hyz hz; simp; grind
      | false => simp; grind)
    (fun y z hyz hz => by have := c.grows0 y z hyz hz; grind) N (Nat.le_refl _) (τ - w) τ (by grind)
  have dhi := cum_mono t (fun k y => lin t hi k y - c.m k y) (fun y => (y - t 0) - c.m0 y) N ht
    (fun k h1 h2 y z hy hyz hz => by
      have g := c.grows k h1 h2 y z hy hyz hz
      unfold lin
      cases hh : hi k with
      | true => simp; grind
      | false => have := c.excluded k h1 h2 hh y z hy hyz hz; simp; grind)
    (fun y z hyz hz => by have := c.grows0 y z hyz hz; grind) N (Nat.le_refl _) (τ - w) τ (by grind)
  rw [cum_sub, cum_sub] at dlo dhi
  generalize cum t c.m c.m0 τ N = A at *
  generalize cum t c.m c.m0 (τ - w) N = B at *
  generalize cum t (lin t lo) (fun _ => 0) τ N = C at *
  generalize cum t (lin t lo) (fun _ => 0) (τ - w) N = D at *
  generalize cum t (lin t hi) (fun y => y - t 0) τ N = E at *
  generalize cum t (lin t hi) (fun y => y - t 0) (τ - w) N = F at *
  constructor <;> grind

/-- The count at an instant `x` of cell `p` (`1 ≤ p ≤ N`): the whole counts of the cells before
    it and its own count of `x`. -/
theorem cum_in_cell (t : Nat → Rat) (b : Nat → Bool) (f0 : Rat → Rat) (N : Nat) (ht : Sorted t N)
    (p : Nat) (hp1 : 1 ≤ p) (hpN : p ≤ N) (x : Rat) (hx : t (p - 1) ≤ x) (hxp : x ≤ t p) :
    ∀ m, m ≤ N → cum t (lin t b) f0 x m = f0 (t 0) + (if m < p then sumR t b m else sumR t b (p - 1) + lin t b p x) := by
  intro m
  induction m with
  | zero =>
    intro _
    have h0 : t 0 ≤ t (p - 1) := ht 0 (p - 1) (by omega) (by omega)
    simp only [cum, sumR]
    have e : (if x ≤ t 0 then x else t 0) = t 0 := by split <;> grind
    rw [e, if_pos (by omega)]; grind
  | succ m ih =>
    intro hm
    have ih' := ih (by omega)
    simp only [cum, sumR]
    rw [ih']
    have h2 : t m ≤ t (m + 1) := ht m (m + 1) (by omega) hm
    by_cases hlt : m + 1 < p
    · have h1 : t (m + 1) ≤ t (p - 1) := ht (m + 1) (p - 1) (by omega) (by omega)
      have e : clamp x (t m) (t (m + 1)) = t (m + 1) := by unfold clamp; split <;> (try split) <;> grind
      rw [e, if_pos (by omega), if_pos hlt]; unfold lin; simp; grind
    · by_cases heq : m + 1 = p
      · subst heq
        have hx' : t m ≤ x := by simpa using hx
        have e : clamp x (t m) (t (m + 1)) = x := by unfold clamp; split <;> (try split) <;> grind
        rw [e, if_pos (by omega), if_neg hlt]; simp; grind
      · have h1 : t p ≤ t m := ht p m (by omega) (by omega)
        have e : clamp x (t m) (t (m + 1)) = t m := by unfold clamp; split <;> grind
        rw [e, if_neg (by omega), if_neg hlt]; unfold lin; split <;> grind

/-- The count at an instant before the first observation: the part before it alone. -/
theorem cum_before (t : Nat → Rat) (b : Nat → Bool) (f0 : Rat → Rat) (N : Nat) (ht : Sorted t N)
    (x : Rat) (hx : x ≤ t 0) : ∀ m, m ≤ N → cum t (lin t b) f0 x m = f0 x := by
  intro m
  induction m with
  | zero => intro _; simp only [cum, if_pos hx]
  | succ m ih =>
    intro hm
    simp only [cum, ih (by omega)]
    have h1 : t 0 ≤ t m := ht 0 m (by omega) (by omega)
    have e : clamp x (t m) (t (m + 1)) = t m := by unfold clamp; split <;> grind
    rw [e]; unfold lin; split <;> grind

/-- The count at observation `i`: the whole counts of the cells up to it. -/
theorem cum_at_obs (t : Nat → Rat) (b : Nat → Bool) (f0 : Rat → Rat) (N : Nat) (ht : Sorted t N)
    (i : Nat) (hi : i ≤ N) : cum t (lin t b) f0 (t i) N = f0 (t 0) + sumR t b i := by
  cases i with
  | zero => rw [cum_before t b f0 N ht (t 0) Rat.le_refl N (Nat.le_refl _), sumR]; grind
  | succ i =>
    rw [cum_in_cell t b f0 N ht (i + 1) (by omega) hi (t (i + 1)) (ht i (i + 1) (by omega) hi) Rat.le_refl N (Nat.le_refl _)]
    by_cases h : N < i + 1
    · omega
    · rw [if_neg h]; simp only [sumR, Nat.add_sub_cancel, lin]

end Spec

-- ---------------------------------------------------------------------------------------------
-- The operator
-- ---------------------------------------------------------------------------------------------
/-- The bounds at one observation, and the reasons the window holds an uncertain part: a cell whose
    value is unknown, a cell longer than the step bound, the part before the first observation. -/
structure Bounds where
  lower : Q
  upper : Q
  why : List UnknownReason
  deriving Inhabited

/-- Cell `k` counts toward the lower bound: it is a cell (not the first observation), no longer
    than the step bound, and the condition is true at its observation. -/
def low (times : Array Q) (step : Q) (vals : Array R) (k : Nat) : Bool :=
  k != 0 && Q.le (Accumulate.dt times k) step && vals[k]!.v == .t

/-- Cell `k` counts toward the upper bound: unless it is no longer than the step bound and the
    condition is false at its observation. -/
def high (times : Array Q) (step : Q) (vals : Array R) (k : Nat) : Bool :=
  !(Q.le (Accumulate.dt times k) step && vals[k]!.v == .f)

/-- Σ_{j=1}^{k} of the cells' elapsed times where `b`. -/
def sumAt (times : Array Q) (b : Nat → Bool) : Nat → Q
  | 0 => Q.zero
  | k + 1 => Q.add (sumAt times b k) (if b (k + 1) then Accumulate.dt times (k + 1) else Q.zero)

/-- `sumAt` for each of the first `n` observations, in one forward pass. -/
def sums (times : Array Q) (b : Nat → Bool) (n : Nat) : Array Q :=
  (List.range n).foldl (fun (acc : Array Q) k =>
    acc.push (if k = 0 then Q.zero else Q.add acc[k - 1]! (if b k then Accumulate.dt times k else Q.zero))) #[]

/-- From `j` on, the least index below `i` whose time is not before `x`; `i` when none is. -/
def seek (times : Array Q) (x : Q) (i j : Nat) : Nat :=
  if j < i ∧ Q.lt times[j]! x = true then seek times x i (j + 1) else j
termination_by i - j

/-- The start of the window behind observation `i`. -/
def start (times : Array Q) (w : Q) (i : Nat) : Q := Q.sub times[i]! w

/-- The cell holding the start of the window behind observation `i`, found from the previous one. -/
def ptrAt (times : Array Q) (w : Q) : Nat → Nat
  | 0 => 0
  | i + 1 => seek times (start times w (i + 1)) (i + 1) (ptrAt times w i)

/-- `ptrAt` for each of the first `n` observations, in one forward pass. -/
def ptrs (times : Array Q) (w : Q) (n : Nat) : Array Nat :=
  (List.range n).foldl (fun (acc : Array Nat) i =>
    acc.push (if i = 0 then 0 else seek times (start times w i) i acc[i - 1]!)) #[]

/-- The count at `x` in cell `p` from the sums `S` (before the first observation when `p = 0`,
    where `pre` counts its time). -/
def cumAt (times : Array Q) (b : Nat → Bool) (pre : Bool) (S : Array Q) (x : Q) (p : Nat) : Q :=
  if p = 0 then (if pre then Q.sub x times[0]! else Q.zero)
  else Q.add S[p - 1]! (if b p then Q.sub x times[p - 1]! else Q.zero)

/-- Per observation `k`, the least `j ≥ k` no longer than the step bound whose value is unknown
    (`n` when none). -/
def nextUnknown (times : Array Q) (step : Q) (vals : Array R) : Array Nat :=
  let n := vals.size
  (List.range n).reverse.foldl (fun (acc : Array Nat) k =>
    acc.set! k (if k != 0 && Q.le (Accumulate.dt times k) step && vals[k]!.v == .u then k else acc[k + 1]!))
    (Array.replicate (n + 1) n)

/-- The bounds on the time ψ held in the window of length `w` behind every observation, the cells
    no longer than `step` decided by ψ's value at their observation. `op` names the operator in
    the reasons. -/
def boundsAll (times : Array Q) (w step : Q) (op : String) (vals : Array R) : Array Bounds :=
  let n := vals.size
  let lo := low times step vals
  let hi := high times step vals
  let wide := fun k => k != 0 && !Q.le (Accumulate.dt times k) step
  let SL := sums times lo n
  let SU := sums times hi n
  let SW := sums times wide n
  let ps := ptrs times w n
  let nu := nextUnknown times step vals
  (Array.range n).map fun i =>
    let x := start times w i
    let p := ps[i]!
    let k := nu[if p = 0 then 1 else p]!
    let why := (if Q.lt Q.zero (Q.sub SW[i]! (cumAt times wide false SW x p)) then [UnknownReason.samplingGap op] else []) ++
      (if k ≤ i then vals[k]!.why else []) ++
      (if p = 0 && Q.lt x times[0]! then [UnknownReason.windowTruncated op] else [])
    ⟨Q.sub SL[i]! (cumAt times lo false SL x p), Q.sub SU[i]! (cumAt times hi true SU x p), why.eraseDups⟩

-- ---------------------------------------------------------------------------------------------
-- The operator is its specification
-- ---------------------------------------------------------------------------------------------
section Bridge
variable {times : Array Q} {w step : Q} {op : String} {vals : Array R}

theorem size_boundsAll : (boundsAll times w step op vals).size = vals.size := by simp [boundsAll]

theorem sums_get (b : Nat → Bool) (n k : Nat) (hk : k < n) : (sums times b n)[k]! = sumAt times b k := by
  unfold sums
  refine (Accumulate.build_get _ (sumAt times b) n ?_ n (Nat.le_refl _)).2 k hk
  intro acc j _ _ hm
  cases j with
  | zero => rfl
  | succ j => simp only [Nat.add_one_ne_zero, if_false, Nat.add_sub_cancel]; rw [hm j (by omega)]; rfl

theorem ptrs_get (n i : Nat) (hi : i < n) : (ptrs times w n)[i]! = ptrAt times w i := by
  unfold ptrs
  refine (Accumulate.build_get _ (ptrAt times w) n ?_ n (Nat.le_refl _)).2 i hi
  intro acc j _ _ hm
  cases j with
  | zero => rfl
  | succ j => simp only [Nat.add_one_ne_zero, if_false, Nat.add_sub_cancel]; rw [hm j (by omega)]; rfl

/-- What `seek` finds: an index at most `i`, every index before it earlier than `x`, and itself not
    earlier than `x` unless it is `i`. -/
theorem seek_spec (x : Q) (i j : Nat) (hj : j ≤ i) (hb : ∀ k, k < j → Q.lt times[k]! x = true) :
    seek times x i j ≤ i ∧ (∀ k, k < seek times x i j → Q.lt times[k]! x = true) ∧
      (seek times x i j < i → Q.lt times[seek times x i j]! x = false) := by
  induction h : i - j generalizing j with
  | zero =>
    have : j = i := by omega
    subst this
    rw [seek]; simp only [Nat.lt_irrefl, false_and, if_false]
    exact ⟨Nat.le_refl _, hb, fun h => h.elim⟩
  | succ d ih =>
    rw [seek]
    by_cases hc : j < i ∧ Q.lt times[j]! x = true
    · rw [if_pos hc]
      exact ih (j + 1) (by omega) (fun k hk => by
        rcases Nat.lt_succ_iff_lt_or_eq.mp hk with h' | h'
        · exact hb k h'
        · subst h'; exact hc.2) (by omega)
    · rw [if_neg hc]
      refine ⟨hj, hb, fun hl => ?_⟩
      cases hq : Q.lt times[j]! x with
      | false => rfl
      | true => exact absurd ⟨hl, hq⟩ hc

/-- The cell of each window start: at most its observation, every observation before it earlier
    than the start, and itself not earlier unless it is the window's own observation. -/
theorem ptr_spec {N : Nat} (hsort : Sorted (fun k => (times[k]!).val) N) (i : Nat) (hi : i ≤ N) :
    ptrAt times w i ≤ i ∧ (∀ k, k < ptrAt times w i → Q.lt times[k]! (start times w i) = true) ∧
      (ptrAt times w i < i → Q.lt times[ptrAt times w i]! (start times w i) = false) := by
  induction i with
  | zero => simp [ptrAt]
  | succ i ih =>
    obtain ⟨h1, h2, _⟩ := ih (by omega)
    refine seek_spec _ (i + 1) _ (by omega) (fun k hk => ?_)
    have a := (Q.lt_iff_val _ _).mp (h2 k hk)
    have mono : (times[i]!).val ≤ (times[i + 1]!).val := hsort i (i + 1) (by omega) hi
    rw [Q.lt_iff_val]
    unfold start at a ⊢
    rw [Accumulate.Q.val_sub] at a ⊢
    grind

theorem sumAt_val (b : Nat → Bool) : ∀ k, (sumAt times b k).val = sumR (fun k => (times[k]!).val) b k := by
  intro k
  induction k with
  | zero => exact Q.val_zero
  | succ k ih =>
    simp only [sumAt, sumR, Accumulate.Q.val_add, ih]
    split
    · simp only [Accumulate.dt, Nat.add_one_ne_zero, if_false, Nat.add_sub_cancel]; rw [Accumulate.Q.val_sub]
    · rw [Q.val_zero]

/-- The fast count at the window start is the specification's. -/
theorem cumAt_val {N : Nat} (hsort : Sorted (fun k => (times[k]!).val) N) (hw : 0 ≤ w.val) (b : Nat → Bool) (pre : Bool) (n : Nat) (hn : N + 1 = n) (i : Nat) (hi : i ≤ N) :
    (cumAt times b pre (sums times b n) (start times w i) (ptrAt times w i)).val =
      cum (fun k => (times[k]!).val) (lin (fun k => (times[k]!).val) b)
        (fun y => if pre then y - (times[0]!).val else 0) (start times w i).val N := by
  obtain ⟨p1, p2, p3⟩ := ptr_spec (w := w) hsort i hi
  have hx : (start times w i).val ≤ (times[ptrAt times w i]!).val := by
    by_cases hp : ptrAt times w i < i
    · have h3 := p3 hp
      apply Rat.not_lt.mp
      intro hh
      rw [(Q.lt_iff_val _ _).mpr hh] at h3
      cases h3
    · have e : ptrAt times w i = i := by omega
      rw [e]; unfold start; rw [Accumulate.Q.val_sub]; grind
  unfold cumAt
  by_cases hp : ptrAt times w i = 0
  · rw [if_pos hp]
    rw [hp] at hx
    rw [cum_before _ b _ N hsort _ hx N (Nat.le_refl _)]
    cases pre
    · simp only [Bool.false_eq_true, if_false]; exact Q.val_zero
    · simp only [if_true]; rw [Accumulate.Q.val_sub]
  · rw [if_neg hp]
    have hlt := (Q.lt_iff_val _ _).mp (p2 (ptrAt times w i - 1) (by omega))
    rw [cum_in_cell _ b _ N hsort (ptrAt times w i) (by omega) (by omega) _ (Rat.le_of_lt hlt) hx N (Nat.le_refl _),
      if_neg (show ¬ N < ptrAt times w i by omega)]
    have e0 : (if pre = true then (times[0]!).val - (times[0]!).val else 0) = 0 := by cases pre <;> simp <;> grind
    rw [e0, Accumulate.Q.val_add, sums_get b n (ptrAt times w i - 1) (by omega), sumAt_val b]
    unfold lin
    split
    · rw [Accumulate.Q.val_sub]; grind
    · rw [Q.val_zero]; grind

/-- The computed bounds are the specification's: at observation `i`, the lower bound is the window
    count of the cells counting toward both bounds with nothing before the first observation, the
    upper bound that of the cells counting toward the upper bound with all of the part before the
    first observation, for observation times in order and a window not negative. -/
theorem bounds_val (hsort : Sorted (fun k => (times[k]!).val) (vals.size - 1)) (hw : 0 ≤ w.val)
    (i : Nat) (hi : i < vals.size) :
    ((boundsAll times w step op vals)[i]!).lower.val =
        inWindow (fun k => (times[k]!).val) (lin (fun k => (times[k]!).val) (low times step vals)) (fun _ => 0)
          (vals.size - 1) w.val (times[i]!).val ∧
      ((boundsAll times w step op vals)[i]!).upper.val =
        inWindow (fun k => (times[k]!).val) (lin (fun k => (times[k]!).val) (high times step vals))
          (fun y => y - (times[0]!).val) (vals.size - 1) w.val (times[i]!).val := by
  have hn : vals.size - 1 + 1 = vals.size := by omega
  have hst : (start times w i).val = (times[i]!).val - w.val := by unfold start; rw [Accumulate.Q.val_sub]
  unfold boundsAll
  rw [getElem!_pos _ i (by simpa using hi)]
  simp only [Array.getElem_map, Array.getElem_range]
  rw [ptrs_get _ i hi]
  unfold inWindow
  constructor
  · rw [Accumulate.Q.val_sub, sums_get _ _ i hi, sumAt_val _,
      cumAt_val hsort hw _ false vals.size hn i (by omega), hst,
      cum_at_obs _ _ _ _ hsort i (by omega)]
    simp only [Bool.false_eq_true, if_false]; grind
  · rw [Accumulate.Q.val_sub, sums_get _ _ i hi, sumAt_val _,
      cumAt_val hsort hw _ true vals.size hn i (by omega), hst,
      cum_at_obs _ _ _ _ hsort i (by omega)]
    simp only [if_true]; grind

/-- Judging at the observations decides every window: for observation times in order, every
    window ending between the first and the last observation has a lower bound at most the computed
    lower bound at some observation, and an upper bound at most the computed upper bound at some
    observation. -/
theorem judged_at_observations (hsort : Sorted (fun k => (times[k]!).val) (vals.size - 1)) (hw : 0 ≤ w.val)
    (hn : 0 < vals.size) (τ : Rat) (h0 : (times[0]!).val ≤ τ) (hN : τ ≤ (times[vals.size - 1]!).val) :
    (∃ i, i < vals.size ∧ inWindow (fun k => (times[k]!).val) (lin (fun k => (times[k]!).val) (low times step vals))
        (fun _ => 0) (vals.size - 1) w.val τ ≤ ((boundsAll times w step op vals)[i]!).lower.val) ∧
      (∃ i, i < vals.size ∧ inWindow (fun k => (times[k]!).val) (lin (fun k => (times[k]!).val) (high times step vals))
        (fun y => y - (times[0]!).val) (vals.size - 1) w.val τ ≤ ((boundsAll times w step op vals)[i]!).upper.val) := by
  obtain ⟨i, hi, h⟩ := worst_lower _ (low times step vals) _ hsort w.val τ h0 hN
  obtain ⟨j, hj, h'⟩ := worst_upper _ (high times step vals) _ hsort w.val τ h0 hN
  exact ⟨⟨i, by omega, by rw [(bounds_val (step := step) (op := op) hsort hw i (by omega)).1]; exact h⟩,
    ⟨j, by omega, by rw [(bounds_val (step := step) (op := op) hsort hw j (by omega)).2]; exact h'⟩⟩

/-- The whole counts of the cells of `(j, i]` are `Accumulate.integral` of their indicator. -/
theorem integral_sumR (b : Nat → Bool) (rate : Array (Option Q)) (j : Nat) :
    ∀ i, j ≤ i → (∀ k, j < k → k ≤ i → rate[k]! = some (if b k then Q.ofInt 1 else Q.zero)) →
      Accumulate.integral times rate j i =
        some (sumR (fun k => (times[k]!).val) b i - sumR (fun k => (times[k]!).val) b j) := by
  intro i
  induction i with
  | zero => intro h _; have : j = 0 := by omega
            subst this; simp only [Accumulate.integral, Option.some.injEq]; grind
  | succ i ih =>
    intro hji hr
    rcases Nat.lt_succ_iff_lt_or_eq.mp (Nat.lt_succ_of_le hji) with hlt | heq
    · have hj : ¬ (i + 1 ≤ j) := by omega
      have ih' := ih (by omega) (fun k h1 h2 => hr k h1 (by omega))
      simp only [Accumulate.integral, hj, if_false, ih', hr (i + 1) hlt (Nat.le_refl _), Option.bind_eq_bind,
        Option.bind_some, Option.pure_def, Option.some.injEq, sumR]
      cases b (i + 1)
      · simp only [Bool.false_eq_true, if_false, Q.val_zero]; grind
      · simp only [if_true]; have : (Q.ofInt 1).val = 1 := by simp [Q.val, Q.ofInt]; rfl
        rw [this]; grind
    · subst heq; rw [Accumulate.integral_le _ _ (Nat.le_refl _)]; simp only [Option.some.injEq]; grind

/-- Where the window behind observation `i` starts at observation `j` and every cell of `(j, i]` is
    no longer than the step bound with the condition known at its observation, both bounds are
    `Accumulate.integral` of the condition's indicator over `(j, i]`. -/
theorem agrees_integral (hsort : Sorted (fun k => (times[k]!).val) (vals.size - 1)) (hw : 0 ≤ w.val)
    (i j : Nat) (hi : i < vals.size) (hji : j ≤ i) (hstart : (times[i]!).val - w.val = (times[j]!).val)
    (hdec : ∀ k, j < k → k ≤ i → Q.le (Accumulate.dt times k) step = true ∧ vals[k]!.v ≠ .u)
    (rate : Array (Option Q))
    (hr : ∀ k, j < k → k ≤ i → rate[k]! = some (if vals[k]!.v == .t then Q.ofInt 1 else Q.zero)) :
    Accumulate.integral times rate j i = some ((boundsAll times w step op vals)[i]!).lower.val ∧
      Accumulate.integral times rate j i = some ((boundsAll times w step op vals)[i]!).upper.val := by
  obtain ⟨hl, hu⟩ := bounds_val (step := step) (op := op) hsort hw i hi
  rw [hl, hu]
  unfold inWindow
  rw [hstart, cum_at_obs _ _ _ _ hsort i (by omega), cum_at_obs _ _ _ _ hsort j (by omega),
    cum_at_obs _ _ _ _ hsort i (by omega), cum_at_obs _ _ _ _ hsort j (by omega)]
  constructor
  · rw [integral_sumR (low times step vals) rate j i hji (fun k h1 h2 => by
      rw [hr k h1 h2]; obtain ⟨hn, _⟩ := hdec k h1 h2
      unfold low; simp [hn, show k ≠ 0 by omega])]
    congr 1; grind
  · rw [integral_sumR (high times step vals) rate j i hji (fun k h1 h2 => by
      rw [hr k h1 h2]; obtain ⟨hn, hu⟩ := hdec k h1 h2
      unfold high; cases hv : vals[k]!.v <;> simp_all)]
    congr 1; grind

end Bridge

end SampledDuration
end TrafficSpec
