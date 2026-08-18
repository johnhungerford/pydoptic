import pytest

from pydoptic_sql import SqlTable, ColumnType, PrimaryKey, column, SqlQuery, Constraint, Constraint2, Constraint3, Constraint4, Direction, HavingConstraint, HavingConstraint2
from pydoptic import Prop, PropOpt
import psycopg

from pydoptic_sql.sql_service import PsycoPgSqlClient

pytestmark = pytest.mark.integration

_DB_DSN = "host=localhost port=5432 dbname=pydoptic user=postgres password=password"

class MyTable(SqlTable):
    prop_1: Prop['MyTable', int] = column(type=ColumnType.BIGINT(), constraints=[PrimaryKey])
    prop_2: Prop['MyTable', str] = column(type=ColumnType.TEXT())
    prop_3: Prop['MyTable', bool]


class Department(SqlTable):
    id: Prop['Department', int] = column(type=ColumnType.BIGINT(), constraints=[PrimaryKey])
    name: Prop['Department', str] = column(type=ColumnType.TEXT())
    min_age: Prop['Department', int] = column(type=ColumnType.INT())


class Worker(SqlTable):
    id: Prop['Worker', int] = column(type=ColumnType.BIGINT(), constraints=[PrimaryKey])
    name: Prop['Worker', str] = column(type=ColumnType.TEXT())
    department_id: Prop['Worker', int]
    age: Prop['Worker', int]


class Project(SqlTable):
    id: Prop['Project', int] = column(type=ColumnType.BIGINT(), constraints=[PrimaryKey])
    name: Prop['Project', str] = column(type=ColumnType.TEXT())
    department_id: Prop['Project', int]


class Task(SqlTable):
    id: Prop['Task', int] = column(type=ColumnType.BIGINT(), constraints=[PrimaryKey])
    name: Prop['Task', str] = column(type=ColumnType.TEXT())
    project_id: Prop['Task', int]
    done: Prop['Task', bool]


# --- CREATE / INSERT / SELECT (single table) ---

def test_create_query_table():
    with psycopg.connect(_DB_DSN) as conn:
        pg_client = PsycoPgSqlClient(conn)

        with pg_client.open() as tx:
            try:
                tx.execute(SqlQuery.create(MyTable))

                res = tx.execute(SqlQuery.from_table(MyTable).select(MyTable.prop_1, MyTable.prop_2).where())
                value = res.fetchone()
                assert value is None
            finally:
                tx.execute(SqlQuery.drop(MyTable))
                tx.commit()

def test_create_create_insert_query():
    with psycopg.connect(_DB_DSN) as conn:
        pg_client = PsycoPgSqlClient(conn)

        try:
            with pg_client.open() as tx:
                tx.execute(SqlQuery.create(MyTable))

                tx.execute(SqlQuery.insert(MyTable.construct(
                    MyTable.prop_1.param(50),
                    MyTable.prop_2.param('some text'),
                    MyTable.prop_3.param(True),
                )))

                res = tx.execute(
                    SqlQuery
                    .from_table(MyTable)
                    .select(MyTable.prop_1, MyTable.prop_2, MyTable.prop_3)
                    .where(Constraint.eq(MyTable.prop_2, 'some text'))
                )

                value = res.fetchone()
                assert value is not None
                assert MyTable.prop_1.get_val_safe(value) == 50
                assert MyTable.prop_2.get_val_safe(value) == 'some text'
                assert MyTable.prop_3.get_val_safe(value) == True
        finally:
            with pg_client.open() as tx:
                try:
                    tx.execute(SqlQuery.drop(MyTable))
                    tx.commit()
                except:
                    ...


# --- UPDATE / DELETE (single table) ---

def test_update_query():
    with psycopg.connect(_DB_DSN) as conn:
        pg_client = PsycoPgSqlClient(conn)

        try:
            with pg_client.open() as tx:
                tx.execute(SqlQuery.create(MyTable))

                tx.execute(SqlQuery.insert(MyTable.construct(
                    MyTable.prop_1.param(1),
                    MyTable.prop_2.param('before'),
                    MyTable.prop_3.param(False),
                )))

                tx.execute(SqlQuery.update(
                    MyTable, MyTable.prop_2.param('after'), MyTable.prop_3.param(True),
                ).where(Constraint.eq(MyTable.prop_1, 1)))

                res = tx.execute(
                    SqlQuery.from_table(MyTable).select(MyTable.prop_2, MyTable.prop_3).where(
                        Constraint.eq(MyTable.prop_1, 1),
                    )
                )

                value = res.fetchone()
                assert value is not None
                assert MyTable.prop_2.get_val_safe(value) == 'after'
                assert MyTable.prop_3.get_val_safe(value) == True
        finally:
            with pg_client.open() as tx:
                try:
                    tx.execute(SqlQuery.drop(MyTable))
                    tx.commit()
                except:
                    ...

