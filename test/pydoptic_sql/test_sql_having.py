import pytest

from pydoptic_sql import SqlTable, ColumnType, PrimaryKey, column, SqlQuery, Constraint, Constraint2, Constraint3, HavingConstraint, HavingConstraint2, HavingConstraint3
from pydoptic import Prop

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


# --- HavingConstraint (arity 1): plain-column and computed operands ---

def test_having_constraint_plain_column_comparison():
    assert HavingConstraint.gt(Worker.age, 30).to_sql() == 'age > 30'

def test_having_constraint_computed_operand_renders_function_call_not_alias():
    total = SqlQuery.sum(Worker.age)
    constraint = HavingConstraint.gt(total, 100)

    assert constraint.to_sql() == 'SUM(age) > 100'
    assert 'worker_age_sum' not in constraint.to_sql()

def test_having_constraint_count_star_operand():
    count = SqlQuery.count(Worker)

    assert HavingConstraint.gte(count, 2).to_sql() == 'COUNT(*) >= 2'

def test_having_constraint_computed_vs_computed():
    total = SqlQuery.sum(Worker.age)
    highest = SqlQuery.max(Worker.age)

    assert HavingConstraint.gt(total, highest).to_sql() == 'SUM(age) > MAX(age)'

def test_having_constraint_between():
    total = SqlQuery.sum(Worker.age)

    assert HavingConstraint.between(total, 10, 100).to_sql() == 'SUM(age) BETWEEN 10 AND 100'

def test_having_constraint_in():
    count = SqlQuery.count(Worker)

    assert HavingConstraint.in_(count, [1, 2, 3]).to_sql() == 'COUNT(*) IN (1, 2, 3)'

def test_having_constraint_and_or_not():
    total = SqlQuery.sum(Worker.age)
    constraint = HavingConstraint.all(
        HavingConstraint.gt(total, 100),
        HavingConstraint.lt(total, 1000).NOT,
    )

    assert constraint.to_sql() == '(SUM(age) > 100 AND NOT (SUM(age) < 1000))'

def test_having_constraint_params():
    total = SqlQuery.sum(Worker.age)
    sql, params = HavingConstraint.gt(total, 100).to_sql_params()

    assert sql == 'SUM(age) > %s'
    assert params == [100]


# --- HavingConstraint2 (joined, qualified rendering) ---

def test_having_constraint2_qualifies_computed_operand():
    total = SqlQuery.sum(Worker.age)

    assert HavingConstraint2.gt(total, 100).to_sql() == 'SUM(worker.age) > 100'

def test_having_constraint2_can_compare_computed_across_tables():
    total = SqlQuery.sum(Worker.age)

    assert HavingConstraint2[Worker, Department].gt(total, Department.min_age).to_sql() == 'SUM(worker.age) > department.min_age'


# --- query-level: having / having_and / having_or, WHERE + GROUP BY + HAVING + ORDER BY ---

def test_select_computed_having_single_table():
    total = SqlQuery.sum(Worker.age)
    query = SqlQuery.from_table(Worker).select(Worker.department_id).group_by(Worker.department_id).select_computed(total).having(HavingConstraint.gt(total, 100)).where()

    assert query.to_sql() == 'SELECT department_id, SUM(age) AS worker_age_sum FROM worker GROUP BY department_id HAVING SUM(age) > 100;'

def test_having_renders_after_group_by_and_before_order_by():
    total = SqlQuery.sum(Worker.age)
    query = SqlQuery.from_table(Worker).select(Worker.department_id).group_by(Worker.department_id).order_by_more(Worker.department_id).select_computed(total).having(HavingConstraint.gt(total, 100)).where()

    assert query.to_sql() == (
        'SELECT department_id, SUM(age) AS worker_age_sum FROM worker '
        'GROUP BY department_id HAVING SUM(age) > 100 ORDER BY department_id ASC;'
    )

def test_having_renders_after_where():
    total = SqlQuery.sum(Worker.age)
    query = SqlQuery.from_table(Worker).select(Worker.department_id).group_by(Worker.department_id).select_computed(total).having(HavingConstraint.gt(total, 100)).where(Constraint.gt(Worker.age, 18))

    assert query.to_sql() == (
        'SELECT department_id, SUM(age) AS worker_age_sum FROM worker WHERE age > 18 '
        'GROUP BY department_id HAVING SUM(age) > 100;'
    )

def test_having_and_combines_with_existing_constraint():
    total = SqlQuery.sum(Worker.age)
    query = SqlQuery.from_table(Worker).select(Worker.department_id).group_by(Worker.department_id).select_computed(total).having(
        HavingConstraint.gt(total, 100),
    ).having_and(HavingConstraint.lt(total, 1000)).where()

    assert query.to_sql() == (
        'SELECT department_id, SUM(age) AS worker_age_sum FROM worker '
        'GROUP BY department_id HAVING (SUM(age) > 100 AND SUM(age) < 1000);'
    )

