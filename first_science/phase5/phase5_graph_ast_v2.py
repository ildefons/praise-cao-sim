"""Phase-5 V2 graph-AST compiler.

This module is deliberately pure Python.  It translates the frozen graph AST
into the branch-dependency representation used by the PRAISE composition
controller.  It contains no scientific parameters and performs no simulation.

The four frozen ASTs compile to:

G_PAR     : A(), B(), C()
G_SEQ     : A(), B(A), C(B)
G_SEQPAR  : A(), B(A), C(A)
G_PARSEQ  : A(), B(), C(B)

Dependencies are expressed as provider names here and converted to stable
branch ids only at the simulator boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
PROVIDER_BRANCH_ID = {provider: i for i, provider in enumerate(PROVIDERS)}
SUPPORTED_OPERATORS = {"sequence", "parallel_all"}


@dataclass(frozen=True)
class GraphPlan:
    providers: tuple[str, ...]
    dependencies: Mapping[str, tuple[str, ...]]
    entry_providers: tuple[str, ...]
    terminal_providers: tuple[str, ...]

    def dependency_branch_ids(self) -> dict[str, tuple[int, ...]]:
        return {
            provider: tuple(PROVIDER_BRANCH_ID[p] for p in deps)
            for provider, deps in self.dependencies.items()
        }


@dataclass
class _PartialPlan:
    providers: set[str]
    dependencies: dict[str, set[str]]
    entries: set[str]
    terminals: set[str]


def _merge_dependencies(
    target: dict[str, set[str]], source: Mapping[str, set[str]]
) -> None:
    for provider, deps in source.items():
        target.setdefault(provider, set()).update(deps)


def _compile(node: Any) -> _PartialPlan:
    if isinstance(node, str):
        if node not in PROVIDERS:
            raise ValueError(f"unknown provider leaf: {node}")
        return _PartialPlan(
            providers={node},
            dependencies={node: set()},
            entries={node},
            terminals={node},
        )

    if not isinstance(node, Mapping):
        raise TypeError("graph AST node must be a provider name or mapping")

    op = str(node.get("op", ""))
    if op not in SUPPORTED_OPERATORS:
        raise ValueError(f"unsupported graph operator: {op!r}")

    children = node.get("children")
    if not isinstance(children, list) or len(children) < 2:
        raise ValueError(f"{op} requires at least two children")

    compiled = [_compile(child) for child in children]

    seen: set[str] = set()
    for child in compiled:
        overlap = seen.intersection(child.providers)
        if overlap:
            raise ValueError(
                "provider leaves may occur only once in the Phase-5 AST: "
                + ", ".join(sorted(overlap))
            )
        seen.update(child.providers)

    deps: dict[str, set[str]] = {}
    for child in compiled:
        _merge_dependencies(deps, child.dependencies)

    if op == "parallel_all":
        entries = set().union(*(child.entries for child in compiled))
        terminals = set().union(*(child.terminals for child in compiled))
        return _PartialPlan(
            providers=seen,
            dependencies=deps,
            entries=entries,
            terminals=terminals,
        )

    # Sequence semantics: the entry branches of each child are released only
    # after all terminal branches of the immediately preceding child complete.
    entries = set(compiled[0].entries)
    previous_terminals = set(compiled[0].terminals)
    for child in compiled[1:]:
        for provider in child.entries:
            deps.setdefault(provider, set()).update(previous_terminals)
        previous_terminals = set(child.terminals)

    return _PartialPlan(
        providers=seen,
        dependencies=deps,
        entries=entries,
        terminals=previous_terminals,
    )


def compile_graph_ast(ast: Any) -> GraphPlan:
    partial = _compile(ast)
    if partial.providers != set(PROVIDERS):
        missing = sorted(set(PROVIDERS).difference(partial.providers))
        extra = sorted(partial.providers.difference(PROVIDERS))
        raise ValueError(
            f"Phase-5 graph must contain ProviderA/B/C exactly once; "
            f"missing={missing}, extra={extra}"
        )

    dependencies = {
        provider: tuple(
            sorted(
                partial.dependencies.get(provider, set()),
                key=lambda p: PROVIDER_BRANCH_ID[p],
            )
        )
        for provider in PROVIDERS
    }

    # Defensive cycle check on the compiled branch dependency DAG.
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(provider: str) -> None:
        if provider in visited:
            return
        if provider in visiting:
            raise ValueError("compiled graph dependencies contain a cycle")
        visiting.add(provider)
        for dep in dependencies[provider]:
            visit(dep)
        visiting.remove(provider)
        visited.add(provider)

    for provider in PROVIDERS:
        visit(provider)

    return GraphPlan(
        providers=PROVIDERS,
        dependencies=dependencies,
        entry_providers=tuple(
            p for p in PROVIDERS if p in partial.entries
        ),
        terminal_providers=tuple(
            p for p in PROVIDERS if p in partial.terminals
        ),
    )


def expected_frozen_dependency_map(graph_id: str) -> dict[str, tuple[str, ...]]:
    expected = {
        "G_PAR": {
            "ProviderA": (),
            "ProviderB": (),
            "ProviderC": (),
        },
        "G_SEQ": {
            "ProviderA": (),
            "ProviderB": ("ProviderA",),
            "ProviderC": ("ProviderB",),
        },
        "G_SEQPAR": {
            "ProviderA": (),
            "ProviderB": ("ProviderA",),
            "ProviderC": ("ProviderA",),
        },
        "G_PARSEQ": {
            "ProviderA": (),
            "ProviderB": (),
            "ProviderC": ("ProviderB",),
        },
    }
    if graph_id not in expected:
        raise KeyError(graph_id)
    return expected[graph_id]


def assert_frozen_graph_compilation(graph_id: str, ast: Any) -> GraphPlan:
    plan = compile_graph_ast(ast)
    expected = expected_frozen_dependency_map(graph_id)
    actual = dict(plan.dependencies)
    if actual != expected:
        raise RuntimeError(
            f"{graph_id} compiled dependency map changed: "
            f"expected={expected}, actual={actual}"
        )
    return plan