def test_delete_query():
    with psycopg.connect(_DB_DSN) as conn:
        pg_client = PsycoPgSqlClient(conn)

        try:
            with pg_client.open() as tx:
                tx.execute(SqlQuery.create(MyTable))

                tx.execute(SqlQuery.insert(MyTable.construct(
                    MyTable.prop_1.param(1),
                    MyTable.prop_2.param('keep'),
                    MyTable.prop_3.param(True),
                )))
                tx.execute(SqlQuery.insert(MyTable.construct(
                    MyTable.prop_1.param(2),
                    MyTable.prop_2.param('remove'),
                    MyTable.prop_3.param(False),
                )))

                tx.execute(SqlQuery.delete(MyTable).where(Constraint.eq(MyTable.prop_1, 2)))

                remaining = list(tx.execute(SqlQuery.from_table(MyTable).select(MyTable.prop_1, MyTable.prop_2).where()).stream())
                assert len(remaining) == 1
                assert MyTable.prop_1.get_val_safe(remaining[0]) == 1
                assert MyTable.prop_2.get_val_safe(remaining[0]) == 'keep'
        finally:
            with pg_client.open() as tx:
                try:
                    tx.execute(SqlQuery.drop(MyTable))
                    tx.commit()
                except:
                    ...


# --- ORDER BY (single table) ---

def test_select_query_order_by():
    with psycopg.connect(_DB_DSN) as conn:
        pg_client = PsycoPgSqlClient(conn)

        try:
            with pg_client.open() as tx:
                tx.execute(SqlQuery.create(MyTable))

                for prop_1, prop_2 in [(30, 'c'), (10, 'a'), (20, 'b')]:
                    tx.execute(SqlQuery.insert(MyTable.construct(
                        MyTable.prop_1.param(prop_1), MyTable.prop_2.param(prop_2), MyTable.prop_3.param(True),
                    )))

                ascending = list(tx.execute(
                    SqlQuery.from_table(MyTable).select(MyTable.prop_1).where().order_by_more(MyTable.prop_1),
                ).stream())
                assert [MyTable.prop_1.get_val_safe(r) for r in ascending] == [10, 20, 30]

                descending = list(tx.execute(
                    SqlQuery.from_table(MyTable).select(MyTable.prop_1).where().order_by_more(MyTable.prop_1, Direction.DESC),
                ).stream())
                assert [MyTable.prop_1.get_val_safe(r) for r in descending] == [30, 20, 10]
        finally:
            with pg_client.open() as tx:
                try:
                    tx.execute(SqlQuery.drop(MyTable))
                    tx.commit()
                except:
                    ...


# --- JOIN (multiple tables) ---

def test_join_query2_inner():
    with psycopg.connect(_DB_DSN) as conn:
        pg_client = PsycoPgSqlClient(conn)

        try:
            with pg_client.open() as tx:
                tx.execute(SqlQuery.create(Department))
                tx.execute(SqlQuery.create(Worker))

                tx.execute(SqlQuery.insert(Department.construct(
                    Department.id.param(1), Department.name.param('Engineering'), Department.min_age.param(21),
                )))
                tx.execute(SqlQuery.insert(Department.construct(
                    Department.id.param(2), Department.name.param('Sales'), Department.min_age.param(18),
                )))
                tx.execute(SqlQuery.insert(Worker.construct(
                    Worker.id.param(1), Worker.name.param('Alice'), Worker.department_id.param(1), Worker.age.param(30),
                )))

                res = tx.execute(
                    SqlQuery.from_table(Worker).join_inner(
                        Department, Constraint2.eq(Worker.department_id, Department.id),
                    ).select(Worker.name, Department.name).where(
                        Constraint2.eq(Worker.name, 'Alice'),
                    )
                )

                pair = res.fetchone()
                assert pair is not None
                worker, department = pair
                assert Worker.name.get_val_safe(worker) == 'Alice'
                assert Department.name.get_val_safe(department) == 'Engineering'
        finally:
            with pg_client.open() as tx:
                try:
                    tx.execute(SqlQuery.drop(Worker))
                    tx.execute(SqlQuery.drop(Department))
                    tx.commit()
                except:
                    ...

