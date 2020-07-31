# revbranch - add branch names to git revisions to help understand repository history

## Installation

```
pip install revbranch
```

## Development

Install [poetry](https://python-poetry.org/). Then:

```
git clone https://github.com/noamraph/revbranch.git
cd revbranch
poetry install 
```


## Running tests

```
poetry run pytest
```

## Notes

I like to have the virtualenv inside the directory, and this makes it work:

```
poetry config virtualenvs.in-project true
```