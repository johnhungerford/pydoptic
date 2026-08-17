from datetime import date, datetime

import pytest

from pydoptic_sql import SqlTable, ColumnType, PrimaryKey, AutoIncrement, column, SqlQuery, Constraint
from pydoptic_sql.sql_query import BetweenConstraint, InConstraint, SelectQuery, UpdateQuery, JoinQuery, JoinType
from pydoptic import Prop, PropOpt


class Table(SqlTable):
    prop_1: Prop['Table', int] = column(type=ColumnType.BIGINT(), constraints=[PrimaryKey, AutoIncrement])
    prop_2: Prop['Table', str] = column(type=ColumnType.TEXT())
    prop_3: Prop['Table', bool]
    prop_4: PropOpt['Table', str] = column()


class Employee(SqlTable):
    id: Prop['Employee', int] = column(type=ColumnType.BIGINT(), constraints=[PrimaryKey, AutoIncrement])
    name: Prop['Employee', str] = column(type=ColumnType.VARCHAR(100))
    age: Prop['Employee', int]
    salary: Prop['Employee', float]
    active: Prop['Employee', bool]
    department: PropOpt['Employee', str]


class AllColumnTypes(SqlTable):
    a_int: Prop['AllColumnTypes', int] = column(type=ColumnType.INT())
    a_smallint: Prop['AllColumnTypes', int] = column(type=ColumnType.SMALLINT())
    a_bigint: Prop['AllColumnTypes', int] = column(type=ColumnType.BIGINT())
    a_real: Prop['AllColumnTypes', float] = column(type=ColumnType.REAL())
    a_double: Prop['AllColumnTypes', float] = column(type=ColumnType.DOUBLE())
    a_bool: Prop['AllColumnTypes', bool] = column(type=ColumnType.BOOL())
    a_blob: Prop['AllColumnTypes', bytes] = column(type=ColumnType.BLOB())
    a_uuid: Prop['AllColumnTypes', str] = column(type=ColumnType.UUID())
    a_json: Prop['AllColumnTypes', str] = column(type=ColumnType.JSON())
    a_date: Prop['AllColumnTypes', str] = column(type=ColumnType.DATE())
    a_text: Prop['AllColumnTypes', str] = column(type=ColumnType.TEXT())
    a_ntext: Prop['AllColumnTypes', str] = column(type=ColumnType.TEXT(unicode=True))
    a_char: Prop['AllColumnTypes', str] = column(type=ColumnType.CHAR(10))
    a_nchar: Prop['AllColumnTypes', str] = column(type=ColumnType.CHAR(10, unicode=True))
    a_varchar: Prop['AllColumnTypes', str] = column(type=ColumnType.VARCHAR(50))
    a_nvarchar: Prop['AllColumnTypes', str] = column(type=ColumnType.VARCHAR(50, unicode=True))


class InferredTypes(SqlTable):
    an_int: Prop['InferredTypes', int]
    a_str: Prop['InferredTypes', str]
    a_bool: Prop['InferredTypes', bool]
    a_float: Prop['InferredTypes', float]
    a_date: Prop['InferredTypes', date]
    a_datetime: Prop['InferredTypes', datetime]


class UnsupportedColumnType(SqlTable):
    weird: Prop['UnsupportedColumnType', complex]


class Department(SqlTable):
    id: Prop['Department', int] = column(type=ColumnType.BIGINT(), constraints=[PrimaryKey])
    name: Prop['Department', str] = column(type=ColumnType.TEXT())


class Worker(SqlTable):
    id: Prop['Worker', int] = column(type=ColumnType.BIGINT(), constraints=[PrimaryKey])
    name: Prop['Worker', str] = column(type=ColumnType.TEXT())
    department_id: Prop['Worker', int]
    age: Prop['Worker', int]


# --- CREATE TABLE ---

def test_create_table_query():
    query = SqlQuery.create(Table)

    assert query.to_sql() == (
        'CREATE TABLE table (\n'
        'prop_1 BIGINT PRIMARY KEY AUTOINCREMENT,\n'
        'prop_2 TEXT,\n'
        'prop_3 BOOLEAN,\n'
        'prop_4 TEXT\n'
        ');'
    )