def test_where_set_before_join_widens_and_filters_correctly():
    # where() set on a single-table query, before join_inner() widens it to Constraint2 via
    # incr_arity() -- verifies the widened constraint actually filters correctly against real rows,
    # not just that it renders the expected SQL text.
    with psycopg.connect(_DB_DSN) as conn:
        pg_client = PsycoPgSqlClient(conn)

        try:
            with pg_client.open() as tx:
                tx.execute(SqlQuery.create(Department))
                tx.execute(SqlQuery.create(Worker))

                tx.execute(SqlQuery.insert(Department.construct(
                    Department.id.param(1), Department.name.param('Engineering'), Department.min_age.param(21),
                )))
                tx.execute(SqlQuery.insert(Worker.construct(
                    Worker.id.param(1), Worker.name.param('Alice'), Worker.department_id.param(1), Worker.age.param(30),
                )))
                tx.execute(SqlQuery.insert(Worker.construct(
                    Worker.id.param(2), Worker.name.param('Bob'), Worker.department_id.param(1), Worker.age.param(17),
                )))

                res = tx.execute(
                    SqlQuery.from_table(Worker).where(Constraint.gte(Worker.age, 18)).join_inner(
                        Department, Constraint2.eq(Worker.department_id, Department.id),
                    ).select(Worker.name)
                )

                names = [Worker.name.get_val_safe(worker) for worker, _ in res.stream()]
                assert names == ['Alice']
        finally:
            with pg_client.open() as tx:
                try:
                    tx.execute(SqlQuery.drop(Worker))
                    tx.execute(SqlQuery.drop(Department))
                    tx.commit()
                except:
                    ...

def test_join_query2_where_and_filters_correctly():
    with psycopg.connect(_DB_DSN) as conn:
        pg_client = PsycoPgSqlClient(conn)

        try:
            with pg_client.open() as tx:
                tx.execute(SqlQuery.create(Department))
                tx.execute(SqlQuery.create(Worker))

                tx.execute(SqlQuery.insert(Department.construct(
                    Department.id.param(1), Department.name.param('Engineering'), Department.min_age.param(21),
                )))
                tx.execute(SqlQuery.insert(Worker.construct(
                    Worker.id.param(1), Worker.name.param('Alice'), Worker.department_id.param(1), Worker.age.param(30),
                )))
                tx.execute(SqlQuery.insert(Worker.construct(
                    Worker.id.param(2), Worker.name.param('Bob'), Worker.department_id.param(1), Worker.age.param(17),
                )))

                res = tx.execute(
                    SqlQuery.from_table(Worker).join_inner(
                        Department, Constraint2.eq(Worker.department_id, Department.id),
                    ).select(Worker.name).where(
                        Constraint2.eq(Worker.department_id, 1),
                    ).where_and(Constraint2.gte(Worker.age, 18))
                )

                names = [Worker.name.get_val_safe(worker) for worker, _ in res.stream()]
                assert names == ['Alice']
        finally:
            with pg_client.open() as tx:
                try:
                    tx.execute(SqlQuery.drop(Worker))
                    tx.execute(SqlQuery.drop(Department))
                    tx.commit()
                except:
                    ...

def test_join_query2_order_by():
    with psycopg.connect(_DB_DSN) as conn:
        pg_client = PsycoPgSqlClient(conn)

        try:
            with pg_client.open() as tx:
                tx.execute(SqlQuery.create(Department))
                tx.execute(SqlQuery.create(Worker))

                tx.execute(SqlQuery.insert(Department.construct(
                    Department.id.param(1), Department.name.param('Engineering'), Department.min_age.param(21),
                )))
                tx.execute(SqlQuery.insert(Worker.construct(
                    Worker.id.param(1), Worker.name.param('Carol'), Worker.department_id.param(1), Worker.age.param(35),
                )))
                tx.execute(SqlQuery.insert(Worker.construct(
                    Worker.id.param(2), Worker.name.param('Alice'), Worker.department_id.param(1), Worker.age.param(30),
                )))
                tx.execute(SqlQuery.insert(Worker.construct(
                    Worker.id.param(3), Worker.name.param('Bob'), Worker.department_id.param(1), Worker.age.param(25),
                )))

                rows = list(tx.execute(
                    SqlQuery.from_table(Worker).join_inner(
                        Department, Constraint2.eq(Worker.department_id, Department.id),
                    ).select(Worker.name).where().order_by_more(Worker.name)
                ).stream())

                assert [Worker.name.get_val_safe(worker) for worker, _ in rows] == ['Alice', 'Bob', 'Carol']
        finally:
            with pg_client.open() as tx:
                try:
                    tx.execute(SqlQuery.drop(Worker))
                    tx.execute(SqlQuery.drop(Department))
                    tx.commit()
                except:
                    ...

