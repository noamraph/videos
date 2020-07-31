from __future__ import annotations

from typing import List, Set, Dict, Hashable
from collections import OrderedDict
from itertools import permutations

import pytest

from revbranch.revbranch import (
    topological_sort,)


def verify_topological_sort(sorted_nodes: List[Hashable], node_parents: Dict[Hashable, List[Hashable]]):
    seen: Set[Hashable] = set()
    for node in sorted_nodes:
        for parent in node_parents[node]:
            assert parent in seen
        seen.add(node)


def test_topological_sort():
    # A cycle should fail
    with pytest.raises(ValueError, match='Cycle detected'):
        topological_sort({1: [2], 2: [3], 3: [1], 4: []})

    # Verify that verify_topological_sort works
    with pytest.raises(AssertionError):
        verify_topological_sort([1, 2, 3], {1: [], 3: [1], 2: [3]})

    dags = [
        [(1, []), (2, [1]), (3, [1]), (4, [2]), (5, [3])],
        [(1, []), (2, [1]), (3, [1]), (4, [2, 3]), (5, [3, 6]), (6, [4])],
    ]

    for dag in dags:
        for perm in permutations(dag):
            node_parents = OrderedDict(perm)
            sorted_nodes = topological_sort(node_parents)
            verify_topological_sort(sorted_nodes, node_parents)