def test_having_or_combines_with_existing_constraint():
    total = SqlQuery.sum(Worker.age)
    query = SqlQuery.from_table(Worker).select(Worker.department_id).group_by(Worker.department_id).select_computed(total).having(
        HavingConstraint.lt(total, 10),
    ).having_or(HavingConstraint.gt(total, 1000)).where()

    assert query.to_sql() == (
        'SELECT department_id, SUM(age) AS worker_age_sum FROM worker '
        'GROUP BY department_id HAVING (SUM(age) < 10 OR SUM(age) > 1000);'
    )

def test_having_and_with_no_prior_constraint_just_sets_it():
    total = SqlQuery.sum(Worker.age)
    query = SqlQuery.from_table(Worker).select(Worker.department_id).group_by(Worker.department_id).select_computed(total).having_and(HavingConstraint.gt(total, 100)).where()

    assert query.to_sql() == 'SELECT department_id, SUM(age) AS worker_age_sum FROM worker GROUP BY department_id HAVING SUM(age) > 100;'

def test_having_none_clears_it():
    total = SqlQuery.sum(Worker.age)
    query = SqlQuery.from_table(Worker).select(Worker.department_id).group_by(Worker.department_id).select_computed(total).having(HavingConstraint.gt(total, 100)).where()
    cleared = query.having(None)

    assert cleared.to_sql() == 'SELECT department_id, SUM(age) AS worker_age_sum FROM worker GROUP BY department_id;'

def test_having_query_params_include_where_then_having_in_order():
    total = SqlQuery.sum(Worker.age)
    query = SqlQuery.from_table(Worker).select(Worker.department_id).group_by(Worker.department_id).select_computed(total).having(
        HavingConstraint.gt(total, 100),
    ).where(Constraint.gt(Worker.age, 18))

    sql, params = query.to_sql_params()

    assert sql == (
        'SELECT department_id, SUM(age) AS worker_age_sum FROM worker WHERE age > %s '
        'GROUP BY department_id HAVING SUM(age) > %s;'
    )
    assert params == [18, 100]

def test_having_available_on_builder_before_where():
    total = SqlQuery.sum(Worker.age)
    query = SqlQuery.from_table(Worker).select(Worker.department_id).group_by(Worker.department_id).select_computed(total).having(HavingConstraint.gt(total, 100))
    finalized = query.where()

    assert finalized.to_sql() == 'SELECT department_id, SUM(age) AS worker_age_sum FROM worker GROUP BY department_id HAVING SUM(age) > 100;'


# --- joined queries: having across joined tables, and the join-after-having restriction ---

def test_having_on_joined_query_references_computed_from_joined_table():
    total = SqlQuery.sum(Worker.age)
    query = SqlQuery.from_table(Worker).join_inner(
        Department, Constraint2.eq(Worker.department_id, Department.id),
    ).select(Department.name).group_by(Department.name).select_computed(total).having(HavingConstraint2.gt(total, 50)).where()

    assert query.to_sql() == (
        'SELECT department.name, SUM(worker.age) AS worker_age_sum FROM worker '
        'INNER JOIN department ON worker.department_id = department.id '
        'GROUP BY department.name HAVING SUM(worker.age) > 50;'
    )

def test_having_set_before_join_is_rejected():
    # A HavingConstraintN is a distinct, unrelated class per arity (unlike OrderBy/Computed, which
    # are one class widened via unions), so an already-set having constraint can't be safely
    # re-typed for a wider join arity. join_inner/join_left must come before having().
    total = SqlQuery.sum(Worker.age)
    query = SqlQuery.from_table(Worker).select_computed(total).having(HavingConstraint.gt(total, 100))

    with pytest.raises(AssertionError):
        query.join_inner(Department, Constraint2.eq(Worker.department_id, Department.id))

def test_join_inner_still_works_before_having_is_set():
    total = SqlQuery.sum(Worker.age)
    query = SqlQuery.from_table(Worker).select_computed(total).join_inner(
        Department, Constraint2.eq(Worker.department_id, Department.id),
    ).select(Department.name).group_by(Department.name).having(HavingConstraint2.gt(total, 50)).where()

    assert query.to_sql() == (
        'SELECT department.name, SUM(worker.age) AS worker_age_sum FROM worker '
        'INNER JOIN department ON worker.department_id = department.id '
        'GROUP BY department.name HAVING SUM(worker.age) > 50;'
    )

def test_having3_can_reference_any_of_three_joined_tables():
    total = SqlQuery.sum(Worker.age)
    query = SqlQuery.from_table(Worker).join_inner(
        Department, Constraint2.eq(Worker.department_id, Department.id),
    ).join_inner(
        Project, Constraint3.eq(Project.department_id, Department.id),
    ).select(Project.name).group_by(Project.name).select_computed(total).having(
        HavingConstraint3.gt(total, Department.min_age),
    ).where()

    assert query.to_sql() == (
        'SELECT project.name, SUM(worker.age) AS worker_age_sum FROM worker '
        'INNER JOIN department ON worker.department_id = department.id '
        'INNER JOIN project ON project.department_id = department.id '
        'GROUP BY project.name HAVING SUM(worker.age) > department.min_age;'
    )