def test_create_table_query_with_explicit_column_types():
    query = SqlQuery.create(AllColumnTypes)

    assert query.to_sql() == (
        'CREATE TABLE allcolumntypes (\n'
        'a_int INTEGER,\n'
        'a_smallint SMALLINT,\n'
        'a_bigint BIGINT,\n'
        'a_real REAL,\n'
        'a_double DOUBLE PRECISION,\n'
        'a_bool BOOLEAN,\n'
        'a_blob BLOB,\n'
        'a_uuid UUID,\n'
        'a_json JSON,\n'
        'a_date DATE,\n'
        'a_text TEXT,\n'
        'a_ntext NTEXT,\n'
        'a_char CHAR(10),\n'
        'a_nchar NCHAR(10),\n'
        'a_varchar VARCHAR(50),\n'
        'a_nvarchar NVARCHAR(50)\n'
        ');'
    )


def test_create_table_query_infers_column_type_from_python_type():
    query = SqlQuery.create(InferredTypes)

    assert query.to_sql() == (
        'CREATE TABLE inferredtypes (\n'
        'an_int INTEGER,\n'
        'a_str TEXT,\n'
        'a_bool BOOLEAN,\n'
        'a_float REAL,\n'
        'a_date DATE,\n'
        'a_datetime DATE\n'
        ');'
    )


def test_create_table_query_raises_for_unsupported_column_type():
    query = SqlQuery.create(UnsupportedColumnType)

    with pytest.raises(ValueError):
        query.to_sql()


# --- DROP TABLE ---

def test_drop_table_query():
    query = SqlQuery.drop(Table)

    assert query.to_sql() == 'DROP TABLE table;'


def test_drop_table_query_uses_model_name_not_column_names():
    query = SqlQuery.drop(Employee)

    assert query.to_sql() == 'DROP TABLE employee;'


# --- INSERT ---

def test_insert_query():
    row = Employee.construct(
        Employee.id.param(1),
        Employee.name.param('Alice'),
        Employee.age.param(30),
        Employee.salary.param(1000.5),
        Employee.active.param(True),
        Employee.department.param('Sales'),
    )

    query = SqlQuery.insert(row)

    assert query.to_sql() == "INSERT INTO employee VALUES (1, 'Alice', 30, 1000.5, True, 'Sales');"


def test_insert_query_quotes_only_string_values():
    row = Table.construct(
        Table.prop_1.param(235),
        Table.prop_2.param('hello'),
        Table.prop_3.param(False),
    )

    query = SqlQuery.insert(row)

    assert query.to_sql() == "INSERT INTO table VALUES (235, 'hello', False, NULL);"


def test_insert_query_with_missing_optional_property():
    row = Employee.construct(
        Employee.id.param(2),
        Employee.name.param('Bob'),
        Employee.age.param(40),
        Employee.salary.param(2000.0),
        Employee.active.param(False),
    )

    query = SqlQuery.insert(row)

    assert query.to_sql() == "INSERT INTO employee VALUES (2, 'Bob', 40, 2000.0, False, NULL);"


# --- UPDATE ---

def test_update_query_single_value():
    query = SqlQuery.update(Employee, Employee.salary.param(2500.0))

    assert query.to_sql() == 'UPDATE employee SET salary = 2500.0;'


def test_update_query_multiple_values():
    query = SqlQuery.update(Employee, Employee.salary.param(2500.0), Employee.active.param(True))

    assert query.to_sql() == 'UPDATE employee SET salary = 2500.0, active = True;'


def test_update_query_quotes_string_values():
    query = SqlQuery.update(Employee, Employee.name.param('Alice'))

    assert query.to_sql() == "UPDATE employee SET name = 'Alice';"


def test_update_query_with_where_clause():
    query = SqlQuery.update(Employee, Employee.salary.param(2500.0)).where(
        Constraint.eq(Employee.id, 1),
    )

    assert query.to_sql() == 'UPDATE employee SET salary = 2500.0 WHERE id = 1;'


def test_update_query_sets_optional_property_to_null():
    query = SqlQuery.update(Employee, Employee.department.param(None))

    assert query.to_sql() == 'UPDATE employee SET department = NULL;'


def test_update_query_where_replaces_previous_where():
    base = SqlQuery.update(Employee, Employee.salary.param(2500.0)).where(Constraint.eq(Employee.id, 1))
    updated = base.where(Constraint.eq(Employee.id, 2))

    assert base.to_sql() == 'UPDATE employee SET salary = 2500.0 WHERE id = 1;'
    assert updated.to_sql() == 'UPDATE employee SET salary = 2500.0 WHERE id = 2;'


def test_update_query_requires_at_least_one_value():
    query = UpdateQuery(Employee, [])

    with pytest.raises(AssertionError):
        query.to_sql()


# --- DELETE ---

def test_delete_query_without_where():
    query = SqlQuery.delete(Employee)

    assert query.to_sql() == 'DELETE FROM employee;'


