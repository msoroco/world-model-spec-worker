/-
  TrafficSpec.Core.Language.Export
  The specification language as JSON, for the tooling that renders a formula in prose, compares
  bodies structurally, or checks a rule outside Lean. One encoder per constructor;
  `Decode.formula` reads this JSON back strictly, so a decoded formula exported again is canonical.
  A rule's `sampled_duration` says whether its formulas as given read `durationWithin`; the
  monitor's mark of a verdict adds the concept bodies and the rules it reads.
-/
import Lean.Data.Json
import TrafficSpec.Core.Language.Concept

namespace TrafficSpec
open Lean

def Arg.toJson : Arg → Json
  | .var v => Json.mkObj [("var", v)]
  | .lit s => Json.mkObj [("lit", s)]
  | .nat n => Json.mkObj [("nat", n)]

def CmpOp.toJson : CmpOp → Json
  | .lt => "lt" | .le => "le" | .eq => "eq" | .ge => "ge" | .gt => "gt"

def Measure.toJson : Measure → Json
  | .time => "time" | .path => "path"

def PUnit'.toJson : PUnit' → Json
  | .metre => "metre" | .second => "second" | .metrePerSecond => "metre_per_second"
  | .metrePerSecondSq => "metre_per_second_sq" | .degree => "degree" | .degreePerSecond => "degree_per_second"
  | .perMetre => "per_metre" | .kilogram => "kilogram"
  | .ratio => "ratio" | .count => "count"

def Q.toJson (q : Q) : Json := Json.mkObj [("num", q.num), ("den", q.den)]

private def args (as : List Arg) : Json := Json.arr (as.map Arg.toJson).toArray

def RuleScope.toJson : RuleScope → Json
  | .every => "every"
  | .subjectClass a => Json.mkObj [("subject_class", a)]
  | .asClass a => Json.mkObj [("as_class", a)]
  | .purpose p => Json.mkObj [("purpose", p.toString)]
  | .asClassPurpose a p => Json.mkObj [("as_class", a), ("purpose", p.toString)]

