/-
  TrafficSpec.Core.Evidence.Adequacy
  Mutation adequacy of a rule's witnesses: every leaf of the applicability and the obligation
  must do some work in some witness. A leaf is replaced by `tt` and by `ff` in turn; if neither
  replacement changes any scenario's episode verdict, the leaf is unexercised — the witnesses do
  not show that it matters, and a rule could carry an irrelevant atom without anyone noticing.
  Only the witnesses that expect a decided verdict count: a witness that expects unknown under a
  mask is decided by blanking any leaf that reads the masked atom, so it exercises nothing.

  A concept call is one leaf: the rule's witnesses must show the concept matters, and the
  concept's own witnesses exercise its body.

  Leaves of one atom that differ only in a literal argument (the values of one enumeration, each
  tested in its own disjunct) are one leaf in meaning: the family is unexercised only when none of
  its members moves a witness, and it is reported once.

  Only the gate reads this file; rules never import it.
-/
import TrafficSpec.Core.Evidence.Builders

namespace TrafficSpec
namespace Adequacy

/-- The verdict tags a scenario list produces for a rule. -/
def profile (rules : List Rule) (r : Rule) (scs : List Scenario) (cs : List Concept := []) : List String :=
  scs.map fun sc =>
    match sc.run ((rules.filter (·.id != r.id)) ++ [r]) cs with
    | .ok v => v.tag
    | .error e => s!"error:{e}"

/-- A leaf's family: its description with every literal argument blanked, so the leaves that
    test the values of one enumeration on the same atom and variables share a family. -/
def family (leaf : String) : String :=
  let marker := "Arg.lit \""
  match leaf.splitOn marker with
  | [] => leaf
  | first :: rest =>
    rest.foldl (fun acc piece =>
      let after := (piece.splitOn "\"").drop 1      -- drop the literal's text, keep what follows its closing quote
      acc ++ marker ++ "_\"" ++ "\"".intercalate after) first

/-- Leaves of the applicability and the obligation (binder classes are exercised by the
    grounding itself) that neither `tt` nor `ff` replacement moves any witness on; a family of
    literal variants counts once and only when no member moves. -/
def unexercised (rules : List Rule) (r : Rule) (scs : List Scenario) (cs : List Concept := []) : List String :=
  let decided := scs.filter fun sc => sc.expected.tag != "unknown"
  let base := profile rules r decided cs
  let check (label : String) (get : Rule → Formula) (put : Rule → Formula → Rule) : List String :=
    let φ := get r
    let names := Formula.leaves φ
    let moved : List Bool := (List.range (Formula.leafCount φ)).map fun k =>
      [Formula.tt, Formula.ff].any fun rep =>
        profile rules (put r (Formula.replaceLeaf k rep φ)) decided cs != base
    let fams := names.map family
    (List.range names.length).filterMap fun k =>
      if moved[k]?.getD true then none
      else
        let fam := fams[k]?.getD ""
        let members := (List.range names.length).filter fun j => fams[j]?.getD "" == fam
        if members.any (fun j => moved[j]?.getD false) then none      -- a variant of the same atom moved a witness
        else if members.head? != some k then none                       -- the family is reported once, at its first leaf
        else
          let note := if members.length > 1 then s!" (one of {members.length} literal variants of this atom; none exercised)" else ""
          some s!"{label} leaf {k}: {names[k]?.getD ""}{note}"
  check "applicability" (·.applicability) (fun r φ => { r with applicability := φ }) ++
  check "obligation" (·.obligation) (fun r φ => { r with obligation := φ })

end Adequacy
end TrafficSpec
