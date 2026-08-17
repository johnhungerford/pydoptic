from pydoptic_sql import SqlTable, ColumnType, PrimaryKey, AutoIncrement, column, Constraint, Constraint2, Constraint3, Constraint4
from pydoptic_sql.sql_constraint import BetweenConstraint, InConstraint, BetweenConstraint2, InConstraint2, BetweenConstraint3, InConstraint3
from pydoptic import Prop, PropOpt


class Employee(SqlTable):
    id: Prop['Employee', int] = column(type=ColumnType.BIGINT(), constraints=[PrimaryKey, AutoIncrement])
    name: Prop['Employee', str] = column(type=ColumnType.VARCHAR(100))
    age: Prop['Employee', int]
    salary: Prop['Employee', float]
    active: Prop['Employee', bool]
    department: PropOpt['Employee', str]


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


# --- Constraint2 (constraints spanning two joined tables) ---

def test_constraint2_always_qualifies_columns():
    assert Constraint2.eq(Worker.age, 30).to_sql() == 'worker.age = 30'


def test_constraint2_compares_columns_across_both_tables():
    assert Constraint2[Worker, Department].gte(Worker.age, Department.min_age).to_sql() == 'worker.age >= department.min_age'


def test_constraint2_quotes_string_literal_values():
    assert Constraint2.eq(Department.name, 'Engineering').to_sql() == "department.name = 'Engineering'"


def test_constraint2_and_combines_constraints_from_both_tables():
    constraint: Constraint2[Worker, Department] = Constraint2.all(
        Constraint2.gt(Worker.age, 30),
        Constraint2.eq(Department.name, 'Engineering'),
    )

    assert constraint.to_sql() == "(worker.age > 30 AND department.name = 'Engineering')"


def test_constraint2_or_combines_constraints_from_both_tables():
    constraint: Constraint2[Worker, Department] = Constraint2.any(
        Constraint2.eq(Worker.name, 'Alice'),
        Constraint2.eq(Department.name, 'Engineering'),
    )

    assert constraint.to_sql() == "(worker.name = 'Alice' OR department.name = 'Engineering')"


def test_constraint2_not():
    constraint = Constraint2[Worker, Department].eq(Worker.age, 30).NOT

    assert constraint.to_sql() == 'NOT (worker.age = 30)'


def test_constraint2_and_or_method_chaining():
    constraint = Constraint2[Worker, Department].gt(Worker.age, 30).AND(Constraint2.eq(Department.name, 'Engineering'))

    assert constraint.to_sql() == "(worker.age > 30 AND department.name = 'Engineering')"


def test_between_constraint2_with_columns_from_both_tables():
    constraint: BetweenConstraint2[Worker, Department, int] = BetweenConstraint2(Worker.age, Department.min_age, 65)

    assert constraint.to_sql() == 'worker.age BETWEEN department.min_age AND 65'


def test_in_constraint2():
    constraint: InConstraint2[Worker, Department, int] = InConstraint2(Worker.age, [20, 30, 40])

    assert constraint.to_sql() == 'worker.age IN (20, 30, 40)'


def test_constraint2_between_and_in_factories():
    assert Constraint2[Worker, Department].between(Worker.age, Department.min_age, 65).to_sql() == 'worker.age BETWEEN department.min_age AND 65'
    assert Constraint2[Worker, Department].in_(Worker.age, [20, 30]).to_sql() == 'worker.age IN (20, 30)'


# --- Constraint3 (constraints spanning three joined tables) ---

def test_constraint3_always_qualifies_columns():
    assert Constraint3[Worker, Department, Project].eq(Project.department_id, Department.id).to_sql() == 'project.department_id = department.id'


def test_constraint3_can_reference_all_three_tables_at_once():
    constraint: Constraint3[Worker, Department, Project] = Constraint3.all(
        Constraint3.eq(Worker.department_id, Department.id),
        Constraint3.eq(Project.department_id, Department.id),
        Constraint3.gt(Worker.age, 21),
    )

    assert constraint.to_sql() == '(worker.department_id = department.id AND project.department_id = department.id AND worker.age > 21)'


def test_between_constraint3():
    constraint: BetweenConstraint3[Worker, Department, Project, int] = BetweenConstraint3(Worker.age, Department.min_age, 65)

    assert constraint.to_sql() == 'worker.age BETWEEN department.min_age AND 65'


def test_in_constraint3():
    constraint: InConstraint3[Worker, Department, Project, int] = InConstraint3(Worker.age, [20, 30, 40])

    assert constraint.to_sql() == 'worker.age IN (20, 30, 40)'


# --- Constraint4 (constraints spanning four joined tables) ---

def test_constraint4_can_reference_all_four_tables():
    constraint: Constraint4[Worker, Department, Project, Task] = Constraint4.all(
        Constraint4.eq(Worker.department_id, Department.id),
        Constraint4.eq(Project.department_id, Department.id),
        Constraint4.eq(Task.project_id, Project.id),
    )

    assert constraint.to_sql() == (
        '(worker.department_id = department.id AND project.department_id = department.id AND task.project_id = project.id)'
    )
