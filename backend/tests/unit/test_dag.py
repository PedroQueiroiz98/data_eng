from __future__ import annotations

import pytest

from nbplatform.core.errors import DomainValidationError
from nbplatform.domain.dag import ready_tasks, topological_order, validate_dag


def test_valid_chain_and_diamond() -> None:
    validate_dag({"a", "b", "c"}, [("a", "b"), ("b", "c")])
    validate_dag({"a", "b", "c", "d"}, [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")])


def test_self_loop_rejected() -> None:
    with pytest.raises(DomainValidationError, match="si mesma"):
        validate_dag({"a"}, [("a", "a")])


def test_unknown_node_rejected() -> None:
    with pytest.raises(DomainValidationError, match="inexistente"):
        validate_dag({"a", "b"}, [("a", "c")])


def test_cycle_rejected() -> None:
    with pytest.raises(DomainValidationError, match="ciclo"):
        validate_dag({"a", "b", "c"}, [("a", "b"), ("b", "c"), ("c", "a")])


def test_topological_order_respects_dependencies() -> None:
    order = topological_order(
        {"extract", "transform", "load"},
        [("extract", "transform"), ("transform", "load")],
    )
    assert order == ["extract", "transform", "load"]


def test_topological_order_is_deterministic_for_parallel() -> None:
    order = topological_order({"a", "b", "c"}, [("a", "c"), ("b", "c")])
    assert order.index("a") < order.index("c")
    assert order.index("b") < order.index("c")
    assert order[:2] == ["a", "b"]  # ordenação estável


def test_ready_tasks() -> None:
    nodes = {"a", "b", "c", "d"}
    edges = [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")]
    assert ready_tasks(nodes, edges, completed=set(), started=set()) == {"a"}
    assert ready_tasks(nodes, edges, completed={"a"}, started=set()) == {"b", "c"}
    assert ready_tasks(nodes, edges, completed={"a", "b"}, started={"c"}) == set()
    assert ready_tasks(nodes, edges, completed={"a", "b", "c"}, started=set()) == {"d"}
