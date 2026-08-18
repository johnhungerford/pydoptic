# Pydoptic

A data modeling library based on reified optics, and two integrations built on top of it. Three
separately-published packages, developed together in this repository:

| Package | What it is | Install |
|---|---|---|
| [`pydoptic`](packages/pydoptic/) | The core data modeling library -- start here | `pip install pydoptic` |
| [`pydoptic-sql`](packages/pydoptic-sql/) | A type-safe SQL query builder | `pip install pydoptic-sql` |
| [`pydoptic-elastic`](packages/pydoptic-elastic/) | An Elasticsearch integration | `pip install pydoptic-elastic` |

`pydoptic-sql` and `pydoptic-elastic` both depend on `pydoptic`; they don't depend on each other, and
neither is installed unless you ask for it -- installing `pydoptic` alone pulls in only `pydoptic`'s
own dependencies.

See [`packages/pydoptic/README.md`](packages/pydoptic/README.md) for the full write-up of what
reified optics are, why they're useful, and the complete user guide -- that's the core concept behind
everything in this repository, so it lives with the core package.

## Why?

A good alternative to Pydantic when one or more of the following is true:
1. You rarely use complete instances of your modeled data
2. You frequently need to retrieve and manipulate deeply nested values
3. You need a type-safe way to refer to properties when querying remote data

See [`packages/pydoptic/README.md`](packages/pydoptic/README.md) for the full explanation and user
guide.

## Development

This repository is a monorepo: all three packages share one `test/`-style layout (each package has
its own `test/` directory), one `mypy.ini`, and one set of GitHub Actions workflows, but each has its
own `pyproject.toml` and is built/versioned/published independently. All three packages share the same
version number, derived from git tags via `setuptools-scm` -- see `CONTEXT.md` for the full versioning
and release setup.

To set up a local dev environment:

```bash
pip install -e packages/pydoptic
pip install -e "packages/pydoptic-sql[test]"
pip install -e "packages/pydoptic-elastic[test]"
```

Then run tests for all three at once with `pytest packages -q` (or `cd` into a single package's
directory and run `pytest test -q` there). Live-service integration tests (Postgres, Elasticsearch)
are excluded by default -- bring up `docker compose up -d` and pass `-m integration` to run them.
