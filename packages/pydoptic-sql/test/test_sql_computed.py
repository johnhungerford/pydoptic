from pydoptic_sql import SqlTable, ColumnType, PrimaryKey, column, SqlQuery, Constraint, Constraint2
from pydoptic_sql.sql_computed import AggregateFunction, Computed, ComputedResult
from pydoptic_sql.sql_query import ComputedQuery1
from pydoptic import Prop, PropOpt

class Department(SqlTable):
    id: Prop['Department', int] = column(type=ColumnType.BIGINT(), constraints=[PrimaryKey])
    name: Prop['Department', str] = column(type=ColumnType.TEXT())
    min_age: Prop['Department', int] = column(type=ColumnType.INT())

class Worker(SqlTable):
    id: Prop['Worker', int] = column(type=ColumnType.BIGINT(), constraints=[PrimaryKey])
    name: Prop['Worker', str] = column(type=ColumnType.TEXT())
    department_id: Prop['Worker', int]
    age: Prop['Worker', int]
    bonus: PropOpt['Worker', float]


# --- ComputedResult ---

def test_computed_result_stores_and_retrieves_by_key():
    result = ComputedResult(total=42, label='x')

    assert result.total == 42
    assert result.label == 'x'
    assert result.as_dict() == {'total': 42, 'label': 'x'}

def test_computed_result_missing_attribute_raises():
    result = ComputedResult(total=42)

    try:
        result.missing
        assert False, 'expected AttributeError'
    except AttributeError:
        pass

def test_computed_result_equality_is_structural():
    assert ComputedResult(a=1, b=2) == ComputedResult(a=1, b=2)
    assert ComputedResult(a=1) != ComputedResult(a=2)


# --- Computed: construction, get_val, to_sql ---

def test_computed_get_val_reads_by_alias():
    computed = Computed(Worker.age, AggregateFunction.SUM, 'worker_age_sum', int)

    assert computed.get_val(ComputedResult(worker_age_sum=95)) == 95

def test_computed_get_val_safe_returns_none_when_missing():
    computed = Computed(Worker.age, AggregateFunction.SUM, 'worker_age_sum', int)

    assert computed.get_val_safe(ComputedResult()) is None

def test_computed_origin_and_target():
    computed = Computed(Worker.age, AggregateFunction.SUM, 'worker_age_sum', int)

    assert computed.origin is ComputedResult
    assert computed.target is int

def test_computed_to_sql_with_column():
    computed = Computed(Worker.age, AggregateFunction.SUM, 'worker_age_sum', int)

    assert computed.to_sql() == 'SUM(age) AS worker_age_sum'

def test_computed_to_sql_count_star():
    computed: Computed[Worker, int] = Computed(None, AggregateFunction.COUNT, 'worker_count', int)

    assert computed.to_sql() == 'COUNT(*) AS worker_count'


# --- SqlQuery aggregate factory methods ---

def test_sqlquery_sum_default_alias_and_target():
    computed = SqlQuery.sum(Worker.age)

    assert computed.label == 'worker_age_sum'
    assert computed.target is int
    assert computed.to_sql() == 'SUM(age) AS worker_age_sum'

def test_sqlquery_avg_default_alias_and_target():
    computed = SqlQuery.avg(Worker.age)

    assert computed.label == 'worker_age_avg'
    assert computed.target is float
    assert computed.to_sql() == 'AVG(age) AS worker_age_avg'

def test_sqlquery_min_and_max():
    lo = SqlQuery.min(Worker.age)
    hi = SqlQuery.max(Worker.age)

    assert lo.to_sql() == 'MIN(age) AS worker_age_min'
    assert hi.to_sql() == 'MAX(age) AS worker_age_max'

def test_sqlquery_count_counts_rows_not_a_column():
    computed = SqlQuery.count(Worker)

    assert computed.column is None
    assert computed.label == 'worker_count'
    assert computed.to_sql() == 'COUNT(*) AS worker_count'

def test_sqlquery_count_col_counts_non_null_values():
    computed = SqlQuery.count_col(Worker.bonus)

    assert computed.column is Worker.bonus
    assert computed.label == 'worker_bonus_count'
    assert computed.to_sql() == 'COUNT(bonus) AS worker_bonus_count'