def test_delete_query_with_where_clause():
    query = SqlQuery.delete(Employee).where(Constraint.eq(Employee.id, 1))

    assert query.to_sql() == 'DELETE FROM employee WHERE id = 1;'


def test_delete_query_with_rich_where_clause():
    query = SqlQuery.delete(Employee).where(
        Constraint.all(
            Constraint.lt(Employee.age, 18),
            Constraint.eq(Employee.active, False),
        ),
    )

    assert query.to_sql() == 'DELETE FROM employee WHERE (age < 18 AND active = False);'


def test_delete_query_where_replaces_previous_where():
    base = SqlQuery.delete(Employee).where(Constraint.eq(Employee.id, 1))
    updated = base.where(Constraint.eq(Employee.id, 2))

    assert base.to_sql() == 'DELETE FROM employee WHERE id = 1;'
    assert updated.to_sql() == 'DELETE FROM employee WHERE id = 2;'


def test_delete_query_uses_model_name_not_column_names():
    query = SqlQuery.delete(Table)

    assert query.to_sql() == 'DELETE FROM table;'


# --- SELECT (basic shape) ---

def test_select_query_single_column():
    query = SqlQuery.select(Table.prop_1)

    assert query.to_sql() == 'SELECT prop_1 FROM table;'


def test_select_query_multiple_columns():
    query = SqlQuery.select(Employee.id, Employee.name, Employee.age)

    assert query.to_sql() == 'SELECT id, name, age FROM employee;'


def test_select_query_without_where_omits_where_clause():
    query = SqlQuery.select(Table.prop_1, Table.prop_2)

    assert query.to_sql() == 'SELECT prop_1, prop_2 FROM table;'


def test_select_query_requires_at_least_one_selected_property():
    query = SelectQuery(Table, [], None)

    with pytest.raises(AssertionError):
        query.to_sql()


def test_simply_select_query():
    query: SelectQuery[Table] = SqlQuery.select(
        Table.prop_1,
        Table.prop_2,
    ).where(
        Constraint.all(
            Constraint.like(Table.prop_2, 'hello'),
            Constraint.lte(Table.prop_1, 235),
        ),
    )

    assert query.to_sql() == 'SELECT prop_1, prop_2 FROM table WHERE (prop_2 LIKE \'hello\' AND prop_1 <= 235);'


# --- comparison constraints ---

def test_constraint_eq():
    assert Constraint.eq(Employee.age, 30).to_sql() == 'age = 30'


def test_constraint_ne():
    assert Constraint.ne(Employee.age, 30).to_sql() == 'age <> 30'


def test_constraint_gt():
    assert Constraint.gt(Employee.age, 30).to_sql() == 'age > 30'


def test_constraint_gte():
    assert Constraint.gte(Employee.age, 30).to_sql() == 'age >= 30'


def test_constraint_lt():
    assert Constraint.lt(Employee.age, 30).to_sql() == 'age < 30'


def test_constraint_lte():
    assert Constraint.lte(Employee.age, 30).to_sql() == 'age <= 30'


def test_constraint_like():
    assert Constraint.like(Employee.name, 'Al%').to_sql() == "name LIKE 'Al%'"


def test_constraint_quotes_string_literal_values():
    assert Constraint.eq(Employee.name, 'Alice').to_sql() == "name = 'Alice'"


def test_constraint_does_not_quote_non_string_values():
    assert Constraint.eq(Employee.age, 30).to_sql() == 'age = 30'
    assert Constraint.eq(Employee.salary, 1000.5).to_sql() == 'salary = 1000.5'


def test_constraint_compares_two_columns_on_the_same_table():
    assert Constraint.eq(Employee.age, Employee.id).to_sql() == 'age = id'


def test_constraint_on_optional_property():
    assert Constraint.eq(Employee.department, 'Sales').to_sql() == "department = 'Sales'"


# --- boolean combinators ---

def test_constraint_all_with_single_constraint():
    constraint = Constraint.all(Constraint.eq(Employee.age, 30))

    assert constraint.to_sql() == '(age = 30)'


def test_constraint_all_with_multiple_constraints():
    constraint = Constraint.all(
        Constraint.eq(Employee.age, 30),
        Constraint.eq(Employee.active, True),
        Constraint.gt(Employee.salary, 1000),
    )

    assert constraint.to_sql() == '(age = 30 AND active = True AND salary > 1000)'


def test_constraint_any_with_multiple_constraints():
    constraint = Constraint.any(
        Constraint.eq(Employee.name, 'Alice'),
        Constraint.eq(Employee.name, 'Bob'),
    )

    assert constraint.to_sql() == "(name = 'Alice' OR name = 'Bob')"


