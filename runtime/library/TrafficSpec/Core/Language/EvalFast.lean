/-
  The evaluator with a sub-expression cache.

  `evalAll` re-evaluates a sub-formula every time a quantifier or a repeated concept reaches it
  again, although its value depends only on the trace, the reading, the rule set and the values of
  the variables it mentions. `evalFastAll` evaluates as `evalAll` does, and stores the value of
  every sub-formula and sub-term under a key: the sub-expression, as a token list, and the values
  its variable names have in the binding (the whole binding where it composes another rule, whose
  evaluation reads every variable). A later visit with the same key reads the stored value.

  What is proved here:
  - `Formula.enc_inj`, `Term.enc_inj`: two sub-expressions with the same tokens are the same;
  - `evalAll_congr`, `evalTAll_congr`: a formula or term that composes no rule has one value for
    every two bindings that agree on its variable names;
  - `Cache.hit`, `Cache.hitT`: in a cache whose every entry is the value `evalAll` gives its key,
    a read returns the value `evalAll` gives the formula under the binding read with;
  - `regionArm_eq`: a region quantifier read through the context's region tables
    (`RegionTable`) is, for any evaluator of its body, the same state program as the direct one:
    the same regions in the same order, the same kind rows and presence, the same calls.
  That the values the cached evaluator stores are those of `evalAll` is checked on executions
  (`Tests/EvalFast.lean` and the monitor's differential runs), not proved.

  A cache lives for one call of `evalFastAll`: one trace, one reading, one rule set and composition
  depth, one set of aggregate overrides. It holds at most `cells` per-observation values; a value
  that would pass the bound empties it first, and an emptied entry is computed again.
-/
import TrafficSpec.Core.Language.Semantics
import Std.Data.HashMap

namespace TrafficSpec

-- ---------------------------------------------------------------------------------------------
-- Keys: a sub-expression as tokens
-- ---------------------------------------------------------------------------------------------

/-- One token of an encoded sub-expression. -/
inductive Tok
  | s (x : String)
  | n (x : Nat)
  | i (x : Int)
  deriving DecidableEq, Hashable, Repr, Inhabited

/-- The token that ends a list. No sub-expression's encoding starts with it. -/
def endTok : Tok := .n 0

def PUnit'.code : PUnit' → Nat
  | .metre => 0 | .second => 1 | .metrePerSecond => 2 | .metrePerSecondSq => 3 | .degree => 4
  | .degreePerSecond => 5 | .perMetre => 6 | .ratio => 7 | .count => 8
def CmpOp.code : CmpOp → Nat | .lt => 0 | .le => 1 | .eq => 2 | .ge => 3 | .gt => 4
def AggOp.code : AggOp → Nat | .min => 0 | .max => 1 | .median => 2 | .count => 3
def Measure.code : Measure → Nat | .time => 0 | .path => 1

theorem PUnit'.code_inj {a b : PUnit'} (h : a.code = b.code) : a = b := by
  cases a <;> cases b <;> first | rfl | (simp [PUnit'.code] at h)
theorem CmpOp.code_inj {a b : CmpOp} (h : a.code = b.code) : a = b := by
  cases a <;> cases b <;> first | rfl | (simp [CmpOp.code] at h)
theorem AggOp.code_inj {a b : AggOp} (h : a.code = b.code) : a = b := by
  cases a <;> cases b <;> first | rfl | (simp [AggOp.code] at h)
theorem Measure.code_inj {a b : Measure} (h : a.code = b.code) : a = b := by
  cases a <;> cases b <;> first | rfl | (simp [Measure.code] at h)

def Arg.enc : Arg → List Tok
  | .var v => [.n 1, .s v]
  | .lit x => [.n 2, .s x]
  | .nat k => [.n 3, .n k]
def Arg.encL : List Arg → List Tok
  | [] => [endTok]
  | a :: as => a.enc ++ Arg.encL as
def encMap : List (String × String) → List Tok
  | [] => [endTok]
  | (a, b) :: m => .n 1 :: .s a :: .s b :: encMap m

mutual
  /-- A term as tokens: its constructor's tag (1–14), then its fields in order. -/
  def Term.enc : Term → List Tok
    | .lit q u => [.n 1, .i q.num, .n q.den, .n u.code]
    | .param p => [.n 2, .s p]
    | .measure a args => .n 3 :: .s a :: Arg.encL args
    | .quantity c args ps => .n 4 :: .s c :: (Arg.encL args ++ Term.encL ps)
    | .distanceWhile s φ => .n 5 :: .s s :: Formula.enc φ
    | .sinceRise φ => .n 6 :: Formula.enc φ
    | .aggregate op v φ t => .n 7 :: .n op.code :: .s v :: (Formula.enc φ ++ Term.enc t)
    | .add a b => .n 8 :: (Term.enc a ++ Term.enc b)
    | .sub a b => .n 9 :: (Term.enc a ++ Term.enc b)
    | .mul a b => .n 10 :: (Term.enc a ++ Term.enc b)
    | .div a b => .n 11 :: (Term.enc a ++ Term.enc b)
    | .neg a => .n 12 :: Term.enc a
    | .abs a => .n 13 :: Term.enc a
    | .cond φ a b => .n 14 :: (Formula.enc φ ++ (Term.enc a ++ Term.enc b))
  def Term.encL : List Term → List Tok
    | [] => [endTok]
    | t :: ts => Term.enc t ++ Term.encL ts
  /-- A formula as tokens: its constructor's tag (1–31), then its fields in order. -/
  def Formula.enc : Formula → List Tok
    | .tt => [.n 1]
    | .ff => [.n 2]
    | .atom a args ps => .n 3 :: .s a :: (Arg.encL args ++ Term.encL ps)
    | .cmp l op r => .n 4 :: .n op.code :: (Term.enc l ++ Term.enc r)
    | .asm id => [.n 5, .s id]
    | .intent id a b => .n 6 :: .s id :: (a.enc ++ b.enc)
    | .same a b => .n 7 :: (a.enc ++ b.enc)
    | .not φ => .n 8 :: Formula.enc φ
    | .and φ ψ => .n 9 :: (Formula.enc φ ++ Formula.enc ψ)
    | .or φ ψ => .n 10 :: (Formula.enc φ ++ Formula.enc ψ)
    | .implies φ ψ => .n 11 :: (Formula.enc φ ++ Formula.enc ψ)
    | .always φ => .n 12 :: Formula.enc φ
    | .eventually φ => .n 13 :: Formula.enc φ
    | .until φ ψ => .n 14 :: (Formula.enc φ ++ Formula.enc ψ)
    | .since φ ψ => .n 15 :: (Formula.enc φ ++ Formula.enc ψ)
    | .holdsFor m d s φ => .n 16 :: .n m.code :: .s s :: (Term.enc d ++ Formula.enc φ)
    | .within m d s φ => .n 17 :: .n m.code :: .s s :: (Term.enc d ++ Formula.enc φ)
    | .untilWithin m d s φ ψ => .n 18 :: .n m.code :: .s s :: (Term.enc d ++ (Formula.enc φ ++ Formula.enc ψ))
    | .atLast m d s ψ φ => .n 19 :: .n m.code :: .s s :: (Term.enc d ++ (Formula.enc ψ ++ Formula.enc φ))
    | .count e sφ op k => .n 20 :: .n op.code :: .n k :: (Formula.enc e ++ Formula.enc sφ)
    | .rises φ => .n 21 :: Formula.enc φ
    | .definedWhen p φ => .n 22 :: (Formula.enc p ++ Formula.enc φ)
    | .derived c args ps => .n 23 :: .s c :: (Arg.encL args ++ Term.encL ps)
    | .rule id map => .n 24 :: .s id :: encMap map
    | .ruleApplies id map => .n 25 :: .s id :: encMap map
    | .existsUser v φ => .n 26 :: .s v :: Formula.enc φ
    | .forallUser v φ => .n 27 :: .s v :: Formula.enc φ
    | .existsRegion k v φ => .n 28 :: .s v :: (k.enc ++ Formula.enc φ)
    | .forallRegion k v φ => .n 29 :: .s v :: (k.enc ++ Formula.enc φ)
    | .existsDevice k v φ => .n 30 :: .s v :: (k.enc ++ Formula.enc φ)
    | .forallDevice k v φ => .n 31 :: .s v :: (k.enc ++ Formula.enc φ)
end

theorem Arg.enc_inj : ∀ (a b : Arg) (r₁ r₂ : List Tok), a.enc ++ r₁ = b.enc ++ r₂ → a = b ∧ r₁ = r₂ := by
  intro a b r₁ r₂ h; cases a <;> cases b <;> simp_all [Arg.enc]

theorem Arg.encL_inj : ∀ (as bs : List Arg) (r₁ r₂ : List Tok), Arg.encL as ++ r₁ = Arg.encL bs ++ r₂ →
    as = bs ∧ r₁ = r₂
  | [], [], _, _, h => by simpa [Arg.encL] using h
  | [], b :: _, _, _, h => by cases b <;> simp [Arg.encL, Arg.enc, endTok] at h
  | a :: _, [], _, _, h => by cases a <;> simp [Arg.encL, Arg.enc, endTok] at h
  | a :: as, b :: bs, r₁, r₂, h => by
    simp only [Arg.encL, List.append_assoc] at h
    obtain ⟨rfl, h'⟩ := Arg.enc_inj a b _ _ h
    obtain ⟨rfl, rfl⟩ := Arg.encL_inj as bs r₁ r₂ h'
    exact ⟨rfl, rfl⟩

theorem encMap_inj : ∀ (m m' : List (String × String)) (r₁ r₂ : List Tok), encMap m ++ r₁ = encMap m' ++ r₂ →
    m = m' ∧ r₁ = r₂
  | [], [], _, _, h => by simpa [encMap] using h
  | [], _ :: _, _, _, h => by simp [encMap, endTok] at h
  | _ :: _, [], _, _, h => by simp [encMap, endTok] at h
  | (a, b) :: m, (a', b') :: m', r₁, r₂, h => by
    simp only [encMap, List.cons_append, List.cons.injEq, Tok.s.injEq, true_and] at h
    obtain ⟨rfl, rfl, h'⟩ := h
    obtain ⟨rfl, rfl⟩ := encMap_inj m m' r₁ r₂ h'
    exact ⟨rfl, rfl⟩

private theorem Q.eq_of {a b : Q} (h₁ : a.num = b.num) (h₂ : a.den = b.den) : a = b := by
  cases a; cases b; simp_all

mutual
  theorem Term.enc_inj : ∀ (a b : Term) (r₁ r₂ : List Tok), a.enc ++ r₁ = b.enc ++ r₂ → a = b ∧ r₁ = r₂
    | .lit q u, b, r₁, r₂, h => by
      cases b <;> simp [Term.enc] at h
      case lit q' u' =>
        obtain ⟨h1, h2, h3, rfl⟩ := h
        exact ⟨by rw [Q.eq_of h1 h2, PUnit'.code_inj h3], rfl⟩
    | .param p, b, r₁, r₂, h => by
      cases b <;> simp [Term.enc] at h
      case param p' => obtain ⟨rfl, rfl⟩ := h; exact ⟨rfl, rfl⟩
    | .measure a args, b, r₁, r₂, h => by
      cases b <;> simp [Term.enc] at h
      case measure a' args' =>
        obtain ⟨rfl, ha⟩ := h
        obtain ⟨rfl, rfl⟩ := Arg.encL_inj args args' r₁ r₂ ha
        exact ⟨rfl, rfl⟩
    | .quantity c args ps, b, r₁, r₂, h => by
      cases b <;> simp [Term.enc] at h
      case quantity c' args' ps' =>
        obtain ⟨rfl, ha⟩ := h
        obtain ⟨rfl, hb⟩ := Arg.encL_inj args args' _ _ ha
        obtain ⟨rfl, rfl⟩ := Term.encL_inj ps ps' r₁ r₂ hb
        exact ⟨rfl, rfl⟩
    | .distanceWhile s φ, b, r₁, r₂, h => by
      cases b <;> simp [Term.enc] at h
      case distanceWhile s' φ' =>
        obtain ⟨rfl, ha⟩ := h
        obtain ⟨rfl, rfl⟩ := Formula.enc_inj φ φ' r₁ r₂ ha
        exact ⟨rfl, rfl⟩
    | .sinceRise φ, b, r₁, r₂, h => by
      cases b <;> simp [Term.enc] at h
      case sinceRise φ' =>
        obtain ⟨rfl, rfl⟩ := Formula.enc_inj φ φ' r₁ r₂ h
        exact ⟨rfl, rfl⟩
    | .aggregate op v φ x, b, r₁, r₂, h => by
      cases b <;> simp [Term.enc] at h
      case aggregate op' v' φ' x' =>
        obtain ⟨hop, rfl, ha⟩ := h
        obtain ⟨rfl, hb⟩ := Formula.enc_inj φ φ' _ _ ha
        obtain ⟨rfl, rfl⟩ := Term.enc_inj x x' r₁ r₂ hb
        exact ⟨by rw [AggOp.code_inj hop], rfl⟩
    | .add x y, b, r₁, r₂, h => by
      cases b <;> simp [Term.enc] at h
      case add x' y' =>
        obtain ⟨rfl, ha⟩ := Term.enc_inj x x' _ _ h
        obtain ⟨rfl, rfl⟩ := Term.enc_inj y y' r₁ r₂ ha
        exact ⟨rfl, rfl⟩
    | .sub x y, b, r₁, r₂, h => by
      cases b <;> simp [Term.enc] at h
      case sub x' y' =>
        obtain ⟨rfl, ha⟩ := Term.enc_inj x x' _ _ h
        obtain ⟨rfl, rfl⟩ := Term.enc_inj y y' r₁ r₂ ha
        exact ⟨rfl, rfl⟩
    | .mul x y, b, r₁, r₂, h => by
      cases b <;> simp [Term.enc] at h
      case mul x' y' =>
        obtain ⟨rfl, ha⟩ := Term.enc_inj x x' _ _ h
        obtain ⟨rfl, rfl⟩ := Term.enc_inj y y' r₁ r₂ ha
        exact ⟨rfl, rfl⟩
    | .div x y, b, r₁, r₂, h => by
      cases b <;> simp [Term.enc] at h
      case div x' y' =>
        obtain ⟨rfl, ha⟩ := Term.enc_inj x x' _ _ h
        obtain ⟨rfl, rfl⟩ := Term.enc_inj y y' r₁ r₂ ha
        exact ⟨rfl, rfl⟩
    | .neg x, b, r₁, r₂, h => by
      cases b <;> simp [Term.enc] at h
      case neg x' =>
        obtain ⟨rfl, rfl⟩ := Term.enc_inj x x' r₁ r₂ h
        exact ⟨rfl, rfl⟩
    | .abs x, b, r₁, r₂, h => by
      cases b <;> simp [Term.enc] at h
      case abs x' =>
        obtain ⟨rfl, rfl⟩ := Term.enc_inj x x' r₁ r₂ h
        exact ⟨rfl, rfl⟩
    | .cond φ x y, b, r₁, r₂, h => by
      cases b <;> simp [Term.enc] at h
      case cond φ' x' y' =>
        obtain ⟨rfl, ha⟩ := Formula.enc_inj φ φ' _ _ h
        obtain ⟨rfl, hb⟩ := Term.enc_inj x x' _ _ ha
        obtain ⟨rfl, rfl⟩ := Term.enc_inj y y' r₁ r₂ hb
        exact ⟨rfl, rfl⟩
  termination_by a => sizeOf a

  theorem Term.encL_inj : ∀ (as bs : List Term) (r₁ r₂ : List Tok), Term.encL as ++ r₁ = Term.encL bs ++ r₂ →
      as = bs ∧ r₁ = r₂
    | [], [], _, _, h => by simpa [Term.encL] using h
    | [], b :: _, _, _, h => by cases b <;> simp [Term.encL, Term.enc, endTok] at h
    | a :: _, [], _, _, h => by cases a <;> simp [Term.encL, Term.enc, endTok] at h
    | a :: as, b :: bs, r₁, r₂, h => by
      simp only [Term.encL, List.append_assoc] at h
      obtain ⟨rfl, ha⟩ := Term.enc_inj a b _ _ h
      obtain ⟨rfl, rfl⟩ := Term.encL_inj as bs r₁ r₂ ha
      exact ⟨rfl, rfl⟩
  termination_by as => sizeOf as

  theorem Formula.enc_inj : ∀ (a b : Formula) (r₁ r₂ : List Tok), a.enc ++ r₁ = b.enc ++ r₂ → a = b ∧ r₁ = r₂
    | .tt, b, r₁, r₂, h => by cases b <;> simp [Formula.enc] at h; exact ⟨rfl, h⟩
    | .ff, b, r₁, r₂, h => by cases b <;> simp [Formula.enc] at h; exact ⟨rfl, h⟩
    | .atom a args ps, b, r₁, r₂, h => by
      cases b <;> simp [Formula.enc] at h
      case atom a' args' ps' =>
        obtain ⟨rfl, ha⟩ := h
        obtain ⟨rfl, hb⟩ := Arg.encL_inj args args' _ _ ha
        obtain ⟨rfl, rfl⟩ := Term.encL_inj ps ps' r₁ r₂ hb
        exact ⟨rfl, rfl⟩
    | .cmp l op r, b, r₁, r₂, h => by
      cases b <;> simp [Formula.enc] at h
      case cmp l' op' r' =>
        obtain ⟨hop, ha⟩ := h
        obtain ⟨rfl, hb⟩ := Term.enc_inj l l' _ _ ha
        obtain ⟨rfl, rfl⟩ := Term.enc_inj r r' r₁ r₂ hb
        exact ⟨by rw [CmpOp.code_inj hop], rfl⟩
    | .asm id, b, r₁, r₂, h => by
      cases b <;> simp [Formula.enc] at h
      case asm id' => obtain ⟨rfl, rfl⟩ := h; exact ⟨rfl, rfl⟩
    | .intent id x y, b, r₁, r₂, h => by
      cases b <;> simp [Formula.enc] at h
      case intent id' x' y' =>
        obtain ⟨rfl, ha⟩ := h
        obtain ⟨rfl, hb⟩ := Arg.enc_inj x x' _ _ ha
        obtain ⟨rfl, rfl⟩ := Arg.enc_inj y y' r₁ r₂ hb
        exact ⟨rfl, rfl⟩
    | .same x y, b, r₁, r₂, h => by
      cases b <;> simp [Formula.enc] at h
      case same x' y' =>
        obtain ⟨rfl, ha⟩ := Arg.enc_inj x x' _ _ h
        obtain ⟨rfl, rfl⟩ := Arg.enc_inj y y' r₁ r₂ ha
        exact ⟨rfl, rfl⟩
    | .not φ, b, r₁, r₂, h => by
      cases b <;> simp [Formula.enc] at h
      case not φ' => obtain ⟨rfl, rfl⟩ := Formula.enc_inj φ φ' r₁ r₂ h; exact ⟨rfl, rfl⟩
    | .and φ ψ, b, r₁, r₂, h => by
      cases b <;> simp [Formula.enc] at h
      case and φ' ψ' =>
        obtain ⟨rfl, ha⟩ := Formula.enc_inj φ φ' _ _ h
        obtain ⟨rfl, rfl⟩ := Formula.enc_inj ψ ψ' r₁ r₂ ha
        exact ⟨rfl, rfl⟩
    | .or φ ψ, b, r₁, r₂, h => by
      cases b <;> simp [Formula.enc] at h
      case or φ' ψ' =>
        obtain ⟨rfl, ha⟩ := Formula.enc_inj φ φ' _ _ h
        obtain ⟨rfl, rfl⟩ := Formula.enc_inj ψ ψ' r₁ r₂ ha
        exact ⟨rfl, rfl⟩
    | .implies φ ψ, b, r₁, r₂, h => by
      cases b <;> simp [Formula.enc] at h
      case implies φ' ψ' =>
        obtain ⟨rfl, ha⟩ := Formula.enc_inj φ φ' _ _ h
        obtain ⟨rfl, rfl⟩ := Formula.enc_inj ψ ψ' r₁ r₂ ha
        exact ⟨rfl, rfl⟩
    | .always φ, b, r₁, r₂, h => by
      cases b <;> simp [Formula.enc] at h
      case always φ' => obtain ⟨rfl, rfl⟩ := Formula.enc_inj φ φ' r₁ r₂ h; exact ⟨rfl, rfl⟩
    | .eventually φ, b, r₁, r₂, h => by
      cases b <;> simp [Formula.enc] at h
      case eventually φ' => obtain ⟨rfl, rfl⟩ := Formula.enc_inj φ φ' r₁ r₂ h; exact ⟨rfl, rfl⟩
    | .until φ ψ, b, r₁, r₂, h => by
      cases b <;> simp [Formula.enc] at h
      case «until» φ' ψ' =>
        obtain ⟨rfl, ha⟩ := Formula.enc_inj φ φ' _ _ h
        obtain ⟨rfl, rfl⟩ := Formula.enc_inj ψ ψ' r₁ r₂ ha
        exact ⟨rfl, rfl⟩
    | .since φ ψ, b, r₁, r₂, h => by
      cases b <;> simp [Formula.enc] at h
      case since φ' ψ' =>
        obtain ⟨rfl, ha⟩ := Formula.enc_inj φ φ' _ _ h
        obtain ⟨rfl, rfl⟩ := Formula.enc_inj ψ ψ' r₁ r₂ ha
        exact ⟨rfl, rfl⟩
    | .holdsFor m d s φ, b, r₁, r₂, h => by
      cases b <;> simp [Formula.enc] at h
      case holdsFor m' d' s' φ' =>
        obtain ⟨hm, rfl, ha⟩ := h
        obtain ⟨rfl, hb⟩ := Term.enc_inj d d' _ _ ha
        obtain ⟨rfl, rfl⟩ := Formula.enc_inj φ φ' r₁ r₂ hb
        exact ⟨by rw [Measure.code_inj hm], rfl⟩
    | .within m d s φ, b, r₁, r₂, h => by
      cases b <;> simp [Formula.enc] at h
      case within m' d' s' φ' =>
        obtain ⟨hm, rfl, ha⟩ := h
        obtain ⟨rfl, hb⟩ := Term.enc_inj d d' _ _ ha
        obtain ⟨rfl, rfl⟩ := Formula.enc_inj φ φ' r₁ r₂ hb
        exact ⟨by rw [Measure.code_inj hm], rfl⟩
    | .untilWithin m d s φ ψ, b, r₁, r₂, h => by
      cases b <;> simp [Formula.enc] at h
      case untilWithin m' d' s' φ' ψ' =>
        obtain ⟨hm, rfl, ha⟩ := h
        obtain ⟨rfl, hb⟩ := Term.enc_inj d d' _ _ ha
        obtain ⟨rfl, hc⟩ := Formula.enc_inj φ φ' _ _ hb
        obtain ⟨rfl, rfl⟩ := Formula.enc_inj ψ ψ' r₁ r₂ hc
        exact ⟨by rw [Measure.code_inj hm], rfl⟩
    | .atLast m d s ψ φ, b, r₁, r₂, h => by
      cases b <;> simp [Formula.enc] at h
      case atLast m' d' s' ψ' φ' =>
        obtain ⟨hm, rfl, ha⟩ := h
        obtain ⟨rfl, hb⟩ := Term.enc_inj d d' _ _ ha
        obtain ⟨rfl, hc⟩ := Formula.enc_inj ψ ψ' _ _ hb
        obtain ⟨rfl, rfl⟩ := Formula.enc_inj φ φ' r₁ r₂ hc
        exact ⟨by rw [Measure.code_inj hm], rfl⟩
    | .count e sφ op k, b, r₁, r₂, h => by
      cases b <;> simp [Formula.enc] at h
      case count e' sφ' op' k' =>
        obtain ⟨hop, rfl, ha⟩ := h
        obtain ⟨rfl, hb⟩ := Formula.enc_inj e e' _ _ ha
        obtain ⟨rfl, rfl⟩ := Formula.enc_inj sφ sφ' r₁ r₂ hb
        exact ⟨by rw [CmpOp.code_inj hop], rfl⟩
    | .rises φ, b, r₁, r₂, h => by
      cases b <;> simp [Formula.enc] at h
      case rises φ' => obtain ⟨rfl, rfl⟩ := Formula.enc_inj φ φ' r₁ r₂ h; exact ⟨rfl, rfl⟩
    | .definedWhen p φ, b, r₁, r₂, h => by
      cases b <;> simp [Formula.enc] at h
      case definedWhen p' φ' =>
        obtain ⟨rfl, ha⟩ := Formula.enc_inj p p' _ _ h
        obtain ⟨rfl, rfl⟩ := Formula.enc_inj φ φ' r₁ r₂ ha
        exact ⟨rfl, rfl⟩
    | .derived a args ps, b, r₁, r₂, h => by
      cases b <;> simp [Formula.enc] at h
      case derived a' args' ps' =>
        obtain ⟨rfl, ha⟩ := h
        obtain ⟨rfl, hb⟩ := Arg.encL_inj args args' _ _ ha
        obtain ⟨rfl, rfl⟩ := Term.encL_inj ps ps' r₁ r₂ hb
        exact ⟨rfl, rfl⟩
    | .rule id m, b, r₁, r₂, h => by
      cases b <;> simp [Formula.enc] at h
      case rule id' m' =>
        obtain ⟨rfl, ha⟩ := h
        obtain ⟨rfl, rfl⟩ := encMap_inj m m' r₁ r₂ ha
        exact ⟨rfl, rfl⟩
    | .ruleApplies id m, b, r₁, r₂, h => by
      cases b <;> simp [Formula.enc] at h
      case ruleApplies id' m' =>
        obtain ⟨rfl, ha⟩ := h
        obtain ⟨rfl, rfl⟩ := encMap_inj m m' r₁ r₂ ha
        exact ⟨rfl, rfl⟩
    | .existsUser v φ, b, r₁, r₂, h => by
      cases b <;> simp [Formula.enc] at h
      case existsUser v' φ' =>
        obtain ⟨rfl, ha⟩ := h
        obtain ⟨rfl, rfl⟩ := Formula.enc_inj φ φ' r₁ r₂ ha
        exact ⟨rfl, rfl⟩
    | .forallUser v φ, b, r₁, r₂, h => by
      cases b <;> simp [Formula.enc] at h
      case forallUser v' φ' =>
        obtain ⟨rfl, ha⟩ := h
        obtain ⟨rfl, rfl⟩ := Formula.enc_inj φ φ' r₁ r₂ ha
        exact ⟨rfl, rfl⟩
    | .existsRegion k v φ, b, r₁, r₂, h => by
      cases b <;> simp [Formula.enc] at h
      case existsRegion k' v' φ' =>
        obtain ⟨rfl, ha⟩ := h
        obtain ⟨rfl, hb⟩ := Arg.enc_inj k k' _ _ ha
        obtain ⟨rfl, rfl⟩ := Formula.enc_inj φ φ' r₁ r₂ hb
        exact ⟨rfl, rfl⟩
    | .forallRegion k v φ, b, r₁, r₂, h => by
      cases b <;> simp [Formula.enc] at h
      case forallRegion k' v' φ' =>
        obtain ⟨rfl, ha⟩ := h
        obtain ⟨rfl, hb⟩ := Arg.enc_inj k k' _ _ ha
        obtain ⟨rfl, rfl⟩ := Formula.enc_inj φ φ' r₁ r₂ hb
        exact ⟨rfl, rfl⟩
    | .existsDevice k v φ, b, r₁, r₂, h => by
      cases b <;> simp [Formula.enc] at h
      case existsDevice k' v' φ' =>
        obtain ⟨rfl, ha⟩ := h
        obtain ⟨rfl, hb⟩ := Arg.enc_inj k k' _ _ ha
        obtain ⟨rfl, rfl⟩ := Formula.enc_inj φ φ' r₁ r₂ hb
        exact ⟨rfl, rfl⟩
    | .forallDevice k v φ, b, r₁, r₂, h => by
      cases b <;> simp [Formula.enc] at h
      case forallDevice k' v' φ' =>
        obtain ⟨rfl, ha⟩ := h
        obtain ⟨rfl, hb⟩ := Arg.enc_inj k k' _ _ ha
        obtain ⟨rfl, rfl⟩ := Formula.enc_inj φ φ' r₁ r₂ hb
        exact ⟨rfl, rfl⟩
  termination_by a => sizeOf a
end

theorem Formula.enc_eq {a b : Formula} (h : a.enc = b.enc) : a = b :=
  (Formula.enc_inj a b [] [] (by simpa using h)).1
theorem Term.enc_eq {a b : Term} (h : a.enc = b.enc) : a = b :=
  (Term.enc_inj a b [] [] (by simpa using h)).1

end TrafficSpec

namespace TrafficSpec

-- ---------------------------------------------------------------------------------------------
-- What a sub-expression reads of the binding
-- ---------------------------------------------------------------------------------------------

def Arg.names : List Arg → List String
  | [] => []
  | .var v :: as => v :: Arg.names as
  | _ :: as => Arg.names as

mutual
  /-- The variable names a term reads, less those its own aggregate binds. -/
  def Term.names : Term → List String
    | .lit _ _ | .param _ => []
    | .measure _ args => Arg.names args
    | .quantity _ args ps => Arg.names args ++ Term.namesL ps
    | .distanceWhile s φ => s :: Formula.names φ
    | .sinceRise φ => Formula.names φ
    | .aggregate _ v φ t => (Formula.names φ ++ Term.names t).filter (· != v)
    | .add a b | .sub a b | .mul a b | .div a b => Term.names a ++ Term.names b
    | .neg a | .abs a => Term.names a
    | .cond φ a b => Formula.names φ ++ (Term.names a ++ Term.names b)
  def Term.namesL : List Term → List String
    | [] => []
    | t :: ts => Term.names t ++ Term.namesL ts
  /-- The variable names a formula reads, less those its own quantifiers bind. -/
  def Formula.names : Formula → List String
    | .tt | .ff | .asm _ | .rule _ _ | .ruleApplies _ _ => []
    | .atom _ args ps | .derived _ args ps => Arg.names args ++ Term.namesL ps
    | .cmp l _ r => Term.names l ++ Term.names r
    | .intent _ a b | .same a b => Arg.names [a, b]
    | .not φ | .always φ | .eventually φ | .rises φ => Formula.names φ
    | .and φ ψ | .or φ ψ | .implies φ ψ | .until φ ψ | .since φ ψ | .definedWhen φ ψ
    | .count φ ψ _ _ => Formula.names φ ++ Formula.names ψ
    | .holdsFor _ d s φ | .within _ d s φ => s :: (Term.names d ++ Formula.names φ)
    | .untilWithin _ d s φ ψ | .atLast _ d s φ ψ => s :: (Term.names d ++ (Formula.names φ ++ Formula.names ψ))
    | .existsUser v φ | .forallUser v φ | .existsRegion _ v φ | .forallRegion _ v φ
    | .existsDevice _ v φ | .forallDevice _ v φ => (Formula.names φ).filter (· != v)
end

mutual
  /-- Whether a term composes another rule anywhere. -/
  def Term.composes : Term → Bool
    | .lit _ _ | .param _ | .measure _ _ => false
    | .quantity _ _ ps => Term.composesL ps
    | .distanceWhile _ φ | .sinceRise φ => Formula.composes φ
    | .aggregate _ _ φ t => Formula.composes φ || Term.composes t
    | .add a b | .sub a b | .mul a b | .div a b => Term.composes a || Term.composes b
    | .neg a | .abs a => Term.composes a
    | .cond φ a b => Formula.composes φ || (Term.composes a || Term.composes b)
  def Term.composesL : List Term → Bool
    | [] => false
    | t :: ts => Term.composes t || Term.composesL ts
  /-- Whether a formula composes another rule anywhere. -/
  def Formula.composes : Formula → Bool
    | .rule _ _ | .ruleApplies _ _ => true
    | .tt | .ff | .asm _ | .intent _ _ _ | .same _ _ => false
    | .atom _ _ ps | .derived _ _ ps => Term.composesL ps
    | .cmp l _ r => Term.composes l || Term.composes r
    | .not φ | .always φ | .eventually φ | .rises φ => Formula.composes φ
    | .and φ ψ | .or φ ψ | .implies φ ψ | .until φ ψ | .since φ ψ | .definedWhen φ ψ
    | .count φ ψ _ _ => Formula.composes φ || Formula.composes ψ
    | .holdsFor _ d _ φ | .within _ d _ φ => Term.composes d || Formula.composes φ
    | .untilWithin _ d _ φ ψ | .atLast _ d _ φ ψ => Term.composes d || (Formula.composes φ || Formula.composes ψ)
    | .existsUser _ φ | .forallUser _ φ | .existsRegion _ _ φ | .forallRegion _ _ φ
    | .existsDevice _ _ φ | .forallDevice _ _ φ => Formula.composes φ
end

namespace Binding

/-- Two bindings agree on some names: each name has the same value, or none, in both. -/
def Agree (β₁ β₂ : Binding) (ns : List String) : Prop := ∀ v ∈ ns, β₁.lookup v = β₂.lookup v

theorem Agree.left {β₁ β₂ : Binding} {a b : List String} (h : Agree β₁ β₂ (a ++ b)) : Agree β₁ β₂ a :=
  fun v hv => h v (List.mem_append_left b hv)
theorem Agree.right {β₁ β₂ : Binding} {a b : List String} (h : Agree β₁ β₂ (a ++ b)) : Agree β₁ β₂ b :=
  fun v hv => h v (List.mem_append_right a hv)
theorem Agree.tail {β₁ β₂ : Binding} {s : String} {a : List String} (h : Agree β₁ β₂ (s :: a)) : Agree β₁ β₂ a :=
  fun v hv => h v (List.mem_cons_of_mem s hv)
theorem Agree.head {β₁ β₂ : Binding} {s : String} {a : List String} (h : Agree β₁ β₂ (s :: a)) :
    β₁.lookup s = β₂.lookup s := h s (List.mem_cons_self ..)

private theorem find?_filter_ne (l : List (String × Val)) (v w : String) (h : w ≠ v) :
    (l.filter (·.1 != v)).find? (·.1 == w) = l.find? (·.1 == w) := by
  induction l with
  | nil => rfl
  | cons p l ih =>
    rcases p with ⟨a, x⟩
    by_cases hp : a = v
    · subst hp
      have : (a == w) = false := by simpa using (fun e => h e.symm)
      rw [List.filter_cons_of_neg (by simp), ih, List.find?_cons_of_neg (by simp [this])]
    · rw [List.filter_cons_of_pos (by simpa using hp), List.find?_cons, List.find?_cons, ih]

theorem lookup_bind (β : Binding) (v w : String) (x : Val) :
    (β.bind v x).lookup w = if w = v then some x else β.lookup w := by
  unfold bind lookup
  by_cases h : w = v
  · subst h; simp [List.find?]
  · have : (v == w) = false := by simp; exact fun e => h e.symm
    simp [List.find?, this, h, find?_filter_ne _ _ _ h]

theorem Agree.bind {β₁ β₂ : Binding} {v : String} {ns : List String} (x : Val)
    (h : Agree β₁ β₂ (ns.filter (· != v))) : Agree (β₁.bind v x) (β₂.bind v x) ns := by
  intro w hw
  rw [lookup_bind, lookup_bind]
  by_cases e : w = v
  · simp [e]
  · simp only [e, if_false]; exact h w (List.mem_filter.mpr ⟨hw, by simp [e]⟩)

end Binding

end TrafficSpec

namespace TrafficSpec
namespace Semantics

open Binding (Agree)

-- ---------------------------------------------------------------------------------------------
-- Congruence: a value depends on the binding only through the names read
-- ---------------------------------------------------------------------------------------------
section Congruence

theorem resolve_congr {β₁ β₂ : Binding} (a : Arg) (h : Agree β₁ β₂ (Arg.names [a])) : resolve β₁ a = resolve β₂ a := by
  cases a with
  | var v => simp only [resolve, Agree.head (by simpa [Arg.names] using h)]
  | lit _ => rfl
  | nat _ => rfl

theorem resolveAll_congr {β₁ β₂ : Binding} : ∀ (args : List Arg), Agree β₁ β₂ (Arg.names args) →
    resolveAll β₁ args = resolveAll β₂ args
  | [], _ => rfl
  | a :: as, h => by
    have ha : Agree β₁ β₂ (Arg.names [a]) := by
      cases a with
      | var v => intro w hw; simp [Arg.names] at hw; subst hw; exact h.head
      | lit _ => intro w hw; simp [Arg.names] at hw
      | nat _ => intro w hw; simp [Arg.names] at hw
    have hs : Agree β₁ β₂ (Arg.names as) := by
      cases a <;> simp only [Arg.names] at h <;> first | exact h | exact h.tail
    have ih := resolveAll_congr as hs
    simp only [resolveAll, List.mapM_cons] at ih ⊢
    rw [resolve_congr a ha, ih]

theorem track_congr {β₁ β₂ : Binding} {s : String} (h : β₁.lookup s = β₂.lookup s) : β₁.track s = β₂.track s := by
  unfold Binding.track; rw [h]

theorem subjectFor_congr {β₁ β₂ : Binding} (m : Measure) {s : String} (h : β₁.lookup s = β₂.lookup s) :
    subjectFor β₁ m s = subjectFor β₂ m s := by
  cases m <;> simp only [subjectFor, track_congr h]

theorem Arg.names_cons (a : Arg) (as : List Arg) : Arg.names (a :: as) = Arg.names [a] ++ Arg.names as := by
  cases a <;> rfl

theorem Agree.filter_app {β₁ β₂ : Binding} {a b : List String} {v : String}
    (h : Agree β₁ β₂ ((a ++ b).filter (· != v))) : Agree β₁ β₂ (a.filter (· != v)) ∧ Agree β₁ β₂ (b.filter (· != v)) := by
  rw [List.filter_append] at h; exact ⟨h.left, h.right⟩

/-- The context a congruence compares: one trace and reading, one composition, two bindings. -/
abbrev ctxWith (d : Primitives.Ctx) (k : String → List (String × String) → Binding → Bool → Array R) (β : Binding) :
    SemCtx := ⟨d, β, k⟩

mutual
  theorem evalTAll_congr (d : Primitives.Ctx) (k : String → List (String × String) → Binding → Bool → Array R) :
      ∀ (t : Term) (β₁ β₂ : Binding), t.composes = false → Agree β₁ β₂ t.names →
        evalTAll (ctxWith d k β₁) t = evalTAll (ctxWith d k β₂) t
    | .lit _ _, _, _, _, _ => by rw [evalTAll, evalTAll] <;> rfl
    | .param _, _, _, _, _ => by rw [evalTAll, evalTAll] <;> rfl
    | .measure _ args, _, _, _, ha => by
      simp only [Term.names] at ha
      rw [evalTAll, evalTAll, resolveAll_congr args ha] <;> rfl
    | .quantity _ args ps, β₁, β₂, hc, ha => by
      simp only [Term.names] at ha; simp only [Term.composes] at hc
      rw [evalTAll, evalTAll, constParams_congr d k ps β₁ β₂ hc ha.right, resolveAll_congr args ha.left] <;> rfl
    | .distanceWhile _ φ, β₁, β₂, hc, ha => by
      simp only [Term.names] at ha; simp only [Term.composes] at hc
      rw [evalTAll, evalTAll, track_congr ha.head, evalAll_congr d k φ β₁ β₂ hc ha.tail] <;> rfl
    | .sinceRise φ, β₁, β₂, hc, ha => by
      simp only [Term.names] at ha; simp only [Term.composes] at hc
      rw [evalTAll, evalTAll, evalAll_congr d k φ β₁ β₂ hc ha] <;> rfl
    | .aggregate _ v φ t, β₁, β₂, hc, ha => by
      simp only [Term.names] at ha; simp only [Term.composes, Bool.or_eq_false_iff] at hc
      have h1 : ∀ u, evalAll ((ctxWith d k β₁).bindVar v (.track u)) φ = evalAll ((ctxWith d k β₂).bindVar v (.track u)) φ :=
        fun u => evalAll_congr d k φ _ _ hc.1 (Agree.bind (.track u) (Agree.filter_app ha).1)
      have h2 : ∀ u, evalTAll ((ctxWith d k β₁).bindVar v (.track u)) t = evalTAll ((ctxWith d k β₂).bindVar v (.track u)) t :=
        fun u => evalTAll_congr d k t _ _ hc.2 (Agree.bind (.track u) (Agree.filter_app ha).2)
      rw [evalTAll, evalTAll]; simp only [h1, h2]; rfl
    | .add a b, β₁, β₂, hc, ha => by
      simp only [Term.names] at ha; simp only [Term.composes, Bool.or_eq_false_iff] at hc
      rw [evalTAll, evalTAll, evalTAll_congr d k a β₁ β₂ hc.1 ha.left, evalTAll_congr d k b β₁ β₂ hc.2 ha.right] <;> rfl
    | .sub a b, β₁, β₂, hc, ha => by
      simp only [Term.names] at ha; simp only [Term.composes, Bool.or_eq_false_iff] at hc
      rw [evalTAll, evalTAll, evalTAll_congr d k a β₁ β₂ hc.1 ha.left, evalTAll_congr d k b β₁ β₂ hc.2 ha.right] <;> rfl
    | .mul a b, β₁, β₂, hc, ha => by
      simp only [Term.names] at ha; simp only [Term.composes, Bool.or_eq_false_iff] at hc
      rw [evalTAll, evalTAll, evalTAll_congr d k a β₁ β₂ hc.1 ha.left, evalTAll_congr d k b β₁ β₂ hc.2 ha.right] <;> rfl
    | .div a b, β₁, β₂, hc, ha => by
      simp only [Term.names] at ha; simp only [Term.composes, Bool.or_eq_false_iff] at hc
      rw [evalTAll, evalTAll, evalTAll_congr d k a β₁ β₂ hc.1 ha.left, evalTAll_congr d k b β₁ β₂ hc.2 ha.right] <;> rfl
    | .neg a, β₁, β₂, hc, ha => by
      simp only [Term.names] at ha; simp only [Term.composes] at hc
      rw [evalTAll, evalTAll, evalTAll_congr d k a β₁ β₂ hc ha] <;> rfl
    | .abs a, β₁, β₂, hc, ha => by
      simp only [Term.names] at ha; simp only [Term.composes] at hc
      rw [evalTAll, evalTAll, evalTAll_congr d k a β₁ β₂ hc ha] <;> rfl
    | .cond φ a b, β₁, β₂, hc, ha => by
      simp only [Term.names] at ha; simp only [Term.composes, Bool.or_eq_false_iff] at hc
      rw [evalTAll, evalTAll, evalAll_congr d k φ β₁ β₂ hc.1 ha.left,
        evalTAll_congr d k a β₁ β₂ hc.2.1 ha.right.left, evalTAll_congr d k b β₁ β₂ hc.2.2 ha.right.right] <;> rfl
  termination_by t => sizeOf t

  theorem constParams_congr (d : Primitives.Ctx) (k : String → List (String × String) → Binding → Bool → Array R) :
      ∀ (ps : List Term) (β₁ β₂ : Binding), Term.composesL ps = false → Agree β₁ β₂ (Term.namesL ps) →
        constParams (ctxWith d k β₁) ps = constParams (ctxWith d k β₂) ps
    | [], _, _, _, _ => by rw [constParams, constParams]
    | t :: rest, β₁, β₂, hc, ha => by
      simp only [Term.namesL] at ha; simp only [Term.composesL, Bool.or_eq_false_iff] at hc
      rw [constParams, constParams, evalTAll_congr d k t β₁ β₂ hc.1 ha.left,
        constParams_congr d k rest β₁ β₂ hc.2 ha.right]
  termination_by ps => sizeOf ps

  theorem evalAll_congr (d : Primitives.Ctx) (k : String → List (String × String) → Binding → Bool → Array R) :
      ∀ (φ : Formula) (β₁ β₂ : Binding), φ.composes = false → Agree β₁ β₂ φ.names →
        evalAll (ctxWith d k β₁) φ = evalAll (ctxWith d k β₂) φ
    | .tt, _, _, _, _ => by rw [evalAll, evalAll] <;> rfl
    | .ff, _, _, _, _ => by rw [evalAll, evalAll] <;> rfl
    | .atom _ args ps, β₁, β₂, hc, ha => by
      simp only [Formula.names] at ha; simp only [Formula.composes] at hc
      rw [evalAll, evalAll, constParams_congr d k ps β₁ β₂ hc ha.right, resolveAll_congr args ha.left] <;> rfl
    | .cmp l _ r, β₁, β₂, hc, ha => by
      simp only [Formula.names] at ha; simp only [Formula.composes, Bool.or_eq_false_iff] at hc
      rw [evalAll, evalAll, evalTAll_congr d k l β₁ β₂ hc.1 ha.left, evalTAll_congr d k r β₁ β₂ hc.2 ha.right] <;> rfl
    | .asm _, _, _, _, _ => by rw [evalAll, evalAll] <;> rfl
    | .intent _ who target, β₁, β₂, _, ha => by
      simp only [Formula.names] at ha
      cases who with
      | var a =>
        cases target with
        | var b =>
          simp only [Arg.names] at ha
          have hA : (ctxWith d k β₁).β.lookup a = (ctxWith d k β₂).β.lookup a := ha.head
          have hB : (ctxWith d k β₁).β.lookup b = (ctxWith d k β₂).β.lookup b := ha.tail.head
          rw [evalAll, evalAll, hA, hB] <;> rfl
        | lit _ => rw [evalAll, evalAll] <;> first | rfl | simp
        | nat _ => rw [evalAll, evalAll] <;> first | rfl | simp
      | lit _ => cases target <;> (rw [evalAll, evalAll] <;> first | rfl | simp)
      | nat _ => cases target <;> (rw [evalAll, evalAll] <;> first | rfl | simp)
    | .same a b, _, _, _, ha => by
      simp only [Formula.names] at ha; rw [Arg.names_cons] at ha
      rw [evalAll, evalAll, resolve_congr a ha.left, resolve_congr b ha.right] <;> rfl
    | .not φ, β₁, β₂, hc, ha => by
      simp only [Formula.names] at ha; simp only [Formula.composes] at hc
      rw [evalAll, evalAll, evalAll_congr d k φ β₁ β₂ hc ha] <;> rfl
    | .and φ ψ, β₁, β₂, hc, ha => by
      simp only [Formula.names] at ha; simp only [Formula.composes, Bool.or_eq_false_iff] at hc
      rw [evalAll, evalAll, evalAll_congr d k φ β₁ β₂ hc.1 ha.left, evalAll_congr d k ψ β₁ β₂ hc.2 ha.right] <;> rfl
    | .or φ ψ, β₁, β₂, hc, ha => by
      simp only [Formula.names] at ha; simp only [Formula.composes, Bool.or_eq_false_iff] at hc
      rw [evalAll, evalAll, evalAll_congr d k φ β₁ β₂ hc.1 ha.left, evalAll_congr d k ψ β₁ β₂ hc.2 ha.right] <;> rfl
    | .implies φ ψ, β₁, β₂, hc, ha => by
      simp only [Formula.names] at ha; simp only [Formula.composes, Bool.or_eq_false_iff] at hc
      rw [evalAll, evalAll, evalAll_congr d k φ β₁ β₂ hc.1 ha.left, evalAll_congr d k ψ β₁ β₂ hc.2 ha.right] <;> rfl
    | .always φ, β₁, β₂, hc, ha => by
      simp only [Formula.names] at ha; simp only [Formula.composes] at hc
      rw [evalAll, evalAll, evalAll_congr d k φ β₁ β₂ hc ha] <;> rfl
    | .eventually φ, β₁, β₂, hc, ha => by
      simp only [Formula.names] at ha; simp only [Formula.composes] at hc
      rw [evalAll, evalAll, evalAll_congr d k φ β₁ β₂ hc ha] <;> rfl
    | .until φ ψ, β₁, β₂, hc, ha => by
      simp only [Formula.names] at ha; simp only [Formula.composes, Bool.or_eq_false_iff] at hc
      rw [evalAll, evalAll, evalAll_congr d k φ β₁ β₂ hc.1 ha.left, evalAll_congr d k ψ β₁ β₂ hc.2 ha.right] <;> rfl
    | .since φ ψ, β₁, β₂, hc, ha => by
      simp only [Formula.names] at ha; simp only [Formula.composes, Bool.or_eq_false_iff] at hc
      rw [evalAll, evalAll, evalAll_congr d k φ β₁ β₂ hc.1 ha.left, evalAll_congr d k ψ β₁ β₂ hc.2 ha.right] <;> rfl
    | .holdsFor m t _ φ, β₁, β₂, hc, ha => by
      simp only [Formula.names] at ha; simp only [Formula.composes, Bool.or_eq_false_iff] at hc
      rw [evalAll, evalAll, subjectFor_congr m ha.head, evalTAll_congr d k t β₁ β₂ hc.1 ha.tail.left,
        evalAll_congr d k φ β₁ β₂ hc.2 ha.tail.right] <;> rfl
    | .within m t _ φ, β₁, β₂, hc, ha => by
      simp only [Formula.names] at ha; simp only [Formula.composes, Bool.or_eq_false_iff] at hc
      rw [evalAll, evalAll, subjectFor_congr m ha.head, evalTAll_congr d k t β₁ β₂ hc.1 ha.tail.left,
        evalAll_congr d k φ β₁ β₂ hc.2 ha.tail.right] <;> rfl
    | .untilWithin m t _ φ ψ, β₁, β₂, hc, ha => by
      simp only [Formula.names] at ha; simp only [Formula.composes, Bool.or_eq_false_iff] at hc
      rw [evalAll, evalAll, subjectFor_congr m ha.head, evalTAll_congr d k t β₁ β₂ hc.1 ha.tail.left,
        evalAll_congr d k φ β₁ β₂ hc.2.1 ha.tail.right.left, evalAll_congr d k ψ β₁ β₂ hc.2.2 ha.tail.right.right] <;> rfl
    | .atLast m t _ ψ φ, β₁, β₂, hc, ha => by
      simp only [Formula.names] at ha; simp only [Formula.composes, Bool.or_eq_false_iff] at hc
      rw [evalAll, evalAll, subjectFor_congr m ha.head, evalTAll_congr d k t β₁ β₂ hc.1 ha.tail.left,
        evalAll_congr d k ψ β₁ β₂ hc.2.1 ha.tail.right.left, evalAll_congr d k φ β₁ β₂ hc.2.2 ha.tail.right.right] <;> rfl
    | .count e s _ _, β₁, β₂, hc, ha => by
      simp only [Formula.names] at ha; simp only [Formula.composes, Bool.or_eq_false_iff] at hc
      rw [evalAll, evalAll, evalAll_congr d k e β₁ β₂ hc.1 ha.left, evalAll_congr d k s β₁ β₂ hc.2 ha.right] <;> rfl
    | .rises φ, β₁, β₂, hc, ha => by
      simp only [Formula.names] at ha; simp only [Formula.composes] at hc
      rw [evalAll, evalAll, evalAll_congr d k φ β₁ β₂ hc ha] <;> rfl
    | .definedWhen p φ, β₁, β₂, hc, ha => by
      simp only [Formula.names] at ha; simp only [Formula.composes, Bool.or_eq_false_iff] at hc
      rw [evalAll, evalAll, evalAll_congr d k p β₁ β₂ hc.1 ha.left, evalAll_congr d k φ β₁ β₂ hc.2 ha.right] <;> rfl
    | .derived _ args ps, β₁, β₂, hc, ha => by
      simp only [Formula.names] at ha; simp only [Formula.composes] at hc
      rw [evalAll, evalAll, constParams_congr d k ps β₁ β₂ hc ha.right, resolveAll_congr args ha.left] <;> rfl
    | .rule _ _, _, _, hc, _ => by simp [Formula.composes] at hc
    | .ruleApplies _ _, _, _, hc, _ => by simp [Formula.composes] at hc
    | .existsUser v φ, β₁, β₂, hc, ha => by
      simp only [Formula.names] at ha; simp only [Formula.composes] at hc
      have h1 : ∀ u, evalAll ((ctxWith d k β₁).bindVar v (.track u)) φ = evalAll ((ctxWith d k β₂).bindVar v (.track u)) φ :=
        fun u => evalAll_congr d k φ _ _ hc (Agree.bind (.track u) ha)
      rw [evalAll, evalAll]; simp only [h1]; rfl
    | .forallUser v φ, β₁, β₂, hc, ha => by
      simp only [Formula.names] at ha; simp only [Formula.composes] at hc
      have h1 : ∀ u, evalAll ((ctxWith d k β₁).bindVar v (.track u)) φ = evalAll ((ctxWith d k β₂).bindVar v (.track u)) φ :=
        fun u => evalAll_congr d k φ _ _ hc (Agree.bind (.track u) ha)
      rw [evalAll, evalAll]; simp only [h1]; rfl
    | .existsRegion _ v φ, β₁, β₂, hc, ha => by
      simp only [Formula.names] at ha; simp only [Formula.composes] at hc
      have h1 : ∀ r, evalAll ((ctxWith d k β₁).bindVar v (.region r)) φ = evalAll ((ctxWith d k β₂).bindVar v (.region r)) φ :=
        fun r => evalAll_congr d k φ _ _ hc (Agree.bind (.region r) ha)
      rw [evalAll, evalAll]; simp only [h1]; rfl
    | .forallRegion _ v φ, β₁, β₂, hc, ha => by
      simp only [Formula.names] at ha; simp only [Formula.composes] at hc
      have h1 : ∀ r, evalAll ((ctxWith d k β₁).bindVar v (.region r)) φ = evalAll ((ctxWith d k β₂).bindVar v (.region r)) φ :=
        fun r => evalAll_congr d k φ _ _ hc (Agree.bind (.region r) ha)
      rw [evalAll, evalAll]; simp only [h1]; rfl
    | .existsDevice _ v φ, β₁, β₂, hc, ha => by
      simp only [Formula.names] at ha; simp only [Formula.composes] at hc
      have h1 : ∀ x, evalAll ((ctxWith d k β₁).bindVar v (.device x)) φ = evalAll ((ctxWith d k β₂).bindVar v (.device x)) φ :=
        fun x => evalAll_congr d k φ _ _ hc (Agree.bind (.device x) ha)
      rw [evalAll, evalAll]; simp only [h1]; rfl
    | .forallDevice _ v φ, β₁, β₂, hc, ha => by
      simp only [Formula.names] at ha; simp only [Formula.composes] at hc
      have h1 : ∀ x, evalAll ((ctxWith d k β₁).bindVar v (.device x)) φ = evalAll ((ctxWith d k β₂).bindVar v (.device x)) φ :=
        fun x => evalAll_congr d k φ _ _ hc (Agree.bind (.device x) ha)
      rw [evalAll, evalAll]; simp only [h1]; rfl
  termination_by φ => sizeOf φ
end

end Congruence

end Semantics
end TrafficSpec

namespace TrafficSpec
namespace Semantics

open Binding (Agree)

-- ---------------------------------------------------------------------------------------------
-- The cache
-- ---------------------------------------------------------------------------------------------

deriving instance Hashable for Val

/-- What a stored value is stored under: the sub-expression's tokens, and the values of its names
    in the binding, or the whole binding where it composes another rule. -/
structure Key where
  expr : List Tok
  vals : List (Option Val)
  whole : List (String × Val)
  deriving DecidableEq, Hashable

def Key.ofF (φ : Formula) (β : Binding) : Key :=
  if φ.composes then ⟨φ.enc, [], β.binds⟩ else ⟨φ.enc, φ.names.map β.lookup, []⟩
def Key.ofT (t : Term) (β : Binding) : Key :=
  if t.composes then ⟨t.enc, [], β.binds⟩ else ⟨t.enc, t.names.map β.lookup, []⟩

private theorem agree_of_map {β₁ β₂ : Binding} {ns : List String} (h : ns.map β₁.lookup = ns.map β₂.lookup) :
    Agree β₁ β₂ ns := by
  intro v hv
  induction ns with
  | nil => simp at hv
  | cons w ns ih =>
    simp only [List.map_cons, List.cons.injEq] at h
    rcases List.mem_cons.mp hv with rfl | hv
    · exact h.1
    · exact ih h.2 hv

/-- Two formulas under two bindings with one key have one value. -/
theorem Key.ofF_sound (d : Primitives.Ctx) (k : String → List (String × String) → Binding → Bool → Array R)
    {φ₁ φ₂ : Formula} {β₁ β₂ : Binding} (h : Key.ofF φ₁ β₁ = Key.ofF φ₂ β₂) :
    evalAll (ctxWith d k β₁) φ₁ = evalAll (ctxWith d k β₂) φ₂ := by
  have he : φ₁ = φ₂ := Formula.enc_eq (by unfold Key.ofF at h; split at h <;> split at h <;> simp_all)
  subst he
  unfold Key.ofF at h
  split at h
  · simp only [Key.mk.injEq, true_and] at h
    have : β₁ = β₂ := by cases β₁; cases β₂; simp_all
    rw [this]
  · simp only [Key.mk.injEq, true_and, and_true] at h
    exact evalAll_congr d k φ₁ β₁ β₂ (by simpa using ‹¬φ₁.composes = true›) (agree_of_map h)

/-- Two terms under two bindings with one key have one value. -/
theorem Key.ofT_sound (d : Primitives.Ctx) (k : String → List (String × String) → Binding → Bool → Array R)
    {t₁ t₂ : Term} {β₁ β₂ : Binding} (h : Key.ofT t₁ β₁ = Key.ofT t₂ β₂) :
    evalTAll (ctxWith d k β₁) t₁ = evalTAll (ctxWith d k β₂) t₂ := by
  have he : t₁ = t₂ := Term.enc_eq (by unfold Key.ofT at h; split at h <;> split at h <;> simp_all)
  subst he
  unfold Key.ofT at h
  split at h
  · simp only [Key.mk.injEq, true_and] at h
    have : β₁ = β₂ := by cases β₁; cases β₂; simp_all
    rw [this]
  · simp only [Key.mk.injEq, true_and, and_true] at h
    exact evalTAll_congr d k t₁ β₁ β₂ (by simpa using ‹¬t₁.composes = true›) (agree_of_map h)

/-- Stored values of formulas and terms, with the number of per-observation values held, the
    bound on it, and counts of reads, misses and emptyings. -/
structure Cache where
  f : Std.HashMap Key (Array R) := {}
  t : Std.HashMap Key (Array QR) := {}
  cells : Nat := 0
  cap : Nat
  hits : Nat := 0
  misses : Nat := 0
  evictions : Nat := 0

namespace Cache

/-- Every stored value is the value `evalAll`/`evalTAll` gives some sub-expression and binding
    with that key, over one trace and reading (`d`) and one composition (`k`). -/
def Valid (d : Primitives.Ctx) (k : String → List (String × String) → Binding → Bool → Array R) (c : Cache) : Prop :=
  (∀ key v, c.f[key]? = some v → ∃ φ β, Key.ofF φ β = key ∧ v = evalAll (ctxWith d k β) φ) ∧
  (∀ key v, c.t[key]? = some v → ∃ t β, Key.ofT t β = key ∧ v = evalTAll (ctxWith d k β) t)

/-- A read from a valid cache is the value `evalAll` gives the formula under the binding read with. -/
theorem hit {d k} {c : Cache} (hv : Valid d k c) {φ : Formula} {β : Binding} {v : Array R}
    (h : c.f[Key.ofF φ β]? = some v) : v = evalAll (ctxWith d k β) φ := by
  obtain ⟨φ', β', hk, rfl⟩ := hv.1 _ _ h
  exact Key.ofF_sound d k hk

/-- A read from a valid cache is the value `evalTAll` gives the term under the binding read with. -/
theorem hitT {d k} {c : Cache} (hv : Valid d k c) {t : Term} {β : Binding} {v : Array QR}
    (h : c.t[Key.ofT t β]? = some v) : v = evalTAll (ctxWith d k β) t := by
  obtain ⟨t', β', hk, rfl⟩ := hv.2 _ _ h
  exact Key.ofT_sound d k hk

/-- Store a formula's value, emptying the cache first when it would pass its bound. -/
def putF (c : Cache) (key : Key) (v : Array R) : Cache :=
  if c.cells + v.size ≤ c.cap then { c with f := c.f.insert key v, cells := c.cells + v.size }
  else { c with f := ({} : Std.HashMap Key (Array R)).insert key v, t := {}, cells := v.size, evictions := c.evictions + 1 }
/-- Store a term's value, emptying the cache first when it would pass its bound. -/
def putT (c : Cache) (key : Key) (v : Array QR) : Cache :=
  if c.cells + v.size ≤ c.cap then { c with t := c.t.insert key v, cells := c.cells + v.size }
  else { c with f := {}, t := ({} : Std.HashMap Key (Array QR)).insert key v, cells := v.size, evictions := c.evictions + 1 }

/-- Storing the value `evalAll` gives a formula keeps the cache valid, whether or not it empties it. -/
theorem putF_valid {d k} {c : Cache} (hv : Valid d k c) (φ : Formula) (β : Binding) :
    Valid d k (c.putF (Key.ofF φ β) (evalAll (ctxWith d k β) φ)) := by
  unfold putF; split
  · refine ⟨fun key v h => ?_, hv.2⟩
    rw [Std.HashMap.getElem?_insert] at h; split at h
    · rename_i e; cases h; exact ⟨φ, β, by simpa using e, rfl⟩
    · exact hv.1 key v h
  · refine ⟨fun key v h => ?_, fun key v h => by simp at h⟩
    rw [Std.HashMap.getElem?_insert] at h; split at h
    · rename_i e; cases h; exact ⟨φ, β, by simpa using e, rfl⟩
    · simp at h

/-- Storing the value `evalTAll` gives a term keeps the cache valid, whether or not it empties it. -/
theorem putT_valid {d k} {c : Cache} (hv : Valid d k c) (t : Term) (β : Binding) :
    Valid d k (c.putT (Key.ofT t β) (evalTAll (ctxWith d k β) t)) := by
  unfold putT; split
  · refine ⟨hv.1, fun key v h => ?_⟩
    rw [Std.HashMap.getElem?_insert] at h; split at h
    · rename_i e; cases h; exact ⟨t, β, by simpa using e, rfl⟩
    · exact hv.2 key v h
  · refine ⟨fun key v h => by simp at h, fun key v h => ?_⟩
    rw [Std.HashMap.getElem?_insert] at h; split at h
    · rename_i e; cases h; exact ⟨t, β, by simpa using e, rfl⟩
    · simp at h

theorem empty_valid (d k) (cap : Nat) : Valid d k { cap := cap } :=
  ⟨fun _ _ h => by simp at h, fun _ _ h => by simp at h⟩

end Cache

end Semantics
end TrafficSpec

namespace TrafficSpec
namespace Semantics

open Temporal

-- ---------------------------------------------------------------------------------------------
-- The cached evaluator
-- ---------------------------------------------------------------------------------------------

/-- The default bound on the per-observation values a cache holds. -/
def defaultCells : Nat := 4000000

abbrev FastM := StateM Cache

/-- A window's subject and length, as `evalAll` reads them before the window's body. -/
private def windowOf (c : SemCtx) (m : Measure) (d : Term) (subj : String) : Except UnknownReason (TrackId × Q) := do
  let x ← subjectFor c.β m subj
  let dv ← constOf d (evalTAll c d)
  pure (x, dv)

/-- `perScene` with presence read by instant index rather than by scene. -/
def perSceneAt (c : SemCtx) (evaluated : List (Nat × Array R)) (presentAt : Nat → Nat → Bool)
    (agg : List R → R) : Array R :=
  (Array.range c.n).map fun i =>
    agg (evaluated.filterMap fun (m, arr) => if presentAt i m then some arr[i]! else none)

theorem perScene_eq_perSceneAt (c : SemCtx) (ev : List (Nat × Array R)) (p : Scene → Nat → Bool)
    (agg : List R → R) : perScene c ev p agg = perSceneAt c ev (fun i m => p c.scenes[i]! m) agg := rfl

/-- A region quantifier over kind `kd` as `evalAll` writes it, with the body evaluated by `rec`:
    every candidate in order, its kind row combined by `comb` with the body's value, then `agg`
    at each instant over the regions present there. -/
def regionArmDirect (rec : SemCtx → Formula → FastM (Array R)) (c : SemCtx) (kd : StructureKind)
    (v : String) (φ : Formula) (comb : R → R → R) (agg : List R → R) : FastM (Array R) := do
  let ev ← (regionsOf c kd).mapM fun r =>
    return (r, Array.zipWith comb (regionIsKind c r kd) (← rec (c.bindVar v (.region r)) φ))
  return perScene c ev (fun s r => (s.structure? r).isSome) agg

/-- The same quantifier with the candidates, kind rows and presence read from the context's region
    tables. -/
def regionArm (rec : SemCtx → Formula → FastM (Array R)) (c : SemCtx) (kd : StructureKind)
    (v : String) (φ : Formula) (comb : R → R → R) (agg : List R → R) : FastM (Array R) := do
  let rows := c.d.regions.rowsOf kd
  let ev ← (rows.ids.toList.zip rows.isKind.toList).mapM fun (r, isK) =>
    return (r, Array.zipWith comb isK (← rec (c.bindVar v (.region r)) φ))
  return perSceneAt c ev (fun i r => (c.d.regions.indexAt i).contains r) agg

private theorem mapM_zip_map {α β γ : Type} (g : α × β → FastM γ) (f : α → β) :
    ∀ l : List α, (l.zip (l.map f)).mapM g = l.mapM (fun a => g (a, f a))
  | [] => rfl
  | a :: l => by simp only [List.map_cons, List.zip_cons_cons, List.mapM_cons, mapM_zip_map g f l]

/-- Within the trace, presence read from the index is presence read by `Scene.structure?`. -/
theorem perSceneAt_index (c : SemCtx) (ev : List (Nat × Array R)) (agg : List R → R) :
    perSceneAt c ev (fun i r => (c.d.regions.indexAt i).contains r) agg =
      perScene c ev (fun s r => (s.structure? r).isSome) agg := by
  rw [perScene_eq_perSceneAt]
  unfold perSceneAt
  apply Array.map_congr_left
  intro i hi
  have hi : i < c.d.scenes.size := by simpa [SemCtx.n, Primitives.Ctx.n] using hi
  simp only [RegionTable.indexAt_contains _ hi, SemCtx.scenes]

/-- The tabled quantifier is the direct one as a state program, for every evaluator `rec` of the
    body: the same calls of `rec` in the same order on the same cache, and the same result. -/
theorem regionArm_eq (rec : SemCtx → Formula → FastM (Array R)) (c : SemCtx) (kd : StructureKind)
    (v : String) (φ : Formula) (comb : R → R → R) (agg : List R → R) :
    regionArm rec c kd v φ comb agg = regionArmDirect rec c kd v φ comb agg := by
  have hz : (c.d.regions.rowsOf kd).ids.toList.zip (c.d.regions.rowsOf kd).isKind.toList =
      (regionsOf c kd).zip ((regionsOf c kd).map fun r => regionIsKind c r kd) := by
    rw [RegionTable.isKind_eq, Array.toList_map, RegionTable.ids_eq]; rfl
  unfold regionArm regionArmDirect
  dsimp only
  rw [hz, mapM_zip_map]
  simp only [perSceneAt_index]

mutual
  /-- `evalTAll c t`, read from the cache when its key is stored there. -/
  partial def fastT (c : SemCtx) (t : Term) : FastM (Array QR) := do
    let key := Key.ofT t c.β
    match (← get).t[key]? with
    | some v => modify (fun s => { s with hits := s.hits + 1 }); pure v
    | none =>
      let v ← fastTBody c t
      modify (fun s => Cache.putT { s with misses := s.misses + 1 } key v)
      pure v

  /-- One step of `evalTAll`, with the sub-expressions read through the cache. A term with no
      sub-expression is evaluated by `evalTAll`. -/
  partial def fastTBody (c : SemCtx) : Term → FastM (Array QR)
    | .distanceWhile subj φ =>
      match c.β.track subj with
      | none => pure (constE c.n (.unboundVariable subj))
      | some x => return Primitives.distanceWhile c.d x (← fastF c φ)
    | .sinceRise φ => return sinceRiseAll c.d.times (← fastF c φ)
    | .aggregate op v φ t => do
      let members ← (usersOf c).mapM fun u => do
        let c' := c.bindVar v (.track u)
        return (u, ← fastF c' φ, ← fastT c' t)
      return (Array.range c.n).map fun i =>
        let s := c.scenes[i]!
        aggregateAt op (members.filterMap fun (u, fa, ta) => if s.tracks.contains u then some (fa[i]!, ta[i]!) else none)
    | .add a b => return qzip Q.add (← fastT c a) (← fastT c b)
    | .sub a b => return qzip Q.sub (← fastT c a) (← fastT c b)
    | .mul a b => return qzip Q.mul (← fastT c a) (← fastT c b)
    | .div a b => do
      let x ← fastT c a
      let y ← fastT c b
      return Array.zipWith (fun x y => do
        let d ← y
        if Q.isZero d then .error (.divisionByZero "div") else pure (Q.div (← x) d)) x y
    | .neg a => return (← fastT c a).map (·.map Q.neg)
    | .abs a => return (← fastT c a).map (·.map Q.abs)
    | .cond φ a b => do
      let g ← fastF c φ
      let x ← fastT c a
      let y ← fastT c b
      return (Array.range c.n).map fun i =>
        condAt (g[i]?.getD (R.u .outOfRange)) (x[i]?.getD (.error .outOfRange)) (y[i]?.getD (.error .outOfRange))
    | t => pure (evalTAll c t)

  /-- `evalAll c φ`, read from the cache when its key is stored there. -/
  partial def fastF (c : SemCtx) (φ : Formula) : FastM (Array R) := do
    let key := Key.ofF φ c.β
    match (← get).f[key]? with
    | some v => modify (fun s => { s with hits := s.hits + 1 }); pure v
    | none =>
      let v ← fastFBody c φ
      modify (fun s => Cache.putF { s with misses := s.misses + 1 } key v)
      pure v

  /-- One step of `evalAll`, with the sub-expressions read through the cache. A formula with no
      sub-formula is evaluated by `evalAll`. -/
  partial def fastFBody (c : SemCtx) : Formula → FastM (Array R)
    | .cmp l op r => do
      let a ← fastT c l
      let b ← fastT c r
      return Array.zipWith (fun x y => match x, y with
        | .ok a, .ok b => R.ofBool (op.apply a b)
        | .error w, _ | _, .error w => R.u w) a b
    | .not φ => return mapNot (← fastF c φ)
    | .and φ ψ => do
      let a ← fastF c φ
      if a.all (·.v == .f) then return a.map (fun _ => R.f) else return zipAnd a (← fastF c ψ)
    | .or φ ψ => do
      let a ← fastF c φ
      if a.all (·.v == .t) then return a.map (fun _ => R.t) else return zipOr a (← fastF c ψ)
    | .implies φ ψ => do
      let a ← fastF c φ
      if a.all (·.v == .f) then return a.map (fun _ => R.t) else return zipImplies a (← fastF c ψ)
    | .always φ => return alwaysAll (← fastF c φ)
    | .eventually φ => return eventuallyAll (← fastF c φ)
    | .until φ ψ => do
      let a ← fastF c φ
      return untilAll a (← fastF c ψ)
    | .since φ ψ => do
      let a ← fastF c φ
      return sinceAll a (← fastF c ψ)
    | .holdsFor m d subj φ =>
      match windowOf c m d subj with
      | .error w => pure (constU c.n w)
      | .ok (x, dv) => return holdsForAll (Primitives.positions c.d m x) dv "holdsFor" (Primitives.missingPos m) (← fastF c φ)
    | .within m d subj φ =>
      match windowOf c m d subj with
      | .error w => pure (constU c.n w)
      | .ok (x, dv) => return withinAll (Primitives.positions c.d m x) dv "within" (Primitives.missingPos m) (← fastF c φ)
    | .untilWithin m d subj φ ψ =>
      match windowOf c m d subj with
      | .error w => pure (constU c.n w)
      | .ok (x, dv) => do
        let a ← fastF c φ
        return untilWithinAll (Primitives.positions c.d m x) dv "untilWithin" (Primitives.missingPos m) a (← fastF c ψ)
    | .atLast m d subj ψ φ =>
      match windowOf c m d subj with
      | .error w => pure (constU c.n w)
      | .ok (x, dv) => do
        let a ← fastF c ψ
        return atLastAll (Primitives.positions c.d m x) dv "atLast" (Primitives.missingPos m) a (← fastF c φ)
    | .count edge sinceφ op k => do
      let e ← fastF c edge
      let s ← fastF c sinceφ
      return (countEdgesAll "count" e s).map fun e => match e with
        | .error w => R.u w
        | .ok m => R.ofBool (op.apply (Q.ofInt (Int.ofNat m)) (Q.ofInt (Int.ofNat k)))
    | .rises φ => return risesAll (← fastF c φ)
    | .definedWhen pre φ => do
      let a ← fastF c pre
      return Array.zipWith definedWhenR a (← fastF c φ)
    | .existsUser v φ => do
      let ev ← (usersOf c).mapM fun t => return (t, ← fastF (c.bindVar v (.track t)) φ)
      return perScene c ev (fun s t => s.tracks.contains t) R.any
    | .forallUser v φ => do
      let ev ← (usersOf c).mapM fun t => return (t, ← fastF (c.bindVar v (.track t)) φ)
      return perScene c ev (fun s t => s.tracks.contains t) R.all
    | .existsRegion k v φ =>
      match regionKindOf k with
      | .error w => pure (constU c.n w)
      | .ok kd => regionArm fastF c kd v φ R.and R.any
    | .forallRegion k v φ =>
      match regionKindOf k with
      | .error w => pure (constU c.n w)
      | .ok kd => regionArm fastF c kd v φ R.implies R.all
    | .existsDevice k v φ =>
      match deviceKindOf k with
      | .error w => pure (constU c.n w)
      | .ok kd => do
        let ev ← (devicesOf c kd).mapM fun x =>
          return (x, Array.zipWith R.and (deviceIsKind c x kd) (← fastF (c.bindVar v (.device x)) φ))
        return perScene c ev (fun s x => (s.device x).isSome) R.any
    | .forallDevice k v φ =>
      match deviceKindOf k with
      | .error w => pure (constU c.n w)
      | .ok kd => do
        let ev ← (devicesOf c kd).mapM fun x =>
          return (x, Array.zipWith R.implies (deviceIsKind c x kd) (← fastF (c.bindVar v (.device x)) φ))
        return perScene c ev (fun s x => (s.device x).isSome) R.all
    | φ => pure (evalAll c φ)
end

/-- `evalAll c φ` through a fresh cache bounded at `cells` values, with the cache it leaves. -/
def evalFastWith (cells : Nat) (c : SemCtx) (φ : Formula) : Array R × Cache :=
  (fastF c φ).run { cap := cells }

/-- `evalAll c φ` through a fresh cache. -/
def evalFastAll (c : SemCtx) (φ : Formula) : Array R := (evalFastWith defaultCells c φ).1

/-- `evalTAll c t` through a fresh cache bounded at `cells` values. -/
def evalFastTWith (cells : Nat) (c : SemCtx) (t : Term) : Array QR × Cache :=
  (fastT c t).run { cap := cells }

end Semantics
end TrafficSpec
