"""Main Datalog Engine API."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from typing import Any

from datalog_engine.ast import Atom, Constant, DerivationNode, Rule, Variable
from datalog_engine.errors import DatalogError, ParseError, ProgramLimitError
from datalog_engine.evaluator import Evaluator, eval_term
from datalog_engine.parser import parse
from datalog_engine.stratification import stratify, validate_safety


class Engine:
    """stratified Datalog engine with incremental updates and derivation explanations."""

    def __init__(
        self,
        *,
        max_program_bytes: int = 1_000_000,
        max_iterations: int = 10_000,
        max_strata: int = 100,
        max_arity: int = 32,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.max_program_bytes = max_program_bytes
        self.max_iterations = max_iterations
        self.max_strata = max_strata
        self.max_arity = max_arity
        self.on_event = on_event

        self.rules: list[Rule] = []
        self.edb_facts: dict[str, set[tuple[Any, ...]]] = defaultdict(set)
        self.strata: list[list[Rule]] = []
        self.evaluator: Evaluator = Evaluator(
            rules=[],
            edb_facts=self.edb_facts,
            max_iterations=self.max_iterations,
            max_strata=self.max_strata,
        )

    def _emit(self, event_name: str, **kwargs: Any) -> None:
        if self.on_event is not None:
            payload = {"event": event_name, **kwargs}
            self.on_event(payload)

    def load(self, text: str) -> None:
        """Load and parse a Datalog program text, stratify rules, and evaluate."""
        encoded_bytes = len(text.encode("utf-8"))
        if encoded_bytes > self.max_program_bytes:
            raise ProgramLimitError(
                f"Program size {encoded_bytes} bytes exceeds limit of {self.max_program_bytes}",
                code="program_size_exceeded",
            )

        rules, _queries = parse(text, max_arity=self.max_arity)

        # Assign rule ids: '<head predicate>/<1-based index among that predicate\'s rules>'
        pred_rule_count: dict[str, int] = defaultdict(int)
        indexed_rules: list[Rule] = []
        facts_to_add: dict[str, set[tuple[Any, ...]]] = defaultdict(set)

        for r in rules:
            if not r.body and not any(isinstance(a, Variable) for a in r.head.args):
                # Ground fact
                ground_vals = tuple(eval_term(a, {}) for a in r.head.args)
                facts_to_add[r.head.predicate].add(ground_vals)
            else:
                pred_rule_count[r.head.predicate] += 1
                rule_id = f"{r.head.predicate}/{pred_rule_count[r.head.predicate]}"
                indexed_rules.append(Rule(head=r.head, body=r.body, rule_id=rule_id))

        # Validate safety
        validate_safety(indexed_rules)

        # Stratify
        all_edb = set(self.edb_facts.keys()) | set(facts_to_add.keys())
        strata = stratify(indexed_rules, edb_predicates=all_edb, max_strata=self.max_strata)

        self.rules = indexed_rules
        self.strata = strata
        for p, facts in facts_to_add.items():
            self.edb_facts[p].update(facts)

        # Re-initialize evaluator
        self.evaluator = Evaluator(
            rules=self.rules,
            edb_facts=self.edb_facts,
            max_iterations=self.max_iterations,
            max_strata=self.max_strata,
        )
        for p, facts in self.edb_facts.items():
            for f in facts:
                self.evaluator.derivations[(p, f)].append((None, ()))

        self.evaluator.evaluate_all(self.strata)
        self._emit("load", rules_count=len(self.rules), strata_count=len(self.strata))

    def add_facts(self, predicate: str, rows: Iterable[tuple[Any, ...]]) -> int:
        """Add ground facts incrementally and update derivations."""
        new_facts: set[tuple[Any, ...]] = set()
        for row in rows:
            tup = tuple(row)
            if len(tup) > self.max_arity:
                raise ParseError(f"Fact arity exceeds maximum {self.max_arity}")
            if tup not in self.edb_facts[predicate]:
                new_facts.add(tup)
                self.edb_facts[predicate].add(tup)
                self.evaluator.relations[predicate].add(tup)
                self.evaluator.derivations[(predicate, tup)].append((None, ()))

        if not new_facts:
            return 0

        # Semi-naive propagation for new facts across all strata
        deltas: dict[str, set[tuple[Any, ...]]] = defaultdict(set)
        deltas[predicate] = set(new_facts)

        all_rules = [r for st in self.strata for r in st]
        while any(deltas.values()):
            next_deltas: dict[str, set[tuple[Any, ...]]] = defaultdict(set)
            for rule in all_rules:
                if not any(isinstance(lit, Atom) and lit.predicate in deltas for lit in rule.body):
                    continue
                matches = self.evaluator.evaluate_rule_body(
                    rule, self.evaluator.relations, delta_view=deltas
                )
                for b, children in matches:
                    head_tuple = tuple(eval_term(arg, b) for arg in rule.head.args)
                    pred = rule.head.predicate
                    if head_tuple not in self.evaluator.relations[pred]:
                        next_deltas[pred].add(head_tuple)
                        self.evaluator.relations[pred].add(head_tuple)
                    if (rule.rule_id, children) not in self.evaluator.derivations[
                        (pred, head_tuple)
                    ]:
                        self.evaluator.derivations[(pred, head_tuple)].append(
                            (rule.rule_id, children)
                        )
            deltas = next_deltas

        self._emit("add_facts", predicate=predicate, count=len(new_facts))
        return len(new_facts)

    def retract_facts(self, predicate: str, rows: Iterable[tuple[Any, ...]]) -> int:
        """Retract facts using the incremental DRed algorithm."""
        to_retract: set[tuple[Any, ...]] = set()
        for row in rows:
            tup = tuple(row)
            if tup in self.edb_facts.get(predicate, set()):
                to_retract.add(tup)
                self.edb_facts[predicate].remove(tup)

        if not to_retract:
            return 0

        self.evaluator.dred_retract({predicate: to_retract}, self.strata)
        self._emit("retract_facts", predicate=predicate, count=len(to_retract))
        return len(to_retract)

    def query(self, query_str: str) -> list[dict[str, Any]]:
        """Evaluate a query string like 'path(\'a\', X)?' and return list of binding dicts."""
        query_str = query_str.strip()
        if not query_str:
            return []
        if not query_str.endswith("?"):
            query_str += "?"

        _rules, queries = parse(query_str, max_arity=self.max_arity)
        if not queries:
            return []
        query_atom = queries[0]

        pred = query_atom.predicate
        facts = self.evaluator.relations.get(pred, set())
        results: list[dict[str, Any]] = []

        for fact in facts:
            if len(fact) != len(query_atom.args):
                continue
            binding: dict[str, Any] = {}
            match = True
            for arg, val in zip(query_atom.args, fact, strict=False):
                if isinstance(arg, Constant):
                    if arg.value != val:
                        match = False
                        break
                elif isinstance(arg, Variable):
                    if arg.name in binding:
                        if binding[arg.name] != val:
                            match = False
                            break
                    else:
                        binding[arg.name] = val
            if match:
                results.append(binding)

        # Sort results deterministically by values representation
        results.sort(key=lambda d: [str(d[k]) for k in sorted(d.keys())])
        self._emit("query", predicate=pred, results_count=len(results))
        return results

    def explain(self, fact: tuple[str, tuple[Any, ...]]) -> DerivationNode:
        """Construct a derivation explanation tree for a given fact."""
        pred, args = fact
        args_tuple = tuple(args)
        key = (pred, args_tuple)

        if key not in self.evaluator.derivations or not self.evaluator.derivations[key]:
            raise DatalogError(
                f"Fact {fact} was not derived or does not exist", code="unknown_fact"
            )

        # Pick the first valid derivation
        rule_id, children_tuples = self.evaluator.derivations[key][0]
        is_fact = rule_id is None

        children_nodes: list[DerivationNode] = []
        # Avoid infinite cycles during proof construction
        visited: set[tuple[str, tuple[Any, ...]]] = {key}

        def build_tree(current_fact: tuple[str, tuple[Any, ...]]) -> DerivationNode:
            c_derivs = self.evaluator.derivations.get(current_fact, [])
            if not c_derivs:
                return DerivationNode(fact=current_fact, rule_id=None, children=[], is_fact=True)
            c_rule_id, c_children = c_derivs[0]
            c_is_fact = c_rule_id is None
            c_nodes: list[DerivationNode] = []
            for ch in c_children:
                if ch not in visited:
                    visited.add(ch)
                    c_nodes.append(build_tree(ch))
                else:
                    c_nodes.append(DerivationNode(fact=ch, rule_id=None, children=[], is_fact=True))
            return DerivationNode(
                fact=current_fact, rule_id=c_rule_id, children=c_nodes, is_fact=c_is_fact
            )

        for ch in children_tuples:
            visited.add(ch)
            children_nodes.append(build_tree(ch))

        return DerivationNode(fact=key, rule_id=rule_id, children=children_nodes, is_fact=is_fact)
