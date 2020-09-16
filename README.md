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

To view revbranch in `git log`:

```
git config notes.displayRef refs/notes/revbranch
```

(or, without config, use `git log --notes=revbranch`)

To view the notes commit history:

```
git log notes/revbranch
```

To undo the last notes commit (saving a backup in refs/notes/revbranch-backup):

```
git update-ref refs/notes/revbranch-backup refs/notes/revbranch
git update-ref refs/notes/revbranch refs/notes/revbranch^
```

Push revbranch data to server:

```
git push origin refs/notes/revbranch
```

Fetch revbranch data from server:

```
git fetch origin refs/notes/revbranch:refs/notes/revbranch
```

To always fetch revbranch data from server:

```
git config --add remote.origin.fetch '+refs/notes/revbranch:refs/notes/revbranch'
```

Install a virtualenv with TortoiseHG that can show the revbranches:

```
python3 -m venv venv
venv/bin/pip install -U pip wheel
venv/bin/pip install pyqt5 QScintilla pygit2
venv/bin/pip install -U hg+https://code.rhodecode.com/u/noamraph/hg@noam
venv/bin/pip install -U hg+https://code.rhodecode.com/u/noamraph/thg@noam
```


## Uploading to PyPI

Based on [this](https://setuptools.readthedocs.io/en/latest/setuptools.html#distributing-a-setuptools-based-project).

1. `venv/bin/pytest`
2. Update setup.py with the new version number.
3. Commit the change.
4. Tag with the version number (`git tag 0.3`)
5. `git push origin 0.3`
6. Publish to pypi:

```
pip3 install --upgrade setuptools wheel twine

rm -rf dist build
python3 setup.py sdist bdist_wheel
twine upload dist/*
```