def test_join_query3_doubly_nested_join():
    with psycopg.connect(_DB_DSN) as conn:
        pg_client = PsycoPgSqlClient(conn)

        try:
            with pg_client.open() as tx:
                tx.execute(SqlQuery.create(Department))
                tx.execute(SqlQuery.create(Worker))
                tx.execute(SqlQuery.create(Project))

                tx.execute(SqlQuery.insert(Department.construct(
                    Department.id.param(1), Department.name.param('Engineering'), Department.min_age.param(21),
                )))
                tx.execute(SqlQuery.insert(Department.construct(
                    Department.id.param(2), Department.name.param('Sales'), Department.min_age.param(18),
                )))
                # Alice is old enough for Engineering and has a project to join to; Bob's department has no
                # project at all, so he's dropped by the second (inner) join regardless of the WHERE clause.
                tx.execute(SqlQuery.insert(Worker.construct(
                    Worker.id.param(1), Worker.name.param('Alice'), Worker.department_id.param(1), Worker.age.param(30),
                )))
                tx.execute(SqlQuery.insert(Worker.construct(
                    Worker.id.param(2), Worker.name.param('Bob'), Worker.department_id.param(2), Worker.age.param(25),
                )))
                tx.execute(SqlQuery.insert(Project.construct(
                    Project.id.param(1), Project.name.param('Apollo'), Project.department_id.param(1),
                )))

                res = tx.execute(
                    SqlQuery.from_table(Worker).join_inner(
                        Department, Constraint2.eq(Worker.department_id, Department.id),
                    ).join_inner(
                        Project, Constraint3.eq(Project.department_id, Department.id),
                    ).select(Worker.name, Department.name, Project.name).where(
                        Constraint3.gt(Worker.age, Department.min_age),
                    )
                )

                triple = res.fetchone()
                assert triple is not None
                worker, department, project = triple
                assert Worker.name.get_val_safe(worker) == 'Alice'
                assert Department.name.get_val_safe(department) == 'Engineering'
                assert Project.name.get_val_safe(project) == 'Apollo'
                assert res.fetchone() is None
        finally:
            with pg_client.open() as tx:
                try:
                    tx.execute(SqlQuery.drop(Project))
                    tx.execute(SqlQuery.drop(Worker))
                    tx.execute(SqlQuery.drop(Department))
                    tx.commit()
                except:
                    ...