def test_sqlquery_aggregate_default_alias_disambiguates_by_function():
    # Two aggregates over the same column must not collide, since that would produce a duplicate
    # SQL alias (a Postgres error) and would silently clobber the same ComputedResult key.
    sum_alias = SqlQuery.sum(Worker.age).label
    avg_alias = SqlQuery.avg(Worker.age).label

    assert sum_alias != avg_alias

def test_sqlquery_aggregate_explicit_alias_overrides_default():
    computed = SqlQuery.sum(Worker.age, alias='total_age')

    assert computed.label == 'total_age'
    assert computed.to_sql() == 'SUM(age) AS total_age'


# --- select_computed / select_computed_more: single table ---

def test_select_computed_pure_aggregate_has_no_plain_columns():
    query = SqlQuery.from_table(Worker).select_computed(SqlQuery.sum(Worker.age)).where()

    assert query.to_sql() == 'SELECT SUM(age) AS worker_age_sum FROM worker;'

def test_select_computed_to_sql_available_without_calling_where():
    query = SqlQuery.from_table(Worker).select_computed(SqlQuery.sum(Worker.age))

    assert query.to_sql() == 'SELECT SUM(age) AS worker_age_sum FROM worker;'

def test_select_computed_where_and_combines_with_existing_constraint():
    base = SqlQuery.from_table(Worker).select_computed(SqlQuery.sum(Worker.age)).where(Constraint.eq(Worker.department_id, 1))
    combined = base.where_and(Constraint.gt(Worker.age, 18))

    assert combined.to_sql() == 'SELECT SUM(age) AS worker_age_sum FROM worker WHERE (department_id = 1 AND age > 18);'

def test_select_computed_where_or_combines_with_existing_constraint():
    base = SqlQuery.from_table(Worker).select_computed(SqlQuery.sum(Worker.age)).where(Constraint.eq(Worker.department_id, 1))
    combined = base.where_or(Constraint.gt(Worker.age, 18))

    assert combined.to_sql() == 'SELECT SUM(age) AS worker_age_sum FROM worker WHERE (department_id = 1 OR age > 18);'

def test_select_computed_where_and_with_no_prior_constraint_just_sets_it():
    query = SqlQuery.from_table(Worker).select_computed(SqlQuery.sum(Worker.age)).where_and(Constraint.eq(Worker.department_id, 1))

    assert query.to_sql() == 'SELECT SUM(age) AS worker_age_sum FROM worker WHERE department_id = 1;'

def test_select_computed_after_where_still_has_no_plain_columns():
    # where() is just another constraint-setter now (it no longer "finalizes" a builder into a
    # terminal class with a resolved selection), so calling it first doesn't change what an unset
    # selection defaults to once select_computed is called -- still no plain columns, same as calling
    # select_computed with no where() at all.
    query = SqlQuery.from_table(Worker).where().select_computed(SqlQuery.sum(Worker.age))

    assert query.to_sql() == 'SELECT SUM(age) AS worker_age_sum FROM worker;'

def test_select_computed_more_appends():
    query = SqlQuery.from_table(Worker).select_computed(SqlQuery.sum(Worker.age)).where().select_computed_more(SqlQuery.count(Worker))

    assert query.to_sql() == 'SELECT SUM(age) AS worker_age_sum, COUNT(*) AS worker_count FROM worker;'

def test_select_computed_replaces_previous_computed_selection():
    base = SqlQuery.from_table(Worker).select_computed(SqlQuery.sum(Worker.age)).where()
    replaced = base.select_computed(SqlQuery.count(Worker))

    assert base.to_sql() == 'SELECT SUM(age) AS worker_age_sum FROM worker;'
    assert replaced.to_sql() == 'SELECT COUNT(*) AS worker_count FROM worker;'

def test_select_computed_with_plain_columns_and_group_by():
    query = SqlQuery.from_table(Worker).select(Worker.department_id).group_by(Worker.department_id).select_computed(SqlQuery.sum(Worker.age)).where()

    assert query.to_sql() == 'SELECT department_id, SUM(age) AS worker_age_sum FROM worker GROUP BY department_id;'

