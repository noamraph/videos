from typing import List, Dict, BinaryIO, cast
import hashlib
import struct

from dulwich.repo import Repo
from dulwich.objects import Commit

# It turns out that unbundling a bundle is *much* faster than committing
# every commit.
# write_bundle() lets you write a metadata-only bundle using the given git
# revisions.
# The format is documented here: https://www.mercurial-scm.org/wiki/BundleFormat


def get_changelog_text(author: bytes, author_time: int, author_timezone: int, branch: bytes, message: bytes) -> bytes:
    # This is constructed in mercurial.changelog:add
    hex_manifest = b'0'*40
    user = author
    parsed_date = f'{int(author_time)} {-author_timezone}'.encode('ascii')
    if branch not in (b'default', b'master'):
        parsed_date += b' branch:' + branch
    return b'\n'.join([hex_manifest, user, parsed_date, b'', message])


def hash_revision_sha1(text: bytes, p1: bytes, p2: bytes) -> bytes:
    """
    p1 and p2 are 20-bytes binary hashes.
    """
    if p1 < p2:
        a = p1
        b = p2
    else:
        a = p2
        b = p1
    s = hashlib.sha1(a)
    s.update(b)
    s.update(text)
    return s.digest()


def get_chunk(data: bytes) -> bytes:
    # For some reason pycharm thinks that struct.pack returns str instead of bytes
    size = cast(bytes, struct.pack('>i', len(data) + 4))
    return size + data


def get_revdata(changelog: bytes, last_changelog_len: int) -> bytes:
    # We create RevData which just replaces the previous changelog
    return cast(bytes, struct.pack('>iii', 0, last_changelog_len, len(changelog))) + changelog


def from_hex(b: bytes) -> bytes:
    return bytes.fromhex(b.decode('ascii'))


def to_hex(b: bytes) -> bytes:
    return b.hex().encode('ascii')


def get_rev_chunk(commit: Commit, branch: bytes, git_hg: Dict[bytes, bytes], last_changelog_len: int) -> (bytes, bytes):
    """
    Get the bundle chunk from a commit.
    Update git_hg with the hg rev.
    """
    message = b'[' + commit.id[:8] + b'] ' + commit.message
    changelog_text = get_changelog_text(commit.author, commit.author_time, commit.author_timezone, branch, message)
    nullid = b"\0" * 20
    p0 = from_hex(git_hg[commit.parents[0]]) if commit.parents else nullid
    p1 = from_hex(git_hg[commit.parents[1]]) if len(commit.parents) > 1 else nullid
    node = hash_revision_sha1(changelog_text, p0, p1)
    revdata = get_revdata(changelog_text, last_changelog_len)
    data = node + p0 + p1 + node + revdata
    chunk = get_chunk(data)
    git_hg[commit.id] = to_hex(node)
    return chunk, changelog_text


def write_bundle(f: BinaryIO, revs: List[bytes], rev_branch: Dict[bytes, bytes], git: Repo):
    """
    Write an HG bundle with only metadata, to help visualize the branch
    assignment.

    :param f: file in which to write the bundle
    :param revs: topologically-sorted list of revision IDs
    :param rev_branch: Map a revision ID to its branch
    :param git: dulwich git repo
    """
    f.write(b'HG10UN')
    git_hg = {}
    last_changelog = b''
    for rev in revs:
        chunk, last_changelog = get_rev_chunk(
            git[rev], cast(bytes, rev_branch[rev]), git_hg, len(last_changelog))
        f.write(chunk)
    for i in range(3):
        # 3 null chunks: one to end the changelog group, one to end the empty
        # manifest group, and one to end the empty filelist.
        f.write(b'\0' * 4)