def test_join_query4_triply_nested_join():
    with psycopg.connect(_DB_DSN) as conn:
        pg_client = PsycoPgSqlClient(conn)

        try:
            with pg_client.open() as tx:
                tx.execute(SqlQuery.create(Department))
                tx.execute(SqlQuery.create(Worker))
                tx.execute(SqlQuery.create(Project))
                tx.execute(SqlQuery.create(Task))

                tx.execute(SqlQuery.insert(Department.construct(
                    Department.id.param(1), Department.name.param('Engineering'), Department.min_age.param(21),
                )))
                tx.execute(SqlQuery.insert(Worker.construct(
                    Worker.id.param(1), Worker.name.param('Alice'), Worker.department_id.param(1), Worker.age.param(30),
                )))
                tx.execute(SqlQuery.insert(Project.construct(
                    Project.id.param(1), Project.name.param('Apollo'), Project.department_id.param(1),
                )))
                tx.execute(SqlQuery.insert(Task.construct(
                    Task.id.param(1), Task.name.param('Fix bug'), Task.project_id.param(1), Task.done.param(False),
                )))
                tx.execute(SqlQuery.insert(Task.construct(
                    Task.id.param(2), Task.name.param('Write tests'), Task.project_id.param(1), Task.done.param(True),
                )))

                res = tx.execute(
                    SqlQuery.from_table(Worker).join_inner(
                        Department, Constraint2.eq(Worker.department_id, Department.id),
                    ).join_inner(
                        Project, Constraint3.eq(Project.department_id, Department.id),
                    ).join_inner(
                        Task, Constraint4.eq(Task.project_id, Project.id),
                    ).select(Worker.name, Project.name, Task.name, Task.done).where().order_by_more(Task.name)
                )

                rows = list(res.stream())
                assert len(rows) == 2
                for worker, department, project, task in rows:
                    assert Worker.name.get_val_safe(worker) == 'Alice'
                    assert Project.name.get_val_safe(project) == 'Apollo'
                assert [Task.name.get_val_safe(task) for _, _, _, task in rows] == ['Fix bug', 'Write tests']
        finally:
            with pg_client.open() as tx:
                try:
                    tx.execute(SqlQuery.drop(Task))
                    tx.execute(SqlQuery.drop(Project))
                    tx.execute(SqlQuery.drop(Worker))
                    tx.execute(SqlQuery.drop(Department))
                    tx.commit()
                except:
                    ...


# --- COMPUTED (aggregates) ---

def test_select_computed_pure_aggregate():
    with psycopg.connect(_DB_DSN) as conn:
        pg_client = PsycoPgSqlClient(conn)

        try:
            with pg_client.open() as tx:
                tx.execute(SqlQuery.create(Worker))

                for id_, name, dept, age in [(1, 'Alice', 1, 30), (2, 'Bob', 1, 25), (3, 'Carol', 2, 40)]:
                    tx.execute(SqlQuery.insert(Worker.construct(
                        Worker.id.param(id_), Worker.name.param(name), Worker.department_id.param(dept), Worker.age.param(age),
                    )))

                total_age = SqlQuery.sum(Worker.age)
                res = tx.execute(SqlQuery.from_table(Worker).select_computed(total_age))

                row = res.fetchone()
                assert row is not None
                _, computed = row
                assert total_age.get_val_safe(computed) == 95
                assert res.fetchone() is None
        finally:
            with pg_client.open() as tx:
                try:
                    tx.execute(SqlQuery.drop(Worker))
                    tx.commit()
                except:
                    ...

def test_select_computed_with_group_by():
    with psycopg.connect(_DB_DSN) as conn:
        pg_client = PsycoPgSqlClient(conn)

        try:
            with pg_client.open() as tx:
                tx.execute(SqlQuery.create(Worker))

                for id_, name, dept, age in [(1, 'Alice', 1, 30), (2, 'Bob', 1, 25), (3, 'Carol', 2, 40)]:
                    tx.execute(SqlQuery.insert(Worker.construct(
                        Worker.id.param(id_), Worker.name.param(name), Worker.department_id.param(dept), Worker.age.param(age),
                    )))

                age_sum = SqlQuery.sum(Worker.age)
                res = tx.execute(
                    SqlQuery.from_table(Worker)
                    .select(Worker.department_id)
                    .group_by(Worker.department_id)
                    .order_by_more(Worker.department_id)
                    .select_computed(age_sum)
                    .where()
                )

                rows = list(res.stream())
                assert [(Worker.department_id.get_val_safe(pm), age_sum.get_val_safe(cr)) for pm, cr in rows] == [(1, 55), (2, 40)]
        finally:
            with pg_client.open() as tx:
                try:
                    tx.execute(SqlQuery.drop(Worker))
                    tx.commit()
                except:
                    ...

