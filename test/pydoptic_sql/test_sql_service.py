from pydoptic_sql import SqlTable, ColumnType, PrimaryKey, column, SqlQuery, Constraint
from pydoptic import Prop, PropOpt
import psycopg

from pydoptic_sql.sql_service import PsycoPgSqlClient

class MyTable(SqlTable):
    prop_1: Prop['MyTable', int] = column(type=ColumnType.BIGINT(), constraints=[PrimaryKey])
    prop_2: Prop['MyTable', str] = column(type=ColumnType.TEXT())
    prop_3: Prop['MyTable', bool]

def test_create_query_table():
    with psycopg.connect("host=localhost port=5432 dbname=pydoptic user=postgres password=password") as conn:
        pg_client = PsycoPgSqlClient(conn)

        with pg_client.open() as tx:
            try:
                tx.execute(SqlQuery.create(MyTable))

                res = tx.execute(SqlQuery[MyTable].select(MyTable.prop_1, MyTable.prop_2))
                value = res.fetchone()
                assert value is None
            finally:
                tx.execute(SqlQuery.drop(MyTable))
                tx.commit()

def test_create_create_insert_query():
    with psycopg.connect("host=localhost port=5432 dbname=pydoptic user=postgres password=password") as conn:
        pg_client = PsycoPgSqlClient(conn)

        try:
            with pg_client.open() as tx:
                tx.execute(SqlQuery.create(MyTable))

                tx.execute(SqlQuery[MyTable].insert(MyTable.construct(
                    MyTable.prop_1.param(50),
                    MyTable.prop_2.param('some text'),
                    MyTable.prop_3.param(True),
                )))

                res = tx.execute(
                    SqlQuery[MyTable]
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