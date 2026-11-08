"""Lexer and parser for Datalog programs."""

from __future__ import annotations

import re

from datalog_engine.ast import (
    AggregateTerm,
    Atom,
    Comparison,
    Constant,
    Literal,
    Rule,
    Term,
    Variable,
)
from datalog_engine.errors import ParseError

TOKEN_SPEC = [
    ("COMMENT_PCT", r"%[^\n]*"),
    ("COMMENT_SLASH", r"//[^\n]*"),
    ("ARROW", r":-"),
    ("NEQ", r"!=|/="),
    ("LTE", r"<="),
    ("GTE", r">="),
    ("LT", r"<"),
    ("GT", r">"),
    ("EQ", r"==|="),
    ("NOT", r"\bnot\b"),
    ("AGG_OP", r"\b(count|sum|min|max)\b"),
    ("IDENT", r"[a-z_][a-zA-Z0-9_]*"),
    ("VAR", r"[A-Z][a-zA-Z0-9_]*"),
    ("NUMBER", r"-?[0-9]+"),
    ("STRING", r"'([^'\\]|\\.)*'"),
    ("LPAREN", r"\("),
    ("RPAREN", r"\)"),
    ("COMMA", r","),
    ("DOT", r"\."),
    ("QUERY", r"\?"),
    ("WS", r"\s+"),
]

TOKEN_RE = re.compile("|".join(f"(?P<{name}>{pattern})" for name, pattern in TOKEN_SPEC))


class Token:
    def __init__(self, type_: str, value: str, pos: int) -> None:
        self.type = type_
        self.value = value
        self.pos = pos

    def __repr__(self) -> str:
        return f"Token({self.type}, {self.value!r})"


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    for match in TOKEN_RE.finditer(text):
        kind = match.lastgroup
        val = match.group()
        pos = match.start()
        if kind is None or kind in ("COMMENT_PCT", "COMMENT_SLASH", "WS"):
            continue
        if kind == "STRING":
            # Unescape single quotes and backslashes
            unescaped = val[1:-1].encode("utf-8").decode("unicode_escape")
            tokens.append(Token("STRING", unescaped, pos))
        else:
            tokens.append(Token(kind, val, pos))
    # Check for unrecognized tokens
    return tokens


class Parser:
    def __init__(self, tokens: list[Token], max_arity: int = 32) -> None:
        self.tokens = tokens
        self.pos = 0
        self.max_arity = max_arity

    def peek(self) -> Token | None:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def current(self) -> Token:
        tok = self.peek()
        if tok is None:
            raise ParseError("Unexpected end of input")
        return tok

    def consume(self, expected_type: str | None = None) -> Token:
        tok = self.current()
        if expected_type is not None and tok.type != expected_type:
            raise ParseError(f"Expected token {expected_type}, got {tok.type} at pos {tok.pos}")
        self.pos += 1
        return tok

    def match(self, *expected_types: str) -> Token | None:
        tok = self.peek()
        if tok and tok.type in expected_types:
            self.pos += 1
            return tok
        return None

    def parse_term(self, allow_aggregate: bool = False) -> Term:
        tok = self.current()
        if tok.type == "AGG_OP" and allow_aggregate:
            op = self.consume("AGG_OP").value
            self.consume("LT")
            v_tok = self.consume("VAR")
            self.consume("GT")
            return AggregateTerm(op=op, var=Variable(v_tok.value))
        if tok.type == "VAR":
            self.consume("VAR")
            return Variable(tok.value)
        if tok.type == "NUMBER":
            self.consume("NUMBER")
            return Constant(int(tok.value))
        if tok.type == "STRING":
            self.consume("STRING")
            return Constant(tok.value)
        if tok.type == "IDENT":
            # Symbol / identifier treated as string constant when in argument position
            self.consume("IDENT")
            return Constant(tok.value)
        raise ParseError(f"Unexpected token for term: {tok.type} at pos {tok.pos}")

    def parse_atom(self, allow_aggregate: bool = False, is_negated: bool = False) -> Atom:
        p_tok = self.consume("IDENT")
        args: list[Term] = []
        if self.match("LPAREN") and not self.match("RPAREN"):
            while True:
                term = self.parse_term(allow_aggregate=allow_aggregate)
                args.append(term)
                if len(args) > self.max_arity:
                    raise ParseError(f"Predicate arity exceeded maximum {self.max_arity}")
                if self.match("COMMA"):
                    continue
                if self.match("RPAREN"):
                    break
                raise ParseError(f"Expected ',' or ')' at pos {self.current().pos}")
        return Atom(predicate=p_tok.value, args=tuple(args), is_negated=is_negated)

    def parse_literal(self) -> Literal:
        if self.match("NOT"):
            return self.parse_atom(allow_aggregate=False, is_negated=True)

        # Could be atom or comparison: peek ahead
        start_pos = self.pos
        # Check if first token is Term followed by Comparison operator
        first_tok = self.peek()
        if first_tok and first_tok.type in ("VAR", "NUMBER", "STRING"):
            left = self.parse_term(allow_aggregate=False)
            cmp_tok = self.match("EQ", "NEQ", "LT", "LTE", "GT", "GTE")
            if cmp_tok:
                op = "==" if cmp_tok.value == "=" else cmp_tok.value
                right = self.parse_term(allow_aggregate=False)
                return Comparison(op=op, left=left, right=right)
            # Reset position
            self.pos = start_pos

        # If first token is IDENT, it might be an atom or comparison if it is a constant
        if first_tok and first_tok.type == "IDENT":
            # Lookahead to see if next is comparison operator
            if self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1].type in (
                "EQ",
                "NEQ",
                "LT",
                "LTE",
                "GT",
                "GTE",
            ):
                left = self.parse_term(allow_aggregate=False)
                cmp_tok = self.match("EQ", "NEQ", "LT", "LTE", "GT", "GTE")
                if cmp_tok is None:
                    raise ParseError(f"Expected comparison operator at pos {self.current().pos}")
                op = "==" if cmp_tok.value == "=" else cmp_tok.value
                right = self.parse_term(allow_aggregate=False)
                return Comparison(op=op, left=left, right=right)
            return self.parse_atom(allow_aggregate=False, is_negated=False)

        raise ParseError(f"Unexpected token in rule body at pos {self.current().pos}")

    def parse_statement(self) -> Rule | Atom:
        """Parses a rule, a fact (rule with empty body), or a query atom (ending with ?)."""
        head = self.parse_atom(allow_aggregate=True, is_negated=False)
        if self.match("QUERY"):
            return head  # Treated as query
        if self.match("ARROW"):
            body: list[Literal] = []
            while True:
                lit = self.parse_literal()
                body.append(lit)
                if self.match("COMMA"):
                    continue
                if self.match("DOT"):
                    break
                raise ParseError(f"Expected ',' or '.' at pos {self.current().pos}")
            return Rule(head=head, body=tuple(body))
        if self.match("DOT"):
            return Rule(head=head, body=())
        raise ParseError(f"Expected ':-', '.' or '?' at pos {self.current().pos}")

    def parse_program(self) -> tuple[list[Rule], list[Atom]]:
        rules: list[Rule] = []
        queries: list[Atom] = []
        while self.peek() is not None:
            stmt = self.parse_statement()
            if isinstance(stmt, Rule):
                rules.append(stmt)
            else:
                queries.append(stmt)
        return rules, queries


def parse(text: str, max_arity: int = 32) -> tuple[list[Rule], list[Atom]]:
    tokens = tokenize(text)
    parser = Parser(tokens, max_arity=max_arity)
    return parser.parse_program()
