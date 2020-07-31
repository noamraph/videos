from __future__ import annotations

from typing import Dict, List, Set, Optional, Hashable

from dulwich.repo import Repo


# A revision ID. dulwich uses bytes, so we allow both bytes and str.
# For testing it's easy to use ints, so we just allow any hashable.
Rev = Hashable
# A branch name.
Branch = Hashable
# A mapping from a revision to its parents. For the root revision, the empty list.
RevParents = Dict[Rev, List[Rev]]
# A mapping from a revision to its first parent, or None for the root revision.
RevParent = Dict[Rev, Optional[Rev]]
# A mapping from a branch name to the revisions it points to
# (There can be a few, for both local and remote branches)
BranchRevs = Dict[Branch, Set[Rev]]


def topological_sort(node_parents: Dict[Hashable, List[Hashable]]) -> List[Hashable]:
    """
    Sort nodes in an order so that each node comes after its parents.
    """
    r: List[Hashable] = []
    in_r: Set[Hashable] = set()
    # When using recursion we reach the maximum depth, so we use a stack.
    # The stack consists of (node, i) tuple. i is the index of the next parent
    # that we need to verify is before node in r. If it's equal to
    # len(node_parents[node]), we add node to r.
    stack: List[(Hashable, bool)] = []
    in_stack: Set[Hashable] = set()

    for x in node_parents.keys():
        if x not in in_r:
            stack.append((x, 0))
            in_stack.add(x)
            while stack:
                y, i = stack.pop()
                parents = node_parents[y]
                while i < len(parents):
                    parent = parents[i]
                    if parent not in in_r:
                        if parent in in_stack:
                            raise ValueError(f"Cycle detected containing {parent!r}")
                        stack.append((y, i + 1))
                        stack.append((parent, 0))
                        in_stack.add(parent)
                        break
                    i += 1
                else:
                    # All parents were already handled
                    r.append(y)
                    in_r.add(y)
                    in_stack.remove(y)
    return r


def get_git_revisions(git: Repo) -> (RevParents, BranchRevs):
    branch_revs: BranchRevs = {}
    for ref in git.refs:
        if ref.startswith(b'refs/heads/'):
            branch = ref[len(b'refs/heads/'):]
        elif ref.startswith(b'refs/remotes/'):
            remote_and_branch = ref[len(b'refs/remotes/'):]
            _remote, branch = remote_and_branch.split(b'/', 1)
        else:
            continue
        branch_revs.setdefault(branch, set()).add(git[ref].id)

    rev_parents: RevParents = {}
    todo = set(rev for revs in branch_revs.values() for rev in revs)
    while todo:
        rev = todo.pop()
        commit = git[rev]
        rev_parents[rev] = commit.parents
        for rev2 in commit.parents:
            if rev2 not in rev_parents:
                todo.add(rev2)

    return rev_parents, branch_revs


def main():
    print("Hello world!")
