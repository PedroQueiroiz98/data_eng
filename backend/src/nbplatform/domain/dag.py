"""Grafo de dependências de workflow: validação (sem ciclos) e ordenação topológica.

Genérico sobre identificadores de nó hasháveis (str ou UUID). Reutilizado pela
orquestração de Jobs para calcular o conjunto de tarefas prontas.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Hashable, Iterable

from nbplatform.core.errors import DomainValidationError


def validate_dag[N: Hashable](nodes: Iterable[N], edges: Iterable[tuple[N, N]]) -> None:
    node_set = set(nodes)
    edge_list = list(edges)

    for src, dst in edge_list:
        if src not in node_set or dst not in node_set:
            raise DomainValidationError(
                f"Dependência referencia tarefa inexistente: {src} → {dst}."
            )
        if src == dst:
            raise DomainValidationError(f"Tarefa não pode depender de si mesma: {src}.")

    if _has_cycle(node_set, edge_list):
        raise DomainValidationError("O workflow contém um ciclo de dependências.")


def topological_order[N: Hashable](nodes: Iterable[N], edges: Iterable[tuple[N, N]]) -> list[N]:
    """Ordem de execução respeitando dependências. Levanta se houver ciclo."""
    node_set = set(nodes)
    edge_list = list(edges)
    validate_dag(node_set, edge_list)

    indegree: dict[N, int] = dict.fromkeys(node_set, 0)
    adjacency: dict[N, list[N]] = defaultdict(list)
    for src, dst in edge_list:
        adjacency[src].append(dst)
        indegree[dst] += 1

    queue: deque[N] = deque(sorted((n for n, deg in indegree.items() if deg == 0), key=str))
    order: list[N] = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for nxt in sorted(adjacency[node], key=str):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    return order


def ready_tasks[N: Hashable](
    nodes: Iterable[N],
    edges: Iterable[tuple[N, N]],
    *,
    completed: set[N],
    started: set[N],
) -> set[N]:
    """Nós ainda não iniciados cujas dependências diretas já terminaram."""
    deps: dict[N, set[N]] = defaultdict(set)
    for src, dst in edges:
        deps[dst].add(src)
    ready: set[N] = set()
    for node in nodes:
        if node in completed or node in started:
            continue
        if deps[node] <= completed:
            ready.add(node)
    return ready


def _has_cycle[N: Hashable](nodes: set[N], edges: list[tuple[N, N]]) -> bool:
    indegree: dict[N, int] = dict.fromkeys(nodes, 0)
    adjacency: dict[N, list[N]] = defaultdict(list)
    for src, dst in edges:
        adjacency[src].append(dst)
        indegree[dst] += 1

    queue: deque[N] = deque(n for n, deg in indegree.items() if deg == 0)
    visited = 0
    while queue:
        node = queue.popleft()
        visited += 1
        for nxt in adjacency[node]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    return visited != len(nodes)
