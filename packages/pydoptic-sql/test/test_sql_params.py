from pydoptic_sql import SqlTable, ColumnType, PrimaryKey, column, SqlQuery, Constraint, Constraint2
from pydoptic import Prop, PropOpt

class Table(SqlTable):
    prop_1: Prop['Table', int] = column(type=ColumnType.BIGINT(), constraints=[PrimaryKey])
    prop_2: Prop['Table', str] = column(type=ColumnType.TEXT())
    prop_3: PropOpt['Table', str] = column()

class Employee(SqlTable):
    id: Prop['Employee', int] = column(type=ColumnType.BIGINT(), constraints=[PrimaryKey])
    name: Prop['Employee', str] = column(type=ColumnType.TEXT())
    age: Prop['Employee', int]
    department_id: Prop['Employee', int]

class Department(SqlTable):
    id: Prop['Department', int] = column(type=ColumnType.BIGINT(), constraints=[PrimaryKey])
    name: Prop['Department', str] = column(type=ColumnType.TEXT())


# --- DDL: no runtime params ---

def test_create_query_params_are_empty():
    sql, params = SqlQuery.create(Table).to_sql_params()

    assert sql == SqlQuery.create(Table).to_sql()
    assert params == []

def test_drop_query_params_are_empty():
    sql, params = SqlQuery.drop(Table).to_sql_params()

    assert sql == SqlQuery.drop(Table).to_sql()
    assert params == []


# --- INSERT ---

def test_insert_query_params():
    row = Table.construct(Table.prop_1.param(1), Table.prop_2.param("hi'; DROP TABLE table; --"))

    sql, params = SqlQuery.insert(row).to_sql_params()

    assert sql == 'INSERT INTO table VALUES (%s, %s, %s);'
    assert params == [1, "hi'; DROP TABLE table; --", None]


# --- UPDATE ---

def test_update_query_params_without_where():
    sql, params = SqlQuery.update(Table, Table.prop_2.param('hello')).to_sql_params()

    assert sql == 'UPDATE table SET prop_2 = %s;'
    assert params == ['hello']

def test_update_query_params_with_where():
    sql, params = SqlQuery.update(Table, Table.prop_2.param('hello')).where(Constraint.eq(Table.prop_1, 1)).to_sql_params()

    assert sql == 'UPDATE table SET prop_2 = %s WHERE prop_1 = %s;'
    assert params == ['hello', 1]

def test_update_query_params_multiple_values():
    sql, params = SqlQuery.update(Table, Table.prop_2.param('a'), Table.prop_3.param('b')).to_sql_params()

    assert sql == 'UPDATE table SET prop_2 = %s, prop_3 = %s;'
    assert params == ['a', 'b']


# --- DELETE ---

def test_delete_query_params_without_where():
    sql, params = SqlQuery.delete(Table).to_sql_params()

    assert sql == 'DELETE FROM table;'
    assert params == []

def test_delete_query_params_with_where():
    sql, params = SqlQuery.delete(Table).where(Constraint.eq(Table.prop_2, 'x')).to_sql_params()

    assert sql == 'DELETE FROM table WHERE prop_2 = %s;'
    assert params == ['x']


# --- SELECT (single table) ---

def test_select_query_params_no_where():
    sql, params = SqlQuery.from_table(Table).select(Table.prop_1).where().to_sql_params()

    assert sql == 'SELECT prop_1 FROM table;'
    assert params == []

def test_select_query_params_eq():
    sql, params = SqlQuery.from_table(Table).select(Table.prop_1).where(Constraint.eq(Table.prop_2, 'hello')).to_sql_params()

    assert sql == 'SELECT prop_1 FROM table WHERE prop_2 = %s;'
    assert params == ['hello']

def test_select_query_params_comparing_two_columns_has_no_params():
    sql, params = SqlQuery.from_table(Employee).select(Employee.id).where(Constraint.eq(Employee.age, Employee.department_id)).to_sql_params()

    assert sql == 'SELECT id FROM employee WHERE age = department_id;'
    assert params == []

def test_select_query_params_between():
    sql, params = SqlQuery.from_table(Employee).select(Employee.id).where(Constraint.between(Employee.age, 20, 30)).to_sql_params()

    assert sql == 'SELECT id FROM employee WHERE age BETWEEN %s AND %s;'
    assert params == [20, 30]

def test_select_query_params_in():
    sql, params = SqlQuery.from_table(Employee).select(Employee.id).where(Constraint.in_(Employee.age, [20, 30, 40])).to_sql_params()

    assert sql == 'SELECT id FROM employee WHERE age IN (%s, %s, %s);'
    assert params == [20, 30, 40]

def test_select_query_params_and_or_not_preserve_param_order():
    query = SqlQuery.from_table(Employee).select(Employee.id).where(
        Constraint.all(
            Constraint.any(
                Constraint.eq(Employee.name, 'Alice'),
                Constraint.eq(Employee.name, 'Bob'),
            ),
            Constraint.gt(Employee.age, 21).NOT,
        ),
    )

    sql, params = query.to_sql_params()

    assert sql == "SELECT id FROM employee WHERE ((name = %s OR name = %s) AND NOT (age > %s));"
    assert params == ['Alice', 'Bob', 21]


# --- JOIN (2 tables): on-condition params come before where-condition params ---

def test_join_query2_params():
    query = SqlQuery.from_table(Employee).join_inner(
        Department, Constraint2.eq(Employee.department_id, Department.id),
    ).select(Employee.name).where(Constraint2.gt(Employee.age, 30))

    sql, params = query.to_sql_params()

    assert sql == (
        'SELECT employee.name FROM employee INNER JOIN department ON employee.department_id = department.id '
        'WHERE employee.age > %s;'
    )
    assert params == [30]

def test_join_query2_params_with_literal_on_condition():
    query = SqlQuery.from_table(Employee).join_inner(
        Department, Constraint2.eq(Employee.department_id, 1),
    ).select(Employee.name).where()

    sql, params = query.to_sql_params()

    assert sql == 'SELECT employee.name FROM employee INNER JOIN department ON employee.department_id = %s;'
    assert params == [1]
