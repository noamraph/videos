# revbranch - add branch names to git revisions to help understand repository history

## Installation

```
pip install revbranch
```

## Development

```
git clone https://github.com/noamraph/revbranch.git
cd revbranch
python3 -m venv venv
venv/bin/pip install -e .[dev]
```


## Running tests

```
venv/bin/pytest
```

## Notes

To view the notes commit history:

```
git log -p -g notes/revbranch
```

To undo the last notes commit (saving a backup in refs/notes/revbranch-backup):

```
git update-ref refs/notes/revbranch-backup refs/notes/revbranch
git update-ref refs/notes/revbranch refs/notes/revbranch^
```

Install a virtualenv with TortoiseHG that can show the revbranches:

```
python3 -m venv venv
venv/bin/pip install pyqt5 QScintilla pygit2
venv/bin/pip install # XXX Noam's hg repo
venv/bin/pip install # XXX Noam's thg repo
```