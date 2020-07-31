from __future__ import annotations

from typing import Dict, List, Set, Optional, Hashable, Any
import time
from subprocess import check_call

from dulwich.repo import Repo
from dulwich.objects import Tree, Blob, Commit

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
# A mapping from a revision to its assigned branch
RevBranch = Dict[Rev, Branch]


# Git file modes
REG = 0o100644
EXE = 0o100755
LINK = 0o120000
DIR = 0o40000
SUBMODULE = 0o160000

NOTES_REF = b'refs/notes/revbranch'


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


def parse_notes_tree(git: Repo, tree: Tree, prefix=b'') -> Dict[bytes, bytes]:
    rev_note = {}
    for entry in tree.iteritems():
        if entry.mode == DIR:
            rev_note2 = parse_notes_tree(git, git[entry.sha], prefix + entry.path)
            rev_note.update(rev_note2)
        elif entry.mode == REG:
            rev = prefix + entry.path
            if len(rev) != 40:
                raise RuntimeError(f"notes tree contains unexpected path {rev!r}")
            assert len(rev) == 40
            rev_note[rev] = git[entry.sha].data
        else:
            raise RuntimeError(f"notes tree contains unexpected mode {entry.mode!r}")
    return rev_note


def get_git_revbranches(git: Repo) -> RevBranch:
    try:
        ref = git.refs[NOTES_REF]
    except KeyError:
        return {}
    notes = git[ref]
    if isinstance(notes, Commit):
        tree = git[notes.tree]
    elif isinstance(notes, Tree):
        tree = notes
    else:
        raise RuntimeError(f"{NOTES_REF} should be either a commit or a tree")
    return parse_notes_tree(git, tree)


def update_git_revbranches(git: Repo, rev_branch: RevBranch):
    """
    Update the stored revbranches according to rev_branch.
    """
    blobs = {}
    tree = Tree()
    for rev, branch in rev_branch.items():
        if branch in blobs:
            blob = blobs[branch]
        else:
            blob = Blob.from_string(branch)
            blobs[branch] = blob
        tree.add(rev, REG, blob.id)
    commit: Any = Commit()  # cast to Any since it suppresses false pycharm warnings
    commit.tree = tree.id
    commit.author = commit.committer = b'revbranch <revbranch>'
    commit.commit_time = commit.author_time = int(time.time())
    commit.commit_timezone = commit.author_timezone = 0
    commit.encoding = b'ascii'
    commit.message = b'Temporary commit by revbranch'

    store = git.object_store
    for blob in blobs.values():
        store.add_object(blob)
    store.add_object(tree)
    store.add_object(commit)

    tmp_notes_ref = b'refs/notes/tmp-revbranch'
    git.refs[tmp_notes_ref] = commit.id
    check_call(
        ['git', '-C', git.path, 'notes',
         '--ref', 'revbranch', 'merge', '-s', 'theirs', tmp_notes_ref])
    git.refs.remove_if_equals(tmp_notes_ref, commit.id)


def main():
    print("Hello world!")