def test_constraint_not():
    constraint = Constraint.eq(Employee.age, 30).NOT

    assert constraint.to_sql() == 'NOT (age = 30)'


def test_constraint_and_method_chaining():
    constraint = Constraint.eq(Employee.age, 30).AND(Constraint.eq(Employee.active, True))

    assert constraint.to_sql() == '(age = 30 AND active = True)'


def test_constraint_or_method_chaining():
    constraint = Constraint.eq(Employee.age, 30).OR(Constraint.eq(Employee.active, True))

    assert constraint.to_sql() == '(age = 30 OR active = True)'


def test_constraint_deeply_nested_combinators():
    constraint = Constraint.all(
        Constraint.any(
            Constraint.eq(Employee.name, 'Alice'),
            Constraint.eq(Employee.name, 'Bob'),
        ),
        Constraint.gt(Employee.id, 0).NOT,
    )

    assert constraint.to_sql() == "((name = 'Alice' OR name = 'Bob') AND NOT (id > 0))"


# --- between / in constraints ---

def test_between_constraint_with_literal_bounds():
    constraint = BetweenConstraint(Employee.age, 20, 30)

    assert constraint.to_sql() == 'age BETWEEN 20 AND 30'


def test_between_constraint_with_property_bounds():
    constraint = BetweenConstraint(Employee.age, Employee.id, Employee.id)

    assert constraint.to_sql() == 'age BETWEEN id AND id'


def test_in_constraint_with_numeric_values():
    constraint = InConstraint(Employee.age, [20, 30, 40])

    assert constraint.to_sql() == 'age IN (20, 30, 40)'


def test_in_constraint_with_single_value():
    constraint = InConstraint(Employee.age, [20])

    assert constraint.to_sql() == 'age IN (20)'


def test_in_constraint_quotes_string_values():
    constraint = InConstraint(Employee.name, ['Alice', 'Bob'])

    assert constraint.to_sql() == "name IN ('Alice', 'Bob')"


# --- Constraint factory methods for between/in ---

def test_constraint_between_factory():
    constraint = Constraint.between(Employee.age, 20, 30)

    assert constraint.to_sql() == 'age BETWEEN 20 AND 30'


def test_constraint_in_factory_with_numeric_values():
    constraint = Constraint.in_(Employee.age, [20, 30, 40])

    assert constraint.to_sql() == 'age IN (20, 30, 40)'


def test_constraint_in_factory_with_string_values():
    constraint = Constraint.in_(Employee.name, ['Alice', 'Bob'])

    assert constraint.to_sql() == "name IN ('Alice', 'Bob')"


# --- SELECT combined with rich WHERE clauses ---

def test_select_query_with_between_constraint():
    query = SqlQuery.select(Employee.name, Employee.age).where(
        BetweenConstraint(Employee.age, 20, 30),
    )

    assert query.to_sql() == 'SELECT name, age FROM employee WHERE age BETWEEN 20 AND 30;'


def test_select_query_with_in_constraint():
    query = SqlQuery.select(Employee.name).where(
        InConstraint(Employee.age, [20, 30, 40]),
    )

    assert query.to_sql() == 'SELECT name FROM employee WHERE age IN (20, 30, 40);'


def test_select_query_with_nested_and_or_not_constraints():
    query = SqlQuery.select(Employee.id, Employee.name).where(
        Constraint.all(
            Constraint.any(
                Constraint.eq(Employee.name, 'Alice'),
                Constraint.eq(Employee.name, 'Bob'),
            ),
            Constraint.eq(Employee.active, False).NOT,
        ),
    )

    assert query.to_sql() == (
        "SELECT id, name FROM employee WHERE ((name = 'Alice' OR name = 'Bob') AND NOT (active = False));"
    )


def test_select_query_where_replaces_previous_where():
    base = SqlQuery.select(Employee.id).where(Constraint.eq(Employee.age, 1))
    updated = base.where(Constraint.eq(Employee.age, 2))

    assert base.to_sql() == 'SELECT id FROM employee WHERE age = 1;'
    assert updated.to_sql() == 'SELECT id FROM employee WHERE age = 2;'


# --- constraint qualification (used for joins) ---

def test_constraint_to_sql_unqualified_by_default():
    assert Constraint.eq(Worker.age, 30).to_sql() == 'age = 30'


def test_comp_constraint_qualified():
    assert Constraint.eq(Worker.age, 30).to_sql(qualify=True) == 'worker.age = 30'


