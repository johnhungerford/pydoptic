from pydoptic_sql import SqlTable, ColumnType, PrimaryKey, AutoIncrement, column, SqlQuery, Constraint
from pydoptic import Prop, PropOpt

class Table(SqlTable):
    prop_1: Prop['SqlTable', int] = column(type=ColumnType.BIGINT(), constraints=[PrimaryKey, AutoIncrement])
    prop_2: Prop['SqlTable', str] = column(type=ColumnType.TEXT())
    prop_3: Prop['SqlTable', bool]
    prop_4: PropOpt['SqlTable', str] = column()

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

def test_simply_select_query():
    query: SqlQuery[Table] = SqlQuery[Table].select(
        Table.prop_1,
        Table.prop_2,
    ).where(
        Constraint.all(
            Constraint.like(Table.prop_2, 'hello'),
            Constraint.lte(Table.prop_1, 235),
        ),
    )

    assert query.to_sql() == 'SELECT prop_1, prop_2 FROM table WHERE (prop_2 LIKE \'hello\' AND prop_1 <= 235);'

def test_insert_query_with_missing_optional_property():
    row = Table(prop_1=1, prop_2='hello', prop_3=True)
    query = SqlQuery.insert(row)

    assert query.to_sql() == "INSERT INTO table VALUES (1, 'hello', True, NULL);"

def test_in_constraint_with_numeric_values():
    constraint = Constraint.in_(Table.prop_1, [1, 2, 3])

    assert constraint.to_sql() == 'prop_1 IN (1, 2, 3)'

def test_in_constraint_with_string_values():
    constraint = Constraint.in_(Table.prop_2, ['hello', 'world'])

    assert constraint.to_sql() == "prop_2 IN ('hello', 'world')"

def test_between_constraint():
    constraint = Constraint.between(Table.prop_1, 1, 10)

    assert constraint.to_sql() == 'prop_1 BETWEEN 1 AND 10'
