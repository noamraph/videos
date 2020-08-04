from __future__ import annotations

from typing import Dict, List, Set, Optional, Hashable, Any, TypeVar
import time
from subprocess import check_output

from dulwich.repo import Repo
from dulwich.objects import Tree, Blob, Commit

# A revision ID. For testing it's easy to use ints, so we just allow any hashable.
Rev = TypeVar('Rev', bound=Hashable)
# A branch name.
Branch = TypeVar('Branch', bound=Hashable)
# A mapping from a revision to its parents. For the root revision, the empty list.
RevParents = Dict[Rev, List[Rev]]
# A mapping from a revision to its children.
RevChildren = Dict[Rev, Set[Rev]]
# A mapping from a revision to its first parent, or None for the root revision.
RevParent = Dict[Rev, Optional[Rev]]
# A mapping from a branch name to the revisions it points to
# (There can be a few, for both local and remote branches)
BranchRevs = Dict[Branch, Set[Rev]]
# A mapping from a revision to its assigned branch
RevBranch = Dict[Rev, Branch]
# A mapping from a revision to a set of branches
RevBranches = Dict[Rev, Set[Branch]]


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
    # git 2.7 doesn't support --quiet, so we just consume the output
    _output = check_output(
        ['git', '-C', git.path, 'notes',
         '--ref', 'revbranch', 'merge', '--strategy', 'theirs', tmp_notes_ref])
    git.refs.remove_if_equals(tmp_notes_ref, commit.id)


def fill_unknown_branches_rec(rev: Rev, root_branch: Branch,
                              rev_children: RevChildren, rev_branch0: RevBranch, rev_branches: RevBranches,
                              new_rev_branch: RevBranch, unnamed_leaves: Set[Rev], ambig_revs: RevBranches,
                              ) -> Set[Branch]:
    """
    The recursive function that traverses the tree for fill_unknown_branches()
    :param rev: Scan this revision and its descendants.
    :param root_branch: The branch of rev's nearest ancestor. This gets priority
        when assigning branches.
    :param rev_children: (unchanged) The set of children for each rev
    :param rev_branch0: (unchanged) See fill_unknown_branches()
    :param rev_branches: (unchanged) The set of branch pointers for each rev
    :param new_rev_branch: (updated) See fill_unknown_branches()
    :param unnamed_leaves: (updated) See fill_unknown_branches()
    :param ambig_revs: (updated) See fill_unknown_branches()
    :return: possible_branches: A set of branch names.
    If len(possible_branches) == 1, a branch was assigned to rev (added to
        new_rev_branch), and that's the branch.
    If len(possible_branches) == 0, rev's branch can't be determined, since
        the user should first assign a branch name to a descendant leaf rev.
    If len(possible_branches) > 1, there are several alternatives for the rev
        branch, and the user will have to choose one. This was not added to
        ambig_revs - the user should only assign a branch for a revision
        whose parent is known. In this case, root_branch can't be in the set,
        since whenever it's one of the alternatives, it's chosen.
    """
    # This is the logic:
    # If we are a known branch, we just call the recursive function with
    # each of our children. If one of them is ambiguous, add it to ambig_revs.
    # Return one branch: the known branch.
    # If we are an unknown branch, go over all the children. We treat branch pointers
    # as children with a known branch. If one of the children is root_branch,
    # then we are definitely root_branch, and add it to new_rev_branch. We
    # also add each ambiguous child to ambig_revs. If one of the children is
    # unknown (len(possible_branches) == 0), then we are unknown too.
    # If all children agree on the same branch, then we have this branch as
    # well. Otherwise, we return the union of the possible branches.
    if rev in rev_branch0:
        my_branch = rev_branch0[rev]
        for rev2 in rev_children[rev]:
            possible_branches2 = fill_unknown_branches_rec(
                rev2, my_branch,
                rev_children, rev_branch0, rev_branches,
                new_rev_branch, unnamed_leaves, ambig_revs)
            if len(possible_branches2) > 1:
                ambig_revs[rev2] = possible_branches2
        return {my_branch}

    # else... (Our branch is not known)

    possible_branches_sets = {}
    for rev2 in rev_children.get(rev, []):
        possible_branches_sets[rev2] = fill_unknown_branches_rec(
            rev2, root_branch,
            rev_children, rev_branch0, rev_branches,
            new_rev_branch, unnamed_leaves, ambig_revs)
    # A list of the possible branches sets, plus a 1-set for each
    # branch pointing at us.
    my_branches = rev_branches.get(rev, set())
    possible_branches_sets2 = list(possible_branches_sets.values()) + [{branch} for branch in my_branches]

    if len(possible_branches_sets2) == 0:
        # We are a leaf rev without a branch pointing at it
        unnamed_leaves.add(rev)
        return set()

    if {root_branch} in possible_branches_sets2:
        # One of the children is known to be root_branch, so we're as well.
        new_rev_branch[rev] = root_branch
        for rev2, possible_branches2 in possible_branches_sets.items():
            if len(possible_branches2) > 1:
                ambig_revs[rev2] = possible_branches2
        return {root_branch}

    if set() in possible_branches_sets2:
        # One of the children is unknown, so we are as well.
        return set()

    possible_branches = set(b for branches in possible_branches_sets2 for b in branches)
    if len(possible_branches) == 1:
        [branch] = possible_branches
        new_rev_branch[rev] = branch
        return set(branch)
    else:
        assert len(possible_branches) > 1
        return possible_branches


def fill_unknown_branches(rev_parent: RevParent, rev_branch0: RevBranch, branch_revs: BranchRevs
                          ) -> (RevBranch, Set[Rev], RevBranches):
    """
    Assign branch names to revisions that don't yet have a branch, and also
    report what the user needs to fill in order to have a full assignment.
    :param rev_parent: The parent of each revision, or None for the root.
        (We are only interested in the first parent of merge commits).
    :param rev_branch0: The current mapping from revision to branch name.
        The roots should already have a branch - that's the job of
        fill_roots().
    :param branch_revs: A map from a branch name to a set of revisions
        it refers to. (There can be multiple, for both local and remotes).
    :return:
    new_rev_branch: A mapping from revisions that didn't have a branch name
        to their new assigned branch.
    unnamed_leaves: A set of revisions that are leaf nodes and don't have
        an assigned branch, so the user needs to decide on that. These are
        second parents of merge revisions. Many times the merge commit message
        can help recovered the branch name.
    ambig_revs: A mapping from revisions to sets of branch names. These are
        ambiguous revisions, where the user needs to decide to which of those
        branches the revision belongs to.
    """
    rev_children: RevChildren = {}
    roots = []
    for rev, parent in rev_parent.items():
        if parent is not None:
            rev_children.setdefault(parent, set()).add(rev)
        else:
            roots.append(rev)

    rev_branches: RevBranches = {}
    for branch, revs in branch_revs.items():
        for rev in revs:
            rev_branches.setdefault(rev, set()).add(branch)

    new_rev_branch: RevBranch = {}
    unnamed_leaves: Set[Rev] = set()
    ambig_revs: RevBranches = {}

    for root in roots:
        branch = rev_branch0[root]  # We assume that roots already have assigned branches
        possible_branches = fill_unknown_branches_rec(
            root, branch,
            rev_children, rev_branch0, rev_branches,
            new_rev_branch, unnamed_leaves, ambig_revs)
        assert possible_branches == {branch}

    return new_rev_branch, unnamed_leaves, ambig_revs


def main():
    print("Hello world!")