mutual
  partial def Term.toJson : Term → Json
    | .lit q u => Json.mkObj [("lit", q.toJson), ("unit", u.toJson)]
    | .param p => Json.mkObj [("param", p)]
    | .measure a as => Json.mkObj [("measure", a), ("args", args as)]
    | .quantity c as ps => Json.mkObj [("quantity", c), ("args", args as), ("params", Json.arr (ps.map Term.toJson).toArray)]
    | .distanceWhile s φ => Json.mkObj [("distance_while", s), ("holds", Formula.toJson φ)]
    | .sinceRise φ => Json.mkObj [("since_rise", Formula.toJson φ)]
    | .headingSince s g ψ => Json.mkObj [("heading_since", s), ("max_step", g.toJson), ("onset", Formula.toJson ψ)]
    | .aggregate op v φ t => Json.mkObj [("aggregate", op.toString), ("var", v), ("where", Formula.toJson φ), ("of", t.toJson)]
    | .add a b => Json.mkObj [("add", Json.arr #[a.toJson, b.toJson])]
    | .sub a b => Json.mkObj [("sub", Json.arr #[a.toJson, b.toJson])]
    | .mul a b => Json.mkObj [("mul", Json.arr #[a.toJson, b.toJson])]
    | .div a b => Json.mkObj [("div", Json.arr #[a.toJson, b.toJson])]
    | .neg a => Json.mkObj [("neg", a.toJson)]
    | .abs a => Json.mkObj [("abs", a.toJson)]
    | .cond φ a b => Json.mkObj [("cond", Formula.toJson φ), ("then", a.toJson), ("else", b.toJson)]
  partial def Formula.toJson : Formula → Json
    | .tt => "tt"
    | .ff => "ff"
    | .atom n as ps => Json.mkObj [("atom", n), ("args", args as), ("params", Json.arr (ps.map Term.toJson).toArray)]
    | .cmp l op r => Json.mkObj [("cmp", op.toJson), ("lhs", l.toJson), ("rhs", r.toJson)]
    | .asm id => Json.mkObj [("asm", id)]
    | .intent id who target => Json.mkObj [("int", id), ("args", Json.arr #[who.toJson, target.toJson])]
    | .fact id xs => Json.mkObj [("fact", id), ("args", args xs)]
    | .same a b => Json.mkObj [("same", Json.arr #[a.toJson, b.toJson])]
    | .not φ => Json.mkObj [("not", φ.toJson)]
    | .and φ ψ => Json.mkObj [("and", Json.arr #[φ.toJson, ψ.toJson])]
    | .or φ ψ => Json.mkObj [("or", Json.arr #[φ.toJson, ψ.toJson])]
    | .implies φ ψ => Json.mkObj [("implies", Json.arr #[φ.toJson, ψ.toJson])]
    | .always φ => Json.mkObj [("always", φ.toJson)]
    | .eventually φ => Json.mkObj [("eventually", φ.toJson)]
    | .until φ ψ => Json.mkObj [("until", Json.arr #[φ.toJson, ψ.toJson])]
    | .since φ ψ => Json.mkObj [("since", Json.arr #[φ.toJson, ψ.toJson])]
    | .holdsFor m d s φ => Json.mkObj [("holds_for", m.toJson), ("length", d.toJson), ("subject", s), ("body", φ.toJson)]
    | .within m d s φ => Json.mkObj [("within", m.toJson), ("length", d.toJson), ("subject", s), ("body", φ.toJson)]
    | .untilWithin m d s φ ψ =>
      Json.mkObj [("until_within", m.toJson), ("length", d.toJson), ("subject", s), ("hold", φ.toJson), ("reach", ψ.toJson)]
    | .atLast m d s ψ φ =>
      Json.mkObj [("at_last", m.toJson), ("length", d.toJson), ("subject", s), ("when", ψ.toJson), ("body", φ.toJson)]
    | .count e s op n => Json.mkObj [("count", e.toJson), ("since", s.toJson), ("op", op.toJson), ("n", n)]
    | .durationWithin w g φ op b =>
      Json.mkObj [("duration_within", φ.toJson), ("length", w.toJson), ("step", g.toJson), ("op", op.toJson), ("bound", b.toJson)]
    | .rises φ => Json.mkObj [("rises", φ.toJson)]
    | .definedWhen p φ => Json.mkObj [("defined_when", p.toJson), ("body", φ.toJson)]
    | .derived c as ps => Json.mkObj [("derived", c), ("args", args as), ("params", Json.arr (ps.map Term.toJson).toArray)]
    | .rule id map => Json.mkObj [("rule", id), ("map", Json.mkObj (map.map fun (i, o) => (i, Json.str o)))]
    | .ruleApplies id map => Json.mkObj [("rule_applies", id), ("map", Json.mkObj (map.map fun (i, o) => (i, Json.str o)))]
    | .requiredBy k who => Json.mkObj [("required_by", k.toString), ("who", who)]
    | .lawful sc who => Json.mkObj [("lawful", RuleScope.toJson sc), ("who", who)]
    | .ruleCase id n map => Json.mkObj [("rule_case", id), ("case", n), ("map", Json.mkObj (map.map fun (i, o) => (i, Json.str o)))]
    | .existsUser v φ => Json.mkObj [("exists_user", v), ("body", φ.toJson)]
    | .forallUser v φ => Json.mkObj [("forall_user", v), ("body", φ.toJson)]
    | .existsRegion k v φ => Json.mkObj [("exists_region", k.toJson), ("var", v), ("body", φ.toJson)]
    | .forallRegion k v φ => Json.mkObj [("forall_region", k.toJson), ("var", v), ("body", φ.toJson)]
    | .existsDevice k v φ => Json.mkObj [("exists_device", k.toJson), ("var", v), ("body", φ.toJson)]
    | .forallDevice k v φ => Json.mkObj [("forall_device", k.toJson), ("var", v), ("body", φ.toJson)]
end

def ArgSort.toJson : ArgSort → Json
  | .track => Json.mkObj [("sort", "track")]
  | .region => Json.mkObj [("sort", "region")]
  | .literal vs => Json.mkObj [("sort", "literal"), ("values", Json.arr (vs.map Json.str).toArray)]
  | .nat => Json.mkObj [("sort", "nat")]

def Narrowing.toJson (n : Narrowing) : Json := Json.mkObj [("span", n.span), ("why", n.why), ("kind", n.kind)]

def Concept.toJson (c : Concept) : Json :=
  Json.mkObj
    [ ("id", c.id), ("contract", c.contract)
    , ("definition", match c.definition with | some d => Json.str d | none => Json.null)
    , ("args", Json.arr (c.args.map fun (n, s) => Json.mkObj [("name", n), ("sort", s.toJson)]).toArray)
    , ("params", Json.arr (c.params.map fun p => Json.mkObj [("name", p.name), ("unit", p.unit.toJson)]).toArray)
    , ("kind", match c.body with | .formula _ => "formula" | .quantity _ => "quantity")
    , ("body", match c.body with | .formula φ => φ.toJson | .quantity t => t.toJson)
    , ("residues", Json.arr (c.residues.map Json.str).toArray)
    , ("narrowings", Json.arr (c.narrowings.map Narrowing.toJson).toArray)
    , ("supersedes", match c.supersedes with | some s => Json.str s | none => Json.null) ]

def CaseKind.toJson : CaseKind → Json
  | .requires k => Json.mkObj [("requires", k.toString)]
  | .permits => "permits"

def RuleCase.toJson (c : RuleCase) : Json :=
  Json.mkObj [("name", c.name), ("kind", c.kind.toJson), ("shown", c.shown.toJson), ("when", c.when.toJson)]

def Rule.toJson (r : Rule) : Json :=
  Json.mkObj
    [ ("id", r.id), ("laws", Json.arr (r.laws.map Json.str).toArray)
    , ("binders", Json.arr (r.binders.map fun b => Json.mkObj [("name", b.name), ("cls", b.cls.toJson)]).toArray)
    , ("applicability", r.applicability.toJson), ("obligation", r.obligation.toJson)
    , ("cases", Json.arr (r.cases.map RuleCase.toJson).toArray), ("permission", r.permission)
    , ("purposes", Json.arr (r.purposes.map fun p => Json.str p.toString).toArray)
    , ("assumptions", Json.arr (r.assumptions.map Json.str).toArray)
    , ("intentions", Json.arr (r.intentions.map Json.str).toArray)
    , ("facts", Json.arr (r.facts.map Json.str).toArray)
    , ("residues", Json.arr (r.residues.map Json.str).toArray)
    , ("narrowings", Json.arr (r.narrowings.map Narrowing.toJson).toArray), ("surrogate", r.surrogate)
    , ("abstractions", Json.arr (r.abstractions.map Json.str).toArray)
    , ("sampled_duration", r.formulas.any Formula.readsDuration) ]

end TrafficSpec
