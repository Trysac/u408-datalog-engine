"""Abstract syntax tree and data structures for Datalog programs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, NamedTuple


class DerivationNode(NamedTuple):
    """Node in a derivation explanation tree."""

    fact: tuple[str, tuple[Any, ...]]
    rule_id: str | None
    children: list[DerivationNode]
    is_fact: bool

    def to_dict(self) -> dict[str, Any]:
        """Serialize node to dictionary."""
        return {
            "predicate": self.fact[0],
            "args": list(self.fact[1]),
            "rule_id": self.rule_id,
            "is_fact": self.is_fact,
            "children": [child.to_dict() for child in self.children],
        }


@dataclass(frozen=True)
class Term:
    """Abstract base for terms in literals."""

    pass


@dataclass(frozen=True)
class Constant(Term):
    """Ground constant value (int, str, bool, etc.)."""

    value: Any

    def __repr__(self) -> str:
        return repr(self.value)


@dataclass(frozen=True)
class Variable(Term):
    """Logical variable."""

    name: str

    def __repr__(self) -> str:
        return self.name


@dataclass(frozen=True)
class AggregateTerm(Term):
    """Aggregate function term in head (e.g. sum<S>, count<X>)."""

    op: str  # 'count', 'sum', 'min', 'max'
    var: Variable

    def __repr__(self) -> str:
        return f"{self.op}<{self.var.name}>"


@dataclass(frozen=True)
class Literal:
    """Base literal."""

    pass


@dataclass(frozen=True)
class Atom(Literal):
    """Positive or negative predicate atom."""

    predicate: str
    args: tuple[Term, ...]
    is_negated: bool = False

    def __repr__(self) -> str:
        prefix = "not " if self.is_negated else ""
        args_str = ", ".join(str(a) for a in self.args)
        return f"{prefix}{self.predicate}({args_str})"


@dataclass(frozen=True)
class Comparison(Literal):
    """Built-in comparison literal, e.g. X != Y or S > 5."""

    op: str  # '==', '!=', '<', '<=', '>', '>='
    left: Term
    right: Term

    def __repr__(self) -> str:
        return f"{self.left} {self.op} {self.right}"


@dataclass(frozen=True)
class Rule:
    """Datalog rule: head :- body."""

    head: Atom
    body: tuple[Literal, ...]
    rule_id: str | None = None

    def __repr__(self) -> str:
        body_str = ", ".join(str(lit) for lit in self.body)
        return f"{self.head} :- {body_str}."
