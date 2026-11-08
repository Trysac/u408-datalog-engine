"""Safety checks and stratification of Datalog programs using Tarjan's SCC algorithm."""

from __future__ import annotations

from collections import defaultdict

from datalog_engine.ast import AggregateTerm, Atom, Comparison, Rule, Term, Variable
from datalog_engine.errors import SafetyError, StratificationError


def get_term_vars(term: Term) -> set[str]:
    if isinstance(term, Variable):
        return {term.name}
    if isinstance(term, AggregateTerm):
        return {term.var.name}
    return set()


def validate_safety(rules: list[Rule]) -> None:
    """Validate range restriction: every head variable and negative/comparison variable
    must appear in a positive relational body atom.
    """
    for rule in rules:
        positive_vars: set[str] = set()
        for lit in rule.body:
            if isinstance(lit, Atom) and not lit.is_negated:
                for arg in lit.args:
                    positive_vars |= get_term_vars(arg)

        # Head variables check
        for arg in rule.head.args:
            head_vars = get_term_vars(arg)
            diff = head_vars - positive_vars
            if diff and rule.body:
                raise SafetyError(
                    f"Variable {diff.pop()} in rule head not bound in positive body atoms"
                )
            # If rule has no body (it is a fact), head cannot have variables
            if diff and not rule.body:
                raise SafetyError(f"Variable {diff.pop()} not allowed in ground fact")

        # Body checks (negated atoms & comparisons)
        for lit in rule.body:
            if isinstance(lit, Atom) and lit.is_negated:
                neg_vars = set().union(*(get_term_vars(a) for a in lit.args))
                diff = neg_vars - positive_vars
                if diff:
                    raise SafetyError(
                        f"Variable {diff.pop()} in negated atom not bound in positive body atoms"
                    )
            elif isinstance(lit, Comparison):
                cmp_vars = get_term_vars(lit.left) | get_term_vars(lit.right)
                diff = cmp_vars - positive_vars
                if diff:
                    raise SafetyError(
                        f"Variable {diff.pop()} in comparison filter not bound in body"
                    )


def stratify(
    rules: list[Rule], edb_predicates: set[str], max_strata: int = 100
) -> list[list[Rule]]:
    """Partition rules into stratified strata such that negation and aggregates
    depend strictly on lower strata.
    """
    all_predicates: set[str] = set(edb_predicates)
    for r in rules:
        all_predicates.add(r.head.predicate)
        for lit in r.body:
            if isinstance(lit, Atom):
                all_predicates.add(lit.predicate)

    # Graph edges: p -> [(q, is_strict)]
    # Edge head -> body predicate
    # is_strict is True if negation or aggregate
    adj: dict[str, list[tuple[str, bool]]] = defaultdict(list)
    has_aggregate: set[str] = set()

    for r in rules:
        h = r.head.predicate
        has_agg = any(isinstance(a, AggregateTerm) for a in r.head.args)
        if has_agg:
            has_aggregate.add(h)
        for lit in r.body:
            if isinstance(lit, Atom):
                b = lit.predicate
                is_strict = lit.is_negated or has_agg
                adj[h].append((b, is_strict))

    # Tarjan's SCC algorithm on the predicate dependency graph
    index = 0
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    on_stack: dict[str, bool] = {}
    stack: list[str] = []
    sccs: list[list[str]] = []

    def strongconnect(v: str) -> None:
        nonlocal index
        indices[v] = index
        lowlink[v] = index
        index += 1
        stack.append(v)
        on_stack[v] = True

        for w, _strict in adj[v]:
            if w not in indices:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif on_stack.get(w, False):
                lowlink[v] = min(lowlink[v], indices[w])

        if lowlink[v] == indices[v]:
            scc: list[str] = []
            while True:
                w = stack.pop()
                on_stack[w] = False
                scc.append(w)
                if w == v:
                    break
            sccs.append(scc)

    for p in all_predicates:
        if p not in indices:
            strongconnect(p)

    # Check for strict edges within the same SCC
    scc_map: dict[str, int] = {}
    for i, scc in enumerate(sccs):
        for pred in scc:
            scc_map[pred] = i

    for u in all_predicates:
        for v, is_strict in adj[u]:
            if scc_map[u] == scc_map[v] and is_strict:
                raise StratificationError(
                    f"Cycle through negation or aggregation detected involving {u} and {v}",
                    code="stratification_cycle",
                )

    # Compute stratum levels for each SCC using topological sort / longest path
    # DAG of SCCs: edge from scc_map[u] to scc_map[v] where u depends on v
    # If u depends strictly on v, stratum(u) >= stratum(v) + 1
    # If u depends non-strictly on v, stratum(u) >= stratum(v)
    stratum: dict[str, int] = {p: 0 for p in all_predicates}

    changed = True
    iterations = 0
    while changed:
        changed = False
        iterations += 1
        if iterations > max_strata:
            raise StratificationError(
                f"Stratification layers exceeded maximum of {max_strata}",
                code="stratification_cycle",
            )
        for u in all_predicates:
            for v, is_strict in adj[u]:
                required = stratum[v] + (1 if is_strict else 0)
                if stratum[u] < required:
                    stratum[u] = required
                    changed = True

    max_level = max(stratum.values()) if stratum else 0
    if max_level >= max_strata:
        raise StratificationError(
            f"Stratification layers {max_level + 1} exceeded maximum {max_strata}",
            code="stratification_cycle",
        )

    # Group rules by stratum of head predicate
    strata_rules: list[list[Rule]] = [[] for _ in range(max_level + 1)]
    for r in rules:
        lvl = stratum[r.head.predicate]
        strata_rules[lvl].append(r)

    return strata_rules
