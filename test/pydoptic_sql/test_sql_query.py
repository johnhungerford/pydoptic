from pydoptic_sql import SqlTable, ColumnType, PrimaryKey, column, SqlQuery, Constraint
from pydoptic import Prop, PropOpt

class Table(SqlTable):
    prop_1: Prop['SqlTable', int] = column(type=ColumnType.BIGINT(), constraints=[PrimaryKey])
    prop_2: Prop['SqlTable', str] = column(type=ColumnType.TEXT())
    prop_3: Prop['SqlTable', bool]

def test_create_table_query():
    query = SqlQuery.create(Table)

    assert query.to_sql() == 'CREATE TABLE table (\nprop_1 BIGINT,\nprop_2 TEXT,\nprop_3 BOOLEAN\n);'

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

    assert query.to_sql() == 'SELECT prop_1, prop_2 FROM table WHERE (prop_2 LIKE "hello" AND prop_1 <= 235);'
