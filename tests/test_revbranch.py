from __future__ import annotations

from typing import List, Set, Dict, Hashable
from collections import OrderedDict
from itertools import permutations

import pytest

from revbranch import (
    topological_sort, fill_unknown_branches)


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


def test_fill_unknown_branches():
    # 1. a pretty standard tree. Only the root is marked with 'm' (for 'master')
    rev_parent = {1: None, 2: 1, 3: 2, 4: 3, 5: 2, 6: 5, 7: 6, 8: 6, 9: 8}
    rev_branch0 = {1: 'm'}
    rev_branches = {4: {'m'}, 7: {'a'}, 9: {'b'}}
    new_rev_branch, unnamed_revs, ambig_revs = fill_unknown_branches(rev_parent, rev_branch0, rev_branches)
    assert new_rev_branch == {2: 'm', 3: 'm', 4: 'm', 7: 'a', 8: 'b', 9: 'b'}
    assert unnamed_revs == set()
    assert ambig_revs == {5: {'a', 'b'}}

    # 2. Now we specify the ambiguous rev
    rev_parent = {1: None, 2: 1, 3: 2, 4: 3, 5: 2, 6: 5, 7: 6, 8: 6, 9: 8}
    rev_branch0 = {1: 'm', 5: 'a'}
    rev_branches = {4: {'m'}, 7: {'a'}, 9: {'b'}}
    new_rev_branch, unnamed_revs, ambig_revs = fill_unknown_branches(rev_parent, rev_branch0, rev_branches)
    assert new_rev_branch == {2: 'm', 3: 'm', 4: 'm', 6: 'a', 7: 'a', 8: 'b', 9: 'b'}
    assert unnamed_revs == set()
    assert ambig_revs == {}

    # 3. Make sure that adding an additional branch pointer to a revision with
    # a known branch doesn't matter. (based on 2)
    rev_parent = {1: None, 2: 1, 3: 2, 4: 3, 5: 2, 6: 5, 7: 6, 8: 6, 9: 8}
    rev_branch0 = {1: 'm', 5: 'a'}
    rev_branches = {4: {'m'}, 7: {'a'}, 9: {'b'}, 5: {'c'}}
    new_rev_branch, unnamed_revs, ambig_revs = fill_unknown_branches(rev_parent, rev_branch0, rev_branches)
    assert new_rev_branch == {2: 'm', 3: 'm', 4: 'm', 6: 'a', 7: 'a', 8: 'b', 9: 'b'}
    assert unnamed_revs == set()
    assert ambig_revs == {}

    # 4. An unnamed leaf (based on 1, remove the branch pointer 'b')
    rev_parent = {1: None, 2: 1, 3: 2, 4: 3, 5: 2, 6: 5, 7: 6, 8: 6, 9: 8}
    rev_branch0 = {1: 'm'}
    rev_branches = {4: {'m'}, 7: {'a'}}
    new_rev_branch, unnamed_revs, ambig_revs = fill_unknown_branches(rev_parent, rev_branch0, rev_branches)
    assert new_rev_branch == {2: 'm', 3: 'm', 4: 'm', 7: 'a'}
    assert unnamed_revs == {9}
    assert ambig_revs == {}

    # 5. Have an unnamed leaf and an ambiguity (based on 4)
    rev_parent = {1: None, 2: 1, 3: 2, 4: 3, 5: 2, 6: 5, 7: 6, 8: 6, 9: 8, 10: 9}
    rev_branch0 = {1: 'm', 8: 'b'}
    rev_branches = {4: {'m'}, 7: {'a'}}
    new_rev_branch, unnamed_revs, ambig_revs = fill_unknown_branches(rev_parent, rev_branch0, rev_branches)
    assert new_rev_branch == {2: 'm', 3: 'm', 4: 'm', 7: 'a'}
    assert unnamed_revs == {10}
    assert ambig_revs == {5: {'a', 'b'}}

    # 6. A branch pointer to a rev with an unnamed descendant doesn't matter,
    # since the rev could still belong to the unnamed branch (based on 4)
    rev_parent = {1: None, 2: 1, 3: 2, 4: 3, 5: 2, 6: 5, 7: 6, 8: 6, 9: 8}
    rev_branch0 = {1: 'm'}
    rev_branches = {4: {'m'}, 7: {'a'}, 8: {'b'}}
    new_rev_branch, unnamed_revs, ambig_revs = fill_unknown_branches(rev_parent, rev_branch0, rev_branches)
    assert new_rev_branch == {2: 'm', 3: 'm', 4: 'm', 7: 'a'}
    assert unnamed_revs == {9}
    assert ambig_revs == {}

    # 7. Multiple branches pointing at a leaf is also an ambiguity (based on 1)
    rev_parent = {1: None, 2: 1, 3: 2, 4: 3,  5: 2, 6: 5, 7: 6,  8: 6, 9: 8, 10: 9}
    rev_branch0 = {1: 'm', 9: 'b'}
    rev_branches = {4: {'m'}, 7: {'a'}, 10: {'c', 'd'}}
    new_rev_branch, unnamed_revs, ambig_revs = fill_unknown_branches(rev_parent, rev_branch0, rev_branches)
    assert new_rev_branch == {2: 'm', 3: 'm', 4: 'm', 7: 'a', 8: 'b'}
    assert unnamed_revs == set()
    assert ambig_revs == {5: {'a', 'b'}, 10: {'c', 'd'}}

    # 8. Automatically determine root branch (based on 1)
    rev_parent = {1: None, 2: 1, 3: 2, 4: 3, 5: 2, 6: 5, 7: 6, 8: 6, 9: 8}
    rev_branch0 = {}
    rev_branches = {4: {'m'}, 7: {'a'}, 9: {'b'}}
    new_rev_branch, unnamed_revs, ambig_revs = fill_unknown_branches(
        rev_parent, rev_branch0, rev_branches, {'m', 'master'})
    assert new_rev_branch == {1: 'm', 2: 'm', 3: 'm', 4: 'm', 7: 'a', 8: 'b', 9: 'b'}
    assert unnamed_revs == set()
    assert ambig_revs == {5: {'a', 'b'}}

    # 9. Multiple roots, make sure that for the unspecified roots only the root is
    # added to unnamed_revs.
    rev_parent = {1: None, 2: 1, 3: 1,
                  4: None, 5: 4, 6: 4,
                  7: None, 8: 7, 9: 8,
                  }
    rev_branch0 = {}
    rev_branches = {2: {'m1'}, 5: {'m1'}, 3: {'m2'}, 6: {'a'}, 9: {'a'}}
    new_rev_branch, unnamed_revs, ambig_revs = fill_unknown_branches(
        rev_parent, rev_branch0, rev_branches, {'m1', 'm2'})
    assert new_rev_branch == {4: 'm1', 5: 'm1', 6: 'a'}
    assert unnamed_revs == {1, 7}
    assert ambig_revs == {}
