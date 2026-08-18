# pydoptic-sql

A type-safe SQL query builder built on [pydoptic](https://pypi.org/project/pydoptic/).

Join arity is tracked in the type system itself, so a WHERE/ON/HAVING clause can't reference a table
that isn't actually in scope at that point in a join chain -- mypy catches it, not just Postgres at
runtime.

## Installation

```bash
pip install pydoptic-sql
```

Includes `psycopg` as a regular dependency, so no extras are needed to execute queries against
Postgres.

## Quickstart

```python3
from pydoptic import Prop
from pydoptic_sql import SqlTable, ColumnType, PrimaryKey, column, SqlQuery, Constraint, PsycoPgSqlClient
import psycopg

class Worker(SqlTable):
    id: Prop['Worker', int] = column(type=ColumnType.BIGINT(), constraints=[PrimaryKey])
    name: Prop['Worker', str] = column(type=ColumnType.TEXT())
    age: Prop['Worker', int] = column(type=ColumnType.INT())
    department_id: Prop['Worker', int] = column(type=ColumnType.BIGINT())

query = SqlQuery.from_table(Worker).select(Worker.name).where(Constraint.gte(Worker.age, 18))

with psycopg.connect("host=localhost dbname=mydb user=postgres password=password") as conn:
    client = PsycoPgSqlClient(conn)
    with client.open() as tx:
        for worker in tx.execute(query).stream():
            print(Worker.name.get_val_safe(worker))
```

Joining a second table generates a new query with two table type parameters. Constraints added to this
query are widened to include both table properties (e.g., `Constraint2` instead of `Constraint`):

```python3
class Department(SqlTable):
    id: Prop['Department', int] = column(type=ColumnType.BIGINT(), constraints=[PrimaryKey])
    name: Prop['Department', str] = column(type=ColumnType.TEXT())

from pydoptic_sql import Constraint2

query = SqlQuery.from_table(Worker).join_inner(
    Department, Constraint2.eq(Worker.department_id, Department.id),
).select(Worker.name, Department.name).where(Constraint2.gte(Worker.age, 18))
```

Currently, queries can include joins up to four tables deep.

See the [pydoptic README](https://github.com/johnhungerford/pydoptic/tree/main/packages/pydoptic) for
the underlying `Prop`/`Select` model this is built on.
