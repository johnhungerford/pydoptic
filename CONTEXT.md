# CONTEXT.md

Working notes for an ongoing development session on this repo, written because the conversation that
produced this work is about to run out of context. Read this before continuing the work — it captures
*why* things are shaped the way they are, which the code alone won't tell you and which took real
back-and-forth to arrive at. Skipping it risks re-litigating settled design questions or reintroducing
bugs that were already found and fixed. The session started as `pydoptic_sql` feature work (the "two
arity strategies" section below and everything under it) and later shifted to packaging/publishing
infrastructure (everything from "Repo structure / packaging" onward) — both are still live context.

## Where the work actually lives

**Do the work in `/Users/johnhungerford/projects/personal/pydoptic` on branch `main` directly.**
That's where every commit below actually landed. If you're reading this from a git worktree under
`.claude/worktrees/...`, that worktree is stale (last touched near the start of this effort) and is
*not* where this work happened — don't use it as a source of truth for current file contents.

Live Postgres integration tests connect to `host=localhost port=5432 dbname=pydoptic user=postgres
password=password` (see `docker-compose.yml`); bring it up with `docker compose up -d` if it's not
already running (this also brings up Elasticsearch, used by `pydoptic-elastic`'s integration tests).

## What `pydoptic_sql` is

A type-safe SQL query builder layered on `pydoptic` (the base package's "reified optics" / selector
system — `Select`, `PropSelect`, `Prop`, `PropOpt`, etc. in
`packages/pydoptic/src/pydoptic/selector.py`). Its distinguishing feature versus mainstream options
(SQLAlchemy, peewee, etc.): join arity is tracked in the type system itself, so a WHERE/ON/HAVING
clause can't reference a table that isn't actually in scope at that point in a join chain — mypy
catches it, not just Postgres at runtime.

## Commands

```bash
# from repo root -- mypy checks all three packages at once (see mypy.ini's mypy_path)
venv/bin/python -m mypy packages --config-file mypy.ini

# pytest.ini at the repo root registers the `integration` marker for this combined run
venv/bin/python -m pytest packages -q               # unit tests, all three packages
venv/bin/python -m pytest packages -q -m integration # live-service integration tests

# to run a single package's tests in isolation (this is what CI actually does per-package):
cd packages/pydoptic-sql && ../../venv/bin/python -m pytest test -q
```
`venv/` at the repo root already has mypy and pytest installed — use it rather than system Python
(which is too old for this codebase's `match` statements etc.). After the packaging split (see below),
local dev needs all three packages installed editable — `pip install -e packages/pydoptic` then
`pip install -e "packages/pydoptic-sql[test]"` and `pip install -e "packages/pydoptic-elastic[test]"`.

## Current state

- Everything through **"Re-export full public API from each package's `__init__.py`, add README
  install docs"** (commit `b41e03e`) is committed on `main` and pushed to
  `github.com:johnhungerford/pydoptic.git`.
- Since then, this repo was **split into three independently-published packages** (`pydoptic`,
  `pydoptic-sql`, `pydoptic-elastic` — previously all published as one `pydoptic` distribution), **done
  and locally verified, but not yet committed**. See "Repo structure / packaging" below for the full
  rationale and layout. In short: `src/pydoptic{,_sql,_elastic}/` and `test/pydoptic{,_sql,_elastic}/`
  moved to `packages/{pydoptic,pydoptic-sql,pydoptic-elastic}/{src,test}/...`, each package gained its
  own `pyproject.toml`, the root `pyproject.toml` is gone (replaced by a root `pytest.ini` for
  local-dev convenience only), `mypy.ini` gained a `mypy_path` pointing at all three `src/` roots, and
  all four `.github/workflows/*.yml` were updated to matrix over the three packages. Also fixed along
  the way: `pydoptic_sql` was missing its `py.typed` marker (added), and the unused `jsonschema`
  dependency was dropped (verified zero references anywhere in the codebase before removing).
  Re-verified locally after the move: `mypy packages --config-file mypy.ini` clean (27 source files),
  `pytest packages -q` → 281 passed/18 deselected, `pytest packages -q -m integration` → 18 passed/281
  deselected, and per-package invocation (`cd packages/<name> && pytest test -q[, -m integration]`)
  matches those same counts split three ways (88/0, 192/16, 1/2) — exactly the same 299 total as before
  the split. Commit this (with the user's go-ahead) before starting anything new.

## Module map (`packages/pydoptic-sql/src/pydoptic_sql/`)

| File | Purpose |
|---|---|
| `sql_table.py` | `SqlTable` base, `ColumnType`, `column()`, DDL column constraints (`PrimaryKey`, `Unique`, `AutoIncrement`, `ForeignKey`, `Check`, `Default`) |
| `sql_constraint.py` | `Constraint`/`Constraint2`/`Constraint3`/`Constraint4` — WHERE and JOIN-ON conditions, one arity-ladder class family per number of tables a single constraint can span. Every concrete subclass at arities 1-3 has `incr_arity()` rewrapping it into the next arity's class (no `Constraint5`, so arity 4 has none) |
| `sql_order.py` | `Direction`, `OrderBy` — ORDER BY. Deliberately **not** an arity ladder (see below) |
| `sql_computed.py` | `AggregateFunction`, `ComputedResult`, `Computed[TC, A]` — aggregate/computed columns (SUM/COUNT/AVG/MIN/MAX) |
| `sql_having.py` | `HavingConstraint`/`2`/`3`/`4` — HAVING conditions; a genuinely separate hierarchy from `Constraint*`, not reused, so `Computed` values stay statically unusable in WHERE/ON. Same `incr_arity()` treatment (arities 1-3) as `Constraint*` |
| `sql_query.py` | The big one (~1150 lines): `SqlQuery` base + one query class per join arity, both plain (`Query1..4`) and `Computed` (`ComputedQuery1..4`) variants — no separate builder/terminal classes (see below). |
| `sql_service.py` | `PsycoPgSqlClient`/`Transaction`/`*Response` — executes queries against Postgres via `psycopg`, decodes rows back into `PartialModel`/`ComputedResult` |

Tests mirror this 1:1 under `packages/pydoptic-sql/test/` (`test_sql_query.py`,
`test_sql_constraint.py`, `test_sql_params.py`, `test_sql_computed.py`, `test_sql_having.py`,
`test_sql_service.py` for the live-DB integration tests).

## Repo structure / packaging

**Why the split happened**: originally all three packages (`pydoptic`, `pydoptic_sql`,
`pydoptic_elastic`) were auto-discovered from a single shared `src/` and published as one `pydoptic`
distribution. `pip install pydoptic` therefore always pulled in `psycopg` and `elasticsearch`
regardless of whether you wanted the SQL or Elasticsearch integrations at all — the user didn't want
that. Splitting into separately-published packages while keeping them developed together in one repo
(a monorepo) is the fix.

**Layout**: `packages/<name>/` is a fully self-contained project — its own `pyproject.toml`, its own
`src/<import_name>/`, its own `test/`. PyPI distribution names are hyphenated (`pydoptic-sql`,
`pydoptic-elastic`) per PyPI convention; the Python *import* names are unchanged (`pydoptic_sql`,
`pydoptic_elastic` — underscore, since hyphens aren't legal in Python identifiers). Only `pydoptic`
core has no dependency on the other two; `pydoptic_sql`/`pydoptic_elastic` both depend on `pydoptic`
but not on each other (verified via grep before splitting — zero cross-imports between them). Things
that stay shared at the repo root rather than being duplicated per package: `docker-compose.yml`,
`mypy.ini`, `.github/workflows/`, `LICENSE` (also copied into each package dir so each sdist/wheel
carries its own copy — trivial, zero drift risk for a license file), and this file.

**README split**: the ~850-line tutorial (reified optics concepts, the full user guide) moved to
`packages/pydoptic/README.md` — it's fundamentally about `pydoptic` core, not the SQL/Elastic
integrations, and giving `pydoptic-sql`/`pydoptic-elastic` their own `readme = "README.md"` pointing
*outside* their own project directory (e.g. `../../README.md`) was deliberately avoided as a
packaging-metadata reference that's a known source of sdist/build-frontend friction, in favor of
something guaranteed to work with any build tool. `pydoptic-sql` and `pydoptic-elastic` each got a
short, genuinely new README (this repo had zero SQL usage documentation before, and only an inline
Elasticsearch example previously buried in the monolithic README) — both examples were verified to
actually run (the SQL one via `.to_sql()` output inspection, the Elasticsearch one live against the
`docker-compose.yml` ES instance) before being written down, not just eyeballed. The repo-root
`README.md` is now a short landing page linking to all three.

**Versioning: lockstep, not independent.** All three packages share one version number, derived from
git tags via `setuptools-scm` — a single `vX.Y.Z` tag bumps and (potentially) publishes all three
together. This was an explicit choice over independent per-package versions/tags: independent
versioning is more precise (a `pydoptic_sql`-only change wouldn't bump `pydoptic`'s version) but needs
per-package tag prefixes, per-package `tag_regex` config, and more day-to-day tagging discipline —
overkill for a project at this stage. The lockstep mechanism has no extra moving parts: each package's
`[tool.setuptools_scm]` sets `root = "../.."` (since its `pyproject.toml` is no longer at the git root)
pointing at the *same* git root, so all three independently compute the identical version from the
same tag/commit-distance automatically — there's no separate step that keeps them "in sync," it's just
an emergent property of all three reading the same git history the same way.

**CI**: `unit-tests.yml`/`integration-tests.yml` now matrix over the three packages (integration only
over `pydoptic-sql`/`pydoptic-elastic` — `pydoptic` core has no integration tests). Each matrix leg
installs `packages/pydoptic` editable first (so pip's resolver is satisfied by this checkout's copy of
`pydoptic` rather than fetching one from PyPI for the `pydoptic-sql`/`pydoptic-elastic` legs, which
declare an unpinned `pydoptic` dependency), then that leg's own package with its `[test]` extra, then
runs `pytest test -q` from inside that package's own directory (not from the repo root) so each leg
picks up *its own* `pyproject.toml`'s `[tool.pytest.ini_options]` — pytest doesn't merge config from
multiple ini files in one run, so a combined root-level invocation wouldn't see the `integration`
marker registration/addopts declared in the per-package files. `release.yml`/`snapshot.yml` matrix the
`build` and `publish-to-pypi` jobs the same way (`python -m build packages/<name>`, artifact named
`dist-<name>` per leg since `upload-artifact@v4` requires unique names within a run), reusing the same
`environment: pypi` across all three matrix legs — trusted-publisher matching on PyPI's side is by
(repo, workflow filename, environment) *and* the target project (encoded in the built distribution's
own metadata, not the environment name), so the same environment name can be — and is — registered as
a trusted publisher on multiple different PyPI projects independently. `github-release` (in
`release.yml` only) stays a single non-matrixed job that waits on all three `publish-to-pypi` legs and
attaches all three's build artifacts to one GitHub Release, since lockstep versioning means one tag =
one release covering all three packages, not three separate releases.

**Still needed on the user's end, not something Claude can do**: register trusted publishers on PyPI
for the two *new* projects (`pydoptic-sql`, `pydoptic-elastic`) — same pattern as the existing
`pydoptic` ones (owner `johnhungerford`, repo `pydoptic`, workflow filename `release.yml` and
`snapshot.yml`, environment `pypi`), just registered on `pydoptic-sql`'s and `pydoptic-elastic`'s own
PyPI project pages instead of `pydoptic`'s.

## The two arity strategies — the single most important thing to understand here

There are **two different solutions** in this codebase for "how does a thing scoped to one table
work once you've joined several," and picking the wrong one for a new feature is the most likely way
to waste a lot of effort. The rule:

- **If a single instance can only ever reference one table** (`OrderBy`, `Computed`, a plain
  group-by column): use **one class**, and let it widen across arities via a **union type** at the
  point of storage — e.g. a 2-table join's `_order_by` field is
  `Sequence[OrderBy[TC] | OrderBy[TC1]]`. Qualification (`table.column` vs. bare `column`) is decided
  *externally*, by whichever query class ends up rendering it (`_order_by_sql(seq, qualify=...)` in
  `sql_query.py`), never baked into the object itself. This means an entry set before a `.join_inner()`
  call is still exactly correct after it — no re-wrapping needed. `Computed` and `OrderBy` both work
  this way on purpose.
- **If a single instance can reference multiple tables at once** (`Constraint.eq(Worker.age,
  Department.min_age)` — one constraint spanning two tables): you need a real **arity ladder**
  (`Constraint`, `Constraint2`, `Constraint3`, `Constraint4`, ..., each with its own
  `Comp/Between/InConstraint`). Qualification is baked into which class you used (arity-1 renders
  unqualified, arity-2+ always qualified) — these are structurally different renderings, not the same
  class with a flag. `HavingConstraint*` mirrors this exact shape for the same reason (a HAVING clause
  can compare `SUM(worker.age) > department.min_age`).

**Historical note, now resolved:** an arity-ladder value (`Constraint2[TC,TC1]`,
`HavingConstraint2[TC,TC1]`, ...) used to be unable to carry across a `.join_inner()` call the way
`OrderBy`/`Computed` can, since `HavingConstraint2` and `HavingConstraint3` are just unrelated classes
with no union relationship — this was *the* reason the old builder/terminal split existed (`.where()`
was only available on a pre-join "builder" as the one-time transition into a "terminal" class with no
further `.join_inner()`/`.join_left()`, and `join_inner`/`join_left` on the "Computed" builder classes
`assert self._having is None`, i.e. joining after `having()` was set was rejected outright).

**That limitation is gone.** Every concrete `Constraint`/`HavingConstraint` subclass at arities 1-3 now
has `.incr_arity()`, which rewraps the exact same operands into the next arity's class (e.g.
`CompConstraint[TC, A].incr_arity() -> CompConstraint2[TC, TC1, A]`, unifying the fresh `TC1` from
context the same way `join_inner`'s own `next: Type[TC1]` parameter already did). So:
- `QueryN`/`ComputedQueryN` are no longer split into builder/terminal classes — one class per arity,
  directly executable (`to_sql`/`to_sql_params`) at every stage, whether or not `.where()`/`.having()`
  was ever called.
- `join_inner`/`join_left` carry `_where` (and `_having`, on `Computed` queries) across by calling
  `.incr_arity()` on them when set, instead of requiring them unset. The old `assert self._having is
  None` is gone.
- `where_and`/`where_or` were added alongside the existing `having_and`/`having_or`, same AND/OR-compose-
  or-just-set semantics.
- One real behavior change from removing the builder/terminal split: `.where()` used to have a side
  effect of eagerly resolving an unset selection to "every column" (since it was the one-time
  transition to a terminal class with a resolved `_selection` field). Now selection resolution is
  fully lazy — done in a `_resolved_selection()` method called from `to_sql`/`to_sql_params()` (and by
  `sql_service.py`, which used to read the terminal's already-resolved `_selection` field directly and
  now calls `query._resolved_selection()` instead) — so calling `.where()` before `.select_computed()`
  no longer changes what an unset selection defaults to.

## Other load-bearing design decisions

- **Parameterization**: every query type has both `.to_sql()` (values interpolated into the string —
  for display/debugging only, and what all the plain string-equality unit tests check) and
  `.to_sql_params()` (returns `(sql_with_%s_placeholders, params_list)` — what `PsycoPgSqlTransaction.
  execute()` actually sends to psycopg). **Never use `.to_sql()`'s output for real execution** — that
  was the original SQL-injection bug this session fixed early on. `Computed`/`OrderBy`/plain group-by
  columns never contribute params (they're identifiers, not data); `CREATE TABLE` DDL is also
  deliberately left unparameterized (its literal values, e.g. a `Default` constraint, come from the
  model definition in code, not runtime data).
- **`Computed[TC, A]`** is a genuine `SelectVal[ComputedResult, A]` subclass (not a `PropSelect`), so
  `get_val`/`get_val_safe` extract an aggregate's value from a `ComputedResult` exactly like a `Prop`
  extracts a value from a model. `TC` is phantom bookkeeping (not part of the `Select` shape at all —
  origin is always `ComputedResult`), used purely so `select_computed(_more)` can be scoped per join
  arity the same way `OrderBy`'s `TC` is. `Select`'s "structural" methods (`set`, `update`, `clear`,
  `copy_to`, `__call__`/composition, `__hash__`, `.properties`) are all implemented in the *base*
  `Select` class via `match self: case PropSelect(): ... case MatchSelect(): ... case LinkedSelect(...):
  ... case _: raise ValueError()` — a closed set that doesn't include `Computed`. Only the *read* side
  (`get`/`get_unsafe`, genuinely-abstract "implemented per-subtype" hooks) works for `Computed`, which
  is fine since setting/mutating a computed aggregate value isn't meaningful anyway.
- **Computed columns require a separate class per arity** (`ComputedQuery1..4` alongside `Query1..4`)
  because the result type `R` can't conditionally vary based on runtime state — it's fixed at
  class-definition time (`class Query1(..., SqlQuery[PartialModel[TC]])` literally hardcodes `R`).
  This used to mean 8 *extra* classes on top of the builder/terminal split (`SelectQueryComputed`/
  `ComputedQuery1`, `JoinQuery2Computed`/`ComputedQuery2`, ...); now that the builder/terminal split is
  gone, it's just the 4 `ComputedQueryN` classes alongside the 4 `QueryN` ones — 8 total, not 16.
  `select_computed`/`select_computed_more` are available at every stage (not terminal-only, which was
  tried and explicitly rejected) since computed columns need to be referenceable from constraints
  (HAVING).
- **Default aliasing for `Computed`**: `SqlQuery.sum/avg/min/max/count_col` default their alias to
  `table_column_function` (e.g. `worker_age_sum`), deliberately including the function name — two
  aggregates over the same column (`SUM` and `AVG` of `worker.age`) would otherwise collide on both
  the SQL alias and the `ComputedResult` key. `SqlQuery.count(table)` (no column, `COUNT(*)`) defaults
  to `table_count`.
- **`HavingConstraint*`'s operand rendering**: a `Computed` operand inside a `HavingConstraint` renders
  as its bare function call (`SUM(age)`), never its alias (`worker_age_sum`) — Postgres doesn't make
  SELECT-list aliases visible inside HAVING (they *are* visible in GROUP BY/ORDER BY, a
  Postgres-specific extension, but not WHERE/HAVING).
- **List/dataclass ordering convention** established across `OrderBy`, `Computed`, group-by, and
  `HavingConstraint`: the "replace whole thing" method is named plainly (`order_by`, `group_by`,
  `select_computed`, `having`) and is **fully variadic including zero args to clear** (except
  `select_computed`, which requires at least one — there's nothing sensible to compute with zero
  aggregates); the "append" method has a `_more` suffix (`order_by_more`, `group_by_more`,
  `select_computed_more`) and requires at least one argument.
- **`having_and`/`having_or`** (and now `where_and`/`where_or`, added alongside them): AND/OR-compose
  with the existing `_having`/`_where` if set, else just set it — avoids the caller having to check
  `if self._having is None`/`if self._where is None` themselves.

## Chronological feature log (for orientation, not a full changelog — see `git log` for that)

1. Fixed three latent bugs found while writing tests for the original WIP `pydoptic_sql` integration:
   `CREATE TABLE` silently dropped column constraints, `IN` didn't quote string values, `INSERT`
   rendered missing optional values as the Python literal `"None"` instead of SQL `NULL`.
2. Split `Constraint`-family tests out of `test_sql_query.py` into `test_sql_constraint.py`.
3. Changed `.join_inner()`/`.join_left()`'s `on` parameter from variadic `*on: ConstraintN` to a
   single optional constraint (compose multiple conditions explicitly via `.AND()`/`.OR()`/`.all()`/
   `.any()` beforehand) — for consistency with `.where()`'s single-constraint shape.
4. **Parameterized every query by default** (`to_sql_params()`) — this was a real SQL injection fix,
   not just a nice-to-have; verified by actually sending a `'; DROP TABLE ...` payload through and
   confirming it round-tripped as inert data.
5. **ORDER BY** (`Direction`, `OrderBy`, `order_by`/`order_by_more`) — established the "single class +
   externally-controlled qualification, widens via union across join arities" pattern described above.
6. **Computed/aggregate columns** (`sql_computed.py`, `select_computed`/`select_computed_more`,
   `group_by`/`group_by_more`) — established that `Computed` follows `OrderBy`'s pattern (no arity
   ladder needed), but required doubling every builder/terminal class since it changes `R`.
7. **HAVING** (`sql_having.py`, `having`/`having_and`/`having_or`) — established that `HavingConstraint`
   needs `Constraint`'s arity-ladder pattern instead (a HAVING clause can span multiple tables), which
   in turn surfaced the `join_inner`-after-`having()` restriction.
8. **`Constraint.incr_arity()`/`HavingConstraint.incr_arity()`** (arities 1→2, 2→3, 3→4) — rewraps a
   constraint's operands into the next arity's class. Removed the structural reason the
   builder/terminal split existed.
9. **Collapsed the builder/terminal split, added `where_and`/`where_or`** — `QueryN`/`ComputedQueryN`
   now carry `_where`/`_having` across `join_inner`/`join_left` via `incr_arity()` instead of requiring
   them unset; one class per arity instead of two. See "The two arity strategies" above for the
   corrected picture and the one real behavior change (lazy selection resolution).

## Known gaps / explicitly flagged, not fixed

- **`AVG` returns `Decimal`, not `float`, at runtime** — Postgres maps `NUMERIC`/`AVG` results to
  Python `Decimal` via psycopg's default adapters, but `Computed.avg()`'s declared static type is
  `float`. Observed directly in a live-Postgres check, not theoretical. Flagged to the user, not fixed
  — fixing it would mean either changing the declared type (losing precision info) or coercing at the
  response layer (extra runtime cost/complexity for a fairly narrow case). No decision made yet.
- ~~The builder/terminal split itself is slated for reconsideration~~ — **done**: see "The two arity
  strategies" and chronological log items 8-9 above. `incr_arity()` was the mechanism; the split is
  gone.

## Working conventions established this session (not just for this codebase, general preferences)

- Every new query-building feature gets: mypy-clean unit tests covering the string-rendering (`to_sql`)
  and parameterized (`to_sql_params`) paths, *and* at least one live-Postgres integration test in
  `test_sql_service.py` actually verifying behavior (not just SQL text) against the real database —
  several bugs in this session were only caught by actually running against Postgres (e.g. the
  `SELECT *`-plus-aggregate default producing invalid SQL, the `Decimal`-vs-`float` mismatch).
  Building a feature and only unit-testing the string output is not considered complete.
  Prefer writing a small throwaway script for the live check, deleting it afterward (`/tmp/*_check.py`
  or the scratchpad dir), rather than skipping live verification.
- For any multi-step design with real forks (not just "which name"), talk through the design and get
  explicit agreement before writing code — this session's features (ORDER BY, Computed, HAVING) each
  started with an architecture discussion, sometimes multiple rounds, before any code was written.
  Don't silently narrow an agreed-upon scope without flagging it (this happened once — a
  terminal-only scoping of `select_computed` was quietly substituted for the agreed
  builder-and-terminal scope, and had to be walked back after the user caught it).
- Commit only when explicitly asked, with a message explaining *why*, and only after re-verifying
  mypy + full test suite pass (don't trust an earlier check if anything changed since).
