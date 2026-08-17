# CONTEXT.md

Working notes for an ongoing feature-development session on `pydoptic_sql`, written because the
conversation that produced this work is about to run out of context. Read this before continuing
the work — it captures *why* things are shaped the way they are, which the code alone won't tell you
and which took real back-and-forth to arrive at. Skipping it risks re-litigating settled design
questions or reintroducing bugs that were already found and fixed.

## Where the work actually lives

**Do the work in `/Users/johnhungerford/projects/personal/pydoptic` on branch `main` directly.**
That's where every commit below actually landed. If you're reading this from a git worktree under
`.claude/worktrees/...`, that worktree is stale (last touched near the start of this effort) and is
*not* where this work happened — don't use it as a source of truth for current file contents.

Live Postgres integration tests connect to `host=localhost port=5432 dbname=pydoptic user=postgres
password=password` (see `docker-compose.yml`); bring it up with `docker compose up -d db` if it's not
already running. Elasticsearch (also in `docker-compose.yml`) is unrelated to this work.

## What `pydoptic_sql` is

A type-safe SQL query builder layered on `pydoptic` (the base package's "reified optics" / selector
system — `Select`, `PropSelect`, `Prop`, `PropOpt`, etc. in `src/pydoptic/selector.py`). Its
distinguishing feature versus mainstream options (SQLAlchemy, peewee, etc.): join arity is tracked in
the type system itself, so a WHERE/ON/HAVING clause can't reference a table that isn't actually in
scope at that point in a join chain — mypy catches it, not just Postgres at runtime.

## Commands

```bash
# from repo root
venv/bin/python -m mypy . --config-file mypy.ini
PYTHONPATH=src venv/bin/python -m pytest test -q
```
`venv/` at the repo root already has mypy and pytest installed — use it rather than system Python
(which is too old for this codebase's `match` statements etc.).

## Current state

- Everything through **"Add computed (aggregate) column support to the SqlQuery DSL"** (commit
  `930d760`) is committed on `main`.
- **HAVING support is built, tested, and verified, but not yet committed.** New/modified files:
  `src/pydoptic_sql/sql_having.py` (new), `src/pydoptic_sql/sql_query.py` (modified),
  `src/pydoptic_sql/__init__.py` (modified), `test/pydoptic_sql/test_sql_having.py` (new),
  `test/pydoptic_sql/test_sql_service.py` (modified). Commit these (with the user's go-ahead) before
  starting anything new, or the next session will have to rediscover this same context.
- mypy is clean (27 source files). Full test suite is 282 passed (unit tests + live-Postgres
  integration tests — the latter require the `db` container above to be running).

## Module map (`src/pydoptic_sql/`)

| File | Purpose |
|---|---|
| `sql_table.py` | `SqlTable` base, `ColumnType`, `column()`, DDL column constraints (`PrimaryKey`, `Unique`, `AutoIncrement`, `ForeignKey`, `Check`, `Default`) |
| `sql_constraint.py` | `Constraint`/`Constraint2`/`Constraint3`/`Constraint4` — WHERE and JOIN-ON conditions, one arity-ladder class family per number of tables a single constraint can span |
| `sql_order.py` | `Direction`, `OrderBy` — ORDER BY. Deliberately **not** an arity ladder (see below) |
| `sql_computed.py` | `AggregateFunction`, `ComputedResult`, `Computed[TC, A]` — aggregate/computed columns (SUM/COUNT/AVG/MIN/MAX) |
| `sql_having.py` | `HavingConstraint`/`2`/`3`/`4` — HAVING conditions; a genuinely separate hierarchy from `Constraint*`, not reused, so `Computed` values stay statically unusable in WHERE/ON |
| `sql_query.py` | The big one (~1370 lines): `SqlQuery` base + every builder/terminal query class, both plain and "Computed" variants. See below for the full class list |
| `sql_service.py` | `PsycoPgSqlClient`/`Transaction`/`*Response` — executes queries against Postgres via `psycopg`, decodes rows back into `PartialModel`/`ComputedResult` |

Tests mirror this 1:1 under `test/pydoptic_sql/` (`test_sql_query.py`, `test_sql_constraint.py`,
`test_sql_params.py`, `test_sql_computed.py`, `test_sql_having.py`, `test_sql_service.py` for the
live-DB integration tests).

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

**Consequence:** an arity-ladder value (`Constraint2[TC,TC1]`, `HavingConstraint2[TC,TC1]`, ...)
**cannot be carried across a `.join_inner()` call** the way `OrderBy`/`Computed` can — there's no
union relationship between e.g. `HavingConstraint2` and `HavingConstraint3`, they're just unrelated
classes, and even if you forced a cast, `.AND()`/`.OR()` on the narrower one wouldn't accept the wider
one's argument type anyway. This is why:
- `.where()` is only ever available on a **builder** (pre-join-completion) as the one-time transition
  into a **terminal** query class that has no further `.join_inner()`/`.join_left()` — once a
  `Constraint[TC]` is set, unqualified column references inside it could become ambiguous if you
  joined in another table with a same-named column, and there's no way to safely re-type it for the
  wider arity. This is *the* reason the builder/terminal split exists, not just a stylistic choice.
- Similarly, `join_inner`/`join_left` on the "Computed" builder classes now `assert self._having is
  None` — set `having()` after your last join, not before, or the join methods raise clearly rather
  than silently dropping the constraint. (This is a **known, deliberate limitation**, not an oversight
  — see "Known gaps" below for the planned fix.)

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
- **Computed columns required doubling every builder/terminal class** (8 new classes:
  `SelectQueryComputed`/`ComputedQuery1`, `JoinQuery2Computed`/`ComputedQuery2`, `JoinQuery3Computed`/
  `ComputedQuery3`, `JoinQuery4Computed`/`ComputedQuery4`) because the result type `R` can't
  conditionally vary based on runtime state — it's fixed at class-definition time (`class Query1(...,
  SqlQuery[PartialModel[TC]])` literally hardcodes `R`). `select_computed`/`select_computed_more` are
  available on *both* builders and terminals (not terminal-only, which was tried and explicitly
  rejected) since computed columns need to be referenceable from constraints eventually (HAVING now
  fulfills that).
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
- **`having_and`/`having_or`**: AND/OR-compose with the existing `_having` if set, else just set it —
  avoids the caller having to check `if self._having is None` themselves.

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

## Known gaps / explicitly flagged, not fixed

- **`AVG` returns `Decimal`, not `float`, at runtime** — Postgres maps `NUMERIC`/`AVG` results to
  Python `Decimal` via psycopg's default adapters, but `Computed.avg()`'s declared static type is
  `float`. Observed directly in a live-Postgres check, not theoretical. Flagged to the user, not fixed
  — fixing it would mean either changing the declared type (losing precision info) or coercing at the
  response layer (extra runtime cost/complexity for a fairly narrow case). No decision made yet.
- **The builder/terminal split itself is slated for reconsideration.** The user's own words, most
  recent turn before this doc: *"We'll update `where` to work the same way [`having`/`having_and`/
  `having_or`] next -- I have an idea about it."* That idea has **not been discussed yet** — don't
  assume any particular direction (e.g. don't assume it means "make `Constraint` qualify-externally
  like `OrderBy`," which was *my* speculation during the HAVING discussion about what *could* remove
  the split, not the user's actual plan). Ask them what they have in mind before implementing anything
  here.
- HAVING's `assert self._having is None` restriction on joining (see above) is a direct consequence of
  not yet having solved the arity-ladder-carries-across-joins problem in general. If the `where`
  redesign solves it, the same fix likely applies to `having` too — worth revisiting together.

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