def test_select_computed_join_with_group_by():
    with psycopg.connect(_DB_DSN) as conn:
        pg_client = PsycoPgSqlClient(conn)

        try:
            with pg_client.open() as tx:
                tx.execute(SqlQuery.create(Department))
                tx.execute(SqlQuery.create(Worker))

                tx.execute(SqlQuery.insert(Department.construct(
                    Department.id.param(1), Department.name.param('Engineering'), Department.min_age.param(21),
                )))
                tx.execute(SqlQuery.insert(Department.construct(
                    Department.id.param(2), Department.name.param('Sales'), Department.min_age.param(18),
                )))
                for id_, name, dept, age in [(1, 'Alice', 1, 30), (2, 'Bob', 1, 25), (3, 'Carol', 2, 40)]:
                    tx.execute(SqlQuery.insert(Worker.construct(
                        Worker.id.param(id_), Worker.name.param(name), Worker.department_id.param(dept), Worker.age.param(age),
                    )))

                worker_count = SqlQuery.count(Worker)
                res = tx.execute(
                    SqlQuery.from_table(Worker)
                    .join_inner(Department, Constraint2.eq(Worker.department_id, Department.id))
                    .select(Department.name)
                    .group_by(Department.name)
                    .order_by_more(Department.name)
                    .select_computed(worker_count)
                    .where()
                )

                rows = list(res.stream())
                out = [(Department.name.get_val_safe(dept), worker_count.get_val_safe(cr)) for _, dept, cr in rows]
                assert out == [('Engineering', 2), ('Sales', 1)]
        finally:
            with pg_client.open() as tx:
                try:
                    tx.execute(SqlQuery.drop(Worker))
                    tx.execute(SqlQuery.drop(Department))
                    tx.commit()
                except:
                    ...


# --- HAVING (filtering on computed columns) ---

def test_having_filters_groups_by_aggregate_single_table():
    with psycopg.connect(_DB_DSN) as conn:
        pg_client = PsycoPgSqlClient(conn)

        try:
            with pg_client.open() as tx:
                tx.execute(SqlQuery.create(Worker))

                # department 1: 2 workers (passes HAVING count >= 2); department 2: 1 worker (fails)
                for id_, name, dept, age in [(1, 'Alice', 1, 30), (2, 'Bob', 1, 25), (3, 'Carol', 2, 40)]:
                    tx.execute(SqlQuery.insert(Worker.construct(
                        Worker.id.param(id_), Worker.name.param(name), Worker.department_id.param(dept), Worker.age.param(age),
                    )))

                worker_count = SqlQuery.count(Worker)
                res = tx.execute(
                    SqlQuery.from_table(Worker)
                    .select(Worker.department_id)
                    .group_by(Worker.department_id)
                    .select_computed(worker_count)
                    .having(HavingConstraint.gte(worker_count, 2))
                    .where()
                )

                rows = list(res.stream())
                out = [(Worker.department_id.get_val_safe(pm), worker_count.get_val_safe(cr)) for pm, cr in rows]
                assert out == [(1, 2)]
        finally:
            with pg_client.open() as tx:
                try:
                    tx.execute(SqlQuery.drop(Worker))
                    tx.commit()
                except:
                    ...

def test_having_filters_groups_by_aggregate_joined():
    with psycopg.connect(_DB_DSN) as conn:
        pg_client = PsycoPgSqlClient(conn)

        try:
            with pg_client.open() as tx:
                tx.execute(SqlQuery.create(Department))
                tx.execute(SqlQuery.create(Worker))

                tx.execute(SqlQuery.insert(Department.construct(
                    Department.id.param(1), Department.name.param('Engineering'), Department.min_age.param(21),
                )))
                tx.execute(SqlQuery.insert(Department.construct(
                    Department.id.param(2), Department.name.param('Sales'), Department.min_age.param(18),
                )))
                # Engineering: total age 55 (passes HAVING > 50); Sales: total age 40 (fails)
                for id_, name, dept, age in [(1, 'Alice', 1, 30), (2, 'Bob', 1, 25), (3, 'Carol', 2, 40)]:
                    tx.execute(SqlQuery.insert(Worker.construct(
                        Worker.id.param(id_), Worker.name.param(name), Worker.department_id.param(dept), Worker.age.param(age),
                    )))

                total_age = SqlQuery.sum(Worker.age)
                res = tx.execute(
                    SqlQuery.from_table(Worker)
                    .join_inner(Department, Constraint2.eq(Worker.department_id, Department.id))
                    .select(Department.name)
                    .group_by(Department.name)
                    .select_computed(total_age)
                    .having(HavingConstraint2.gt(total_age, 50))
                    .where()
                )

                rows = list(res.stream())
                out = [(Department.name.get_val_safe(dept), total_age.get_val_safe(cr)) for _, dept, cr in rows]
                assert out == [('Engineering', 55)]
        finally:
            with pg_client.open() as tx:
                try:
                    tx.execute(SqlQuery.drop(Worker))
                    tx.execute(SqlQuery.drop(Department))
                    tx.commit()
                except:
                    ...
