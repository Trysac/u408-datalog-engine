"""Semi-naive bottom-up evaluation and DRed incremental maintenance."""

from __future__ import annotations

import operator
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from datalog_engine.ast import (
    AggregateTerm,
    Atom,
    Comparison,
    Constant,
    Rule,
    Term,
    Variable,
)
from datalog_engine.errors import ProgramLimitError

COMPARE_OPS: dict[str, Callable[[Any, Any], bool]] = {
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}


def eval_term(term: Term, binding: dict[str, Any]) -> Any:
    if isinstance(term, Constant):
        return term.value
    if isinstance(term, Variable):
        return binding[term.name]
    if isinstance(term, AggregateTerm):
        return binding[term.var.name]
    raise ValueError(f"Unknown term type {type(term)}")


def eval_comparison(cmp: Comparison, binding: dict[str, Any]) -> bool:
    try:
        left_val = eval_term(cmp.left, binding)
        right_val = eval_term(cmp.right, binding)
        return COMPARE_OPS[cmp.op](left_val, right_val)
    except (KeyError, TypeError):
        return False


class Evaluator:
    """Bottom-up evaluator supporting semi-naive fixpoint, head aggregation, and DRed."""

    def __init__(
        self,
        rules: list[Rule],
        edb_facts: dict[str, set[tuple[Any, ...]]],
        max_iterations: int = 10_000,
        max_strata: int = 100,
    ) -> None:
        self.rules = rules
        self.edb_facts = edb_facts
        self.max_iterations = max_iterations
        self.max_strata = max_strata

        # Relation store: predicate -> set of tuples
        self.relations: dict[str, set[tuple[Any, ...]]] = defaultdict(set)
        for p, facts in edb_facts.items():
            self.relations[p] = set(facts)

        # Derivation tracking for explain() and DRed:
        # (pred, tuple) -> list of (rule_id, tuple of child facts)
        self.derivations: dict[
            tuple[str, tuple[Any, ...]],
            list[tuple[str | None, tuple[tuple[str, tuple[Any, ...]], ...]]],
        ] = defaultdict(list)

    def build_indexes(self, pred: str) -> list[dict[tuple[int, Any], set[tuple[Any, ...]]]]:
        """Helper to index facts of a predicate on arguments."""
        facts = self.relations[pred]
        indexes: list[dict[tuple[int, Any], set[tuple[Any, ...]]]] = []
        for fact in facts:
            for idx, val in enumerate(fact):
                while len(indexes) <= idx:
                    indexes.append(defaultdict(set))
                indexes[idx][(idx, val)].add(fact)
        return indexes

    def evaluate_rule_body(
        self,
        rule: Rule,
        rel_view: dict[str, set[tuple[Any, ...]]],
        delta_view: dict[str, set[tuple[Any, ...]]] | None = None,
    ) -> list[tuple[dict[str, Any], tuple[tuple[str, tuple[Any, ...]], ...]]]:
        """Matches rule body against relation views. Returns list of (binding, child_facts)."""
        results: list[tuple[dict[str, Any], tuple[tuple[str, tuple[Any, ...]], ...]]] = []

        positive_atoms: list[Atom] = [
            lit for lit in rule.body if isinstance(lit, Atom) and not lit.is_negated
        ]
        negative_atoms: list[Atom] = [
            lit for lit in rule.body if isinstance(lit, Atom) and lit.is_negated
        ]
        comparisons: list[Comparison] = [lit for lit in rule.body if isinstance(lit, Comparison)]

        if not positive_atoms:
            # Rule with no positive atoms: ground fact or body-less
            # Safety check already verified facts have no variables
            binding: dict[str, Any] = {}
            if all(eval_comparison(c, binding) for c in comparisons):
                results.append((binding, ()))
            return results

        # For semi-naive evaluation, at least one atom must come from delta_view
        # if delta_view is provided. We iterate over which atom is chosen from delta.
        num_pos = len(positive_atoms)
        delta_indices = range(num_pos) if delta_view is not None else [None]

        for chosen_delta in delta_indices:
            curr_matches: list[tuple[dict[str, Any], list[tuple[str, tuple[Any, ...]]]]] = [
                ({}, [])
            ]

            for i, atom in enumerate(positive_atoms):
                if delta_view is not None and i == chosen_delta:
                    source_facts = delta_view.get(atom.predicate, set())
                else:
                    source_facts = rel_view.get(atom.predicate, set())
                if chosen_delta is not None and i < chosen_delta and delta_view is not None:
                    # Avoid duplicate derivations in semi-naive: previous atoms use old relations
                    # (rel_view \ delta_view)
                    diff_facts = rel_view.get(atom.predicate, set()) - delta_view.get(
                        atom.predicate, set()
                    )
                    source_facts = diff_facts

                next_matches: list[tuple[dict[str, Any], list[tuple[str, tuple[Any, ...]]]]] = []
                for b, children in curr_matches:
                    for fact in source_facts:
                        if len(fact) != len(atom.args):
                            continue
                        match = True
                        new_b = dict(b)
                        for arg, val in zip(atom.args, fact, strict=False):
                            if isinstance(arg, Constant):
                                if arg.value != val:
                                    match = False
                                    break
                            elif isinstance(arg, Variable):
                                if arg.name in new_b:
                                    if new_b[arg.name] != val:
                                        match = False
                                        break
                                else:
                                    new_b[arg.name] = val
                        if match:
                            next_matches.append((new_b, [*children, (atom.predicate, fact)]))
                curr_matches = next_matches
                if not curr_matches:
                    break

            # Filter matches with negative atoms and comparisons
            for b, children in curr_matches:
                # Comparisons
                if not all(eval_comparison(cmp, b) for cmp in comparisons):
                    continue
                # Negative atoms
                neg_ok = True
                for neg in negative_atoms:
                    # Check if there exists a ground fact in rel_view matching neg with binding b
                    neg_pred_facts = rel_view.get(neg.predicate, set())
                    for nf in neg_pred_facts:
                        if len(nf) != len(neg.args):
                            continue
                        m = True
                        for arg, val in zip(neg.args, nf, strict=False):
                            if (isinstance(arg, Constant) and arg.value != val) or (
                                isinstance(arg, Variable) and b.get(arg.name) != val
                            ):
                                m = False
                                break
                        if m:
                            neg_ok = False
                            break
                    if not neg_ok:
                        break
                if neg_ok:
                    results.append((b, tuple(children)))

        return results

    def evaluate_stratum(
        self, stratum_rules: list[Rule]
    ) -> tuple[dict[str, set[tuple[Any, ...]]], int]:
        """Evaluate a single stratum using semi-naive bottom-up evaluation."""
        if not stratum_rules:
            return {}, 0

        # Separate aggregate rules from relational rules
        # Head aggregation rules do not recurse within the same stratum due to stratification
        rel_rules = [
            r for r in stratum_rules if not any(isinstance(a, AggregateTerm) for a in r.head.args)
        ]
        agg_rules = [
            r for r in stratum_rules if any(isinstance(a, AggregateTerm) for a in r.head.args)
        ]

        iterations = 0
        new_stratum_facts: dict[str, set[tuple[Any, ...]]] = defaultdict(set)

        if rel_rules:
            # Initial pass: evaluate all rules against current relations
            deltas: dict[str, set[tuple[Any, ...]]] = defaultdict(set)
            for rule in rel_rules:
                matches = self.evaluate_rule_body(rule, self.relations, delta_view=None)
                for b, children in matches:
                    head_tuple = tuple(eval_term(arg, b) for arg in rule.head.args)
                    pred = rule.head.predicate
                    if head_tuple not in self.relations[pred]:
                        deltas[pred].add(head_tuple)
                        new_stratum_facts[pred].add(head_tuple)
                    # Record derivation
                    if (rule.rule_id, children) not in self.derivations[(pred, head_tuple)]:
                        self.derivations[(pred, head_tuple)].append((rule.rule_id, children))

            # Add deltas into relations
            for p, facts in deltas.items():
                self.relations[p].update(facts)

            # Semi-naive loop
            while any(deltas.values()):
                iterations += 1
                if iterations > self.max_iterations:
                    raise ProgramLimitError(
                        f"Evaluation exceeded iteration limit of {self.max_iterations}",
                        code="iteration_limit_exceeded",
                    )

                next_deltas: dict[str, set[tuple[Any, ...]]] = defaultdict(set)
                for rule in rel_rules:
                    # Check if any body atom predicate is in deltas
                    if not any(
                        isinstance(lit, Atom) and lit.predicate in deltas for lit in rule.body
                    ):
                        continue
                    matches = self.evaluate_rule_body(rule, self.relations, delta_view=deltas)
                    for b, children in matches:
                        head_tuple = tuple(eval_term(arg, b) for arg in rule.head.args)
                        pred = rule.head.predicate
                        if head_tuple not in self.relations[pred]:
                            next_deltas[pred].add(head_tuple)
                            new_stratum_facts[pred].add(head_tuple)
                        if (rule.rule_id, children) not in self.derivations[(pred, head_tuple)]:
                            self.derivations[(pred, head_tuple)].append((rule.rule_id, children))

                for p, facts in next_deltas.items():
                    self.relations[p].update(facts)
                deltas = next_deltas

        # Now evaluate aggregate rules
        for rule in agg_rules:
            matches = self.evaluate_rule_body(rule, self.relations, delta_view=None)
            # Group by non-aggregate head arguments
            # Head args can have grouping variables and at most one aggregate term
            group_map: dict[
                tuple[Any, ...], list[tuple[Any, list[tuple[str, tuple[Any, ...]]]]]
            ] = defaultdict(list)
            agg_idx = -1
            agg_op = ""
            for idx, arg in enumerate(rule.head.args):
                if isinstance(arg, AggregateTerm):
                    agg_idx = idx
                    agg_op = arg.op

            for b, children in matches:
                group_key = tuple(
                    eval_term(arg, b) for idx, arg in enumerate(rule.head.args) if idx != agg_idx
                )
                agg_val = eval_term(rule.head.args[agg_idx], b)
                group_map[group_key].append((agg_val, list(children)))

            # Compute aggregates
            for group_key, items in group_map.items():
                vals = [item[0] for item in items]
                all_children: list[tuple[str, tuple[Any, ...]]] = []
                for item in items:
                    all_children.extend(item[1])
                # Remove duplicate children preserving order
                seen_ch: set[tuple[str, tuple[Any, ...]]] = set()
                uniq_children: list[tuple[str, tuple[Any, ...]]] = []
                for ch in all_children:
                    if ch not in seen_ch:
                        seen_ch.add(ch)
                        uniq_children.append(ch)

                res_val: Any = None
                if agg_op == "count":
                    res_val = len(vals)
                elif agg_op == "sum":
                    res_val = sum(vals)
                elif agg_op == "min":
                    res_val = min(vals)
                elif agg_op == "max":
                    res_val = max(vals)

                # Reconstruct full head tuple
                full_tuple_list: list[Any] = list(group_key)
                full_tuple_list.insert(agg_idx, res_val)
                full_tuple = tuple(full_tuple_list)

                pred = rule.head.predicate
                self.relations[pred].add(full_tuple)
                new_stratum_facts[pred].add(full_tuple)
                self.derivations[(pred, full_tuple)].append((rule.rule_id, tuple(uniq_children)))

        return new_stratum_facts, iterations

    def evaluate_all(self, strata: list[list[Rule]]) -> None:
        """Evaluate all strata in order from base to top."""
        for stratum_rules in strata:
            self.evaluate_stratum(stratum_rules)

    def dred_retract(
        self,
        retracted: dict[str, set[tuple[Any, ...]]],
        strata: list[list[Rule]],
    ) -> None:
        """DRed (Delete and Rederive) incremental maintenance algorithm for fact deletions."""
        # Flatten all rules
        all_rules = [r for st in strata for r in st]

        # Step 1: Deletion propagation (overestimate deleted facts)
        deleted: dict[str, set[tuple[Any, ...]]] = defaultdict(set)
        deltas: dict[str, set[tuple[Any, ...]]] = defaultdict(set)
        for p, facts in retracted.items():
            deleted[p].update(facts)
            deltas[p].update(facts)

        while any(deltas.values()):
            next_deltas: dict[str, set[tuple[Any, ...]]] = defaultdict(set)
            for rule in all_rules:
                if any(isinstance(a, AggregateTerm) for a in rule.head.args):
                    continue
                if not any(isinstance(lit, Atom) and lit.predicate in deltas for lit in rule.body):
                    continue
                matches = self.evaluate_rule_body(rule, self.relations, delta_view=deltas)
                for b, _children in matches:
                    head_t = tuple(eval_term(arg, b) for arg in rule.head.args)
                    pred = rule.head.predicate
                    if head_t in self.relations[pred] and head_t not in deleted[pred]:
                        deleted[pred].add(head_t)
                        next_deltas[pred].add(head_t)
            deltas = next_deltas

        # Remove deleted facts tentatively from relations
        for p, facts in deleted.items():
            self.relations[p] -= facts

        # Step 2: Rederivation (check if any deleted fact has alternative valid derivation)
        rederived: dict[str, set[tuple[Any, ...]]] = defaultdict(set)
        for p, facts in deleted.items():
            for f in facts:
                # Is it an EDB fact?
                if f in self.edb_facts.get(p, set()):
                    rederived[p].add(f)
                    self.relations[p].add(f)
                    continue

                for rule in all_rules:
                    if rule.head.predicate != p:
                        continue
                    if any(isinstance(a, AggregateTerm) for a in rule.head.args):
                        continue
                    matches = self.evaluate_rule_body(rule, self.relations, delta_view=None)
                    derived_now = False
                    for b, children in matches:
                        head_t = tuple(eval_term(arg, b) for arg in rule.head.args)
                        if head_t == f:
                            rederived[p].add(f)
                            self.relations[p].add(f)
                            self.derivations[(p, f)] = [(rule.rule_id, children)]
                            derived_now = True
                            break
                    if derived_now:
                        break

        # Step 3: Propagation of rederived facts using semi-naive evaluation
        deltas = defaultdict(set, {p: set(facts) for p, facts in rederived.items()})
        while any(deltas.values()):
            rederrived_next_deltas: defaultdict[str, set[tuple[Any, ...]]] = defaultdict(set)
            for rule in all_rules:
                if any(isinstance(a, AggregateTerm) for a in rule.head.args):
                    continue
                if not any(isinstance(lit, Atom) and lit.predicate in deltas for lit in rule.body):
                    continue
                matches = self.evaluate_rule_body(rule, self.relations, delta_view=deltas)
                for b, children in matches:
                    head_tuple = tuple(eval_term(arg, b) for arg in rule.head.args)
                    pred = rule.head.predicate
                    if head_tuple not in self.relations[pred]:
                        rederrived_next_deltas[pred].add(head_tuple)
                        self.relations[pred].add(head_tuple)
                    self.derivations[(pred, head_tuple)] = [(rule.rule_id, children)]
            deltas = rederrived_next_deltas

        # Re-evaluate any strata with aggregates if needed
        has_any_agg = any(
            any(isinstance(a, AggregateTerm) for a in r.head.args) for st in strata for r in st
        )
        if has_any_agg:
            for stratum_rules in strata:
                agg_in_stratum = [
                    r
                    for r in stratum_rules
                    if any(isinstance(a, AggregateTerm) for a in r.head.args)
                ]
                if agg_in_stratum:
                    for r in agg_in_stratum:
                        self.relations[r.head.predicate].clear()
                    self.evaluate_stratum(stratum_rules)

        # Clean up derivations for permanently removed facts
        for p, facts in deleted.items():
            for f in facts:
                if f not in self.relations[p] and (p, f) in self.derivations:
                    del self.derivations[(p, f)]