def test_comp_constraint_qualified_column_to_column():
    assert Constraint.eq(Worker.age, Worker.id).to_sql(qualify=True) == 'worker.age = worker.id'


def test_between_constraint_qualified():
    assert BetweenConstraint(Worker.age, 20, 30).to_sql(qualify=True) == 'worker.age BETWEEN 20 AND 30'


def test_in_constraint_qualified():
    assert InConstraint(Worker.age, [20, 30]).to_sql(qualify=True) == 'worker.age IN (20, 30)'


def test_and_or_not_constraints_propagate_qualify():
    constraint = Constraint.all(
        Constraint.eq(Worker.age, 30),
        Constraint.eq(Worker.name, 'Alice').NOT,
    )

    assert constraint.to_sql(qualify=True) == "(worker.age = 30 AND NOT (worker.name = 'Alice'))"


# --- JOIN ---

def test_join_query_inner():
    query = SqlQuery.join_inner(Worker, Department).columns(Worker.name, Department.name).on(
        Worker.department_id, Department.id,
    )

    assert query.to_sql() == (
        'SELECT worker.name, department.name FROM worker INNER JOIN department ON worker.department_id = department.id;'
    )


def test_join_query_left():
    query = SqlQuery.join_left(Worker, Department).columns(Worker.id, Worker.name).on(
        Worker.department_id, Department.id,
    )

    assert query.to_sql() == (
        'SELECT worker.id, worker.name FROM worker LEFT JOIN department ON worker.department_id = department.id;'
    )


def test_join_query_with_where_left():
    query = SqlQuery.join_inner(Worker, Department).columns(Worker.name, Department.name).on(
        Worker.department_id, Department.id,
    ).where_left(
        Constraint.gt(Worker.age, 30),
    )

    assert query.to_sql() == (
        'SELECT worker.name, department.name FROM worker INNER JOIN department '
        'ON worker.department_id = department.id WHERE worker.age > 30;'
    )


def test_join_query_with_where_right():
    query = SqlQuery.join_inner(Worker, Department).columns(Worker.name, Department.name).on(
        Worker.department_id, Department.id,
    ).where_right(
        Constraint.eq(Department.name, 'Engineering'),
    )

    assert query.to_sql() == (
        "SELECT worker.name, department.name FROM worker INNER JOIN department "
        "ON worker.department_id = department.id WHERE department.name = 'Engineering';"
    )


def test_join_query_with_where_left_and_right():
    query = SqlQuery.join_inner(Worker, Department).columns(Worker.name, Department.name).on(
        Worker.department_id, Department.id,
    ).where_left(
        Constraint.gt(Worker.age, 30),
    ).where_right(
        Constraint.eq(Department.name, 'Engineering'),
    )

    assert query.to_sql() == (
        "SELECT worker.name, department.name FROM worker INNER JOIN department "
        "ON worker.department_id = department.id WHERE worker.age > 30 AND department.name = 'Engineering';"
    )


def test_join_query_with_compound_where():
    query = SqlQuery.join_inner(Worker, Department).columns(Worker.name).on(
        Worker.department_id, Department.id,
    ).where_left(
        Constraint.all(
            Constraint.gt(Worker.age, 30),
            Constraint.eq(Worker.name, 'Alice'),
        ),
    )

    assert query.to_sql() == (
        "SELECT worker.name FROM worker INNER JOIN department ON worker.department_id = department.id "
        "WHERE (worker.age > 30 AND worker.name = 'Alice');"
    )


def test_join_query_requires_columns():
    query = JoinQuery(JoinType.Inner, Worker, Department).on(Worker.department_id, Department.id)

    with pytest.raises(AssertionError):
        query.to_sql()


def test_join_query_requires_on():
    query = SqlQuery.join_inner(Worker, Department).columns(Worker.name)

    with pytest.raises(AssertionError):
        query.to_sql()


def test_join_query_where_left_and_where_right_replace_previous_value():
    base = SqlQuery.join_inner(Worker, Department).columns(Worker.name).on(
        Worker.department_id, Department.id,
    ).where_left(Constraint.eq(Worker.age, 1))
    updated = base.where_left(Constraint.eq(Worker.age, 2))

    assert base.to_sql() == (
        'SELECT worker.name FROM worker INNER JOIN department ON worker.department_id = department.id '
        'WHERE worker.age = 1;'
    )
    assert updated.to_sql() == (
        'SELECT worker.name FROM worker INNER JOIN department ON worker.department_id = department.id '
        'WHERE worker.age = 2;'
    )