def test_select_computed_with_where_order_by_and_group_by():
    query = SqlQuery.from_table(Worker).select(Worker.department_id).group_by(Worker.department_id).order_by_more(Worker.department_id).select_computed(
        SqlQuery.sum(Worker.age),
    ).where(Constraint.gt(Worker.age, 18))

    assert query.to_sql() == (
        'SELECT department_id, SUM(age) AS worker_age_sum FROM worker '
        'WHERE age > 18 GROUP BY department_id ORDER BY department_id ASC;'
    )

def test_computed_query_requires_a_selection_or_computed_value():
    query = ComputedQuery1(Worker, [], None, (), (), [])

    try:
        query.to_sql()
        assert False, 'expected AssertionError'
    except AssertionError:
        pass

def test_select_computed_params_only_come_from_where():
    sql, params = SqlQuery.from_table(Worker).select_computed(SqlQuery.sum(Worker.age)).where(Constraint.eq(Worker.department_id, 1)).to_sql_params()

    assert sql == 'SELECT SUM(age) AS worker_age_sum FROM worker WHERE department_id = %s;'
    assert params == [1]


# --- group_by (independent of computed columns) ---

def test_group_by_more_appends_columns():
    query = SqlQuery.from_table(Worker).select(Worker.department_id, Worker.name).group_by_more(Worker.department_id).group_by_more(Worker.name).where()

    assert query.to_sql() == 'SELECT department_id, name FROM worker GROUP BY department_id, name;'

def test_group_by_replaces_and_clears():
    base = SqlQuery.from_table(Worker).select(Worker.department_id).group_by(Worker.department_id).where()
    replaced = base.group_by(Worker.name)
    cleared = replaced.group_by()

    assert base.to_sql() == 'SELECT department_id FROM worker GROUP BY department_id;'
    assert replaced.to_sql() == 'SELECT department_id FROM worker GROUP BY name;'
    assert cleared.to_sql() == 'SELECT department_id FROM worker;'

def test_group_by_set_on_builder_before_where_carries_through():
    query = SqlQuery.from_table(Worker).select(Worker.department_id).group_by_more(Worker.department_id).where()

    assert query.to_sql() == 'SELECT department_id FROM worker GROUP BY department_id;'


# --- select_computed: joined queries (arity 2), including pre-join carryover ---

def test_join_query2_select_computed_qualifies_column():
    query = SqlQuery.from_table(Worker).join_inner(
        Department, Constraint2.eq(Worker.department_id, Department.id),
    ).select(Department.name).group_by(Department.name).select_computed(SqlQuery.sum(Worker.age)).where()

    assert query.to_sql() == (
        'SELECT department.name, SUM(worker.age) AS worker_age_sum FROM worker '
        'INNER JOIN department ON worker.department_id = department.id GROUP BY department.name;'
    )

def test_select_computed_set_before_join_carries_through():
    # Same as OrderBy: Computed has no arity variants, so a Computed[Worker, ...] set while there's
    # only one table in scope is still exactly what gets rendered once a second table is joined in.
    query = SqlQuery.from_table(Worker).select_computed(SqlQuery.sum(Worker.age)).join_inner(
        Department, Constraint2.eq(Worker.department_id, Department.id),
    ).select(Department.name).group_by(Department.name).where()

    assert query.to_sql() == (
        'SELECT department.name, SUM(worker.age) AS worker_age_sum FROM worker '
        'INNER JOIN department ON worker.department_id = department.id GROUP BY department.name;'
    )

def test_select_computed_can_reference_either_joined_table():
    query = SqlQuery.from_table(Worker).join_inner(
        Department, Constraint2.eq(Worker.department_id, Department.id),
    ).select_computed(SqlQuery.avg(Worker.age), SqlQuery.max(Department.min_age)).where()

    assert query.to_sql() == (
        'SELECT AVG(worker.age) AS worker_age_avg, MAX(department.min_age) AS department_min_age_max FROM worker '
        'INNER JOIN department ON worker.department_id = department.id;'
    )
