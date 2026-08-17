
from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, List, Sequence, Tuple, Type, TypeVar, cast
from pydoptic import PartialModel
from pydoptic.selector import PropSelect, Prop, PropOpt, Param
from pydoptic_sql import SqlTable
from pydoptic_sql.sql_constraint import A, TC, TC1, TC2, TC3, Constraint, Constraint2, Constraint3, Constraint4, _qualified_label
from pydoptic_sql.sql_table import (
    AutoIncrement,
    Check,
    ColumnConstraint,
    ColumnInfo,
    ColumnType,
    Default,
    ForeignKey,
    ManualColumnConstraint,
    PrimaryKey,
    Unique,
)

R = TypeVar('R')

class SqlQuery(Generic[R]):
    # R is the result type of executing the query (e.g. PartialModel[TC], or None); table type(s) are tracked separately per subclass.
    def to_sql(self) -> str:
        """Render this query as a single SQL string with values interpolated -- for display/debugging only."""
        raise NotImplementedError()

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        """Render this query as a parameterized SQL string (`%s` placeholders) plus its bound values, in order --
        what actually gets executed, so data values are never interpolated into the SQL text itself."""
        raise NotImplementedError()

    @classmethod
    def from_table(cls, table: Type[TC]) -> 'SelectQuery[TC]':
        return SelectQuery(table)

    @classmethod
    def create(cls, table: Type[TC]) -> 'CreateQuery[TC]':
        return CreateQuery(table)

    @classmethod
    def drop(cls, table: Type[TC]) -> 'DropQuery[TC]':
        return DropQuery(table)

    @classmethod
    def insert(cls, row: TC) -> 'InsertQuery[TC]':
        return InsertQuery(row)

    @classmethod
    def update(cls, table: Type[TC], value: Param[TC, Any], *values: Param[TC, Any]) -> 'UpdateQuery[TC]':
        return UpdateQuery(table, [value, *values])

    @classmethod
    def delete(cls, table: Type[TC]) -> 'DeleteQuery[TC]':
        return DeleteQuery(table)


def _all_props(table: Type[SqlTable]) -> List[PropSelect[Any, Any]]:
    return [prop for prop in table.properties().values() if isinstance(prop, PropSelect)]

def _resolve_selection(selection: Sequence[PropSelect[Any, Any]] | None, *tables: Type[SqlTable]) -> List[PropSelect[Any, Any]]:
    """Unset selection ('you didn't call select()') defaults to every column of every joined table -- i.e. SELECT *."""
    if selection is not None:
        return list(selection)
    result: List[PropSelect[Any, Any]] = []
    for table in tables:
        result.extend(_all_props(table))
    return result


class JoinType(Enum):
    Left = 'LEFT'
    Inner = 'INNER'


# --- 1 table: SelectQuery (builder) -> Query1 (terminal) ---

@dataclass(frozen=True)
class SelectQuery(Generic[TC]):
    table1: Type[TC]
    _selection: Sequence[PropSelect[TC, Any]] | None = None

    def select(self, sel: PropSelect[TC, Any], *sels: PropSelect[TC, Any]) -> 'SelectQuery[TC]':
        return SelectQuery(self.table1, [sel, *sels])

    def select_more(self, sel: PropSelect[TC, Any], *sels: PropSelect[TC, Any]) -> 'SelectQuery[TC]':
        return SelectQuery(self.table1, [*(self._selection or []), sel, *sels])

    def join_inner(self, next: Type[TC1], on: Constraint2[TC, TC1] | None = None) -> 'JoinQuery2[TC, TC1]':
        return JoinQuery2(self.table1, next, JoinType.Inner, on, self._selection)

    def join_left(self, next: Type[TC1], on: Constraint2[TC, TC1] | None = None) -> 'JoinQuery2[TC, TC1]':
        return JoinQuery2(self.table1, next, JoinType.Left, on, self._selection)

    def where(self, constraint: Constraint[TC] | None = None) -> 'Query1[TC]':
        return Query1(self.table1, _resolve_selection(self._selection, self.table1), constraint)

@dataclass(frozen=True)
class Query1(Generic[TC], SqlQuery[PartialModel[TC]]):
    table1: Type[TC]
    _selection: Sequence[PropSelect[TC, Any]]
    _where: Constraint[TC] | None = None

    def select(self, sel: PropSelect[TC, Any], *sels: PropSelect[TC, Any]) -> 'Query1[TC]':
        return Query1(self.table1, [sel, *sels], self._where)

    def select_more(self, sel: PropSelect[TC, Any], *sels: PropSelect[TC, Any]) -> 'Query1[TC]':
        return Query1(self.table1, [*self._selection, sel, *sels], self._where)

    def where(self, constraint: Constraint[TC] | None = None) -> 'Query1[TC]':
        return Query1(self.table1, self._selection, constraint)

    def to_sql(self) -> str:
        assert len(self._selection) > 0, 'You must select at least one column'
        selections = ', '.join(p.label for p in self._selection)
        where_clause = '' if self._where is None else (' WHERE ' + self._where.to_sql())
        return f'SELECT {selections} FROM {self.table1.__name__.lower()}{where_clause};'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        assert len(self._selection) > 0, 'You must select at least one column'
        selections = ', '.join(p.label for p in self._selection)
        if self._where is None:
            return f'SELECT {selections} FROM {self.table1.__name__.lower()};', []
        where_clause, params = self._where.to_sql_params()
        return f'SELECT {selections} FROM {self.table1.__name__.lower()} WHERE {where_clause};', params


# --- CREATE / DROP / INSERT / UPDATE / DELETE (always single-table) ---

@dataclass
class DropQuery(Generic[TC], SqlQuery[None]):
    _model: Type[TC]

    def to_sql(self) -> str:
        return f'DROP TABLE {self._model.__name__.lower()};'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        return self.to_sql(), []

def _sql_literal(value: Any) -> str:
    if value is None:
        return 'NULL'
    if isinstance(value, str):
        return "'" + value + "'"
    return str(value)

def _column_constraint_to_sql(constraint: ColumnConstraint) -> str:
    if constraint is PrimaryKey:
        return 'PRIMARY KEY'
    if constraint is Unique:
        return 'UNIQUE'
    if constraint is AutoIncrement:
        return 'AUTOINCREMENT'
    if isinstance(constraint, ForeignKey):
        return f'REFERENCES {constraint.references.origin.__name__.lower()}({constraint.references.label})'
    if isinstance(constraint, Check):
        return f'CHECK ({constraint.constraint})'
    if isinstance(constraint, Default):
        return f'DEFAULT {_sql_literal(constraint.value)}'
    if isinstance(constraint, ManualColumnConstraint):
        return constraint.type
    raise ValueError(f'Unknown column constraint: {constraint}')

@dataclass(frozen=True)
class CreateQuery(Generic[TC], SqlQuery[None]):
    _model: Type[TC]

    def to_sql(self) -> str:
        header = f'CREATE TABLE {self._model.__name__.lower()} (\n'
        footer = '\n);'

        columns: List[str] = []

        for prop in self._model.properties().values():
            if isinstance(prop, PropSelect):
                prop_data = cast(ColumnInfo, prop.data)
                constraints = prop_data['constraints'] if 'constraints' in prop_data else []
                tpe = prop_data['type'] if 'type' in prop_data else ColumnType.from_type(prop.target)
                constraint_sqls = [_column_constraint_to_sql(c) for c in constraints]
                column = ' '.join([f'{prop.label} {tpe.to_sql()}', *constraint_sqls])
                columns.append(column)

        return header + ',\n'.join(columns) + footer

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        # DDL: any literal values here (e.g. a Default constraint's value) come from the model
        # definition in code, not runtime data, so there's nothing to parameterize.
        return self.to_sql(), []


@dataclass(frozen=True)
class InsertQuery(Generic[TC], SqlQuery[None]):
    row: TC

    def _row_values(self) -> List[Any]:
        values: List[Any] = []
        for prop in self.row.__class__.properties().values():
            if isinstance(prop, Prop):
                values.append(prop.get_val(self.row))
            elif isinstance(prop, PropOpt):
                values.append(prop.get_val(self.row))
        return values

    def to_sql(self) -> str:
        values_sql = ', '.join(_sql_literal(v) for v in self._row_values())
        return f'INSERT INTO {self.row.__class__.__name__.lower()} VALUES ({values_sql});'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        values = self._row_values()
        placeholders = ', '.join(['%s'] * len(values))
        return f'INSERT INTO {self.row.__class__.__name__.lower()} VALUES ({placeholders});', values

@dataclass(frozen=True)
class UpdateQuery(Generic[TC], SqlQuery[None]):
    _model: Type[TC]
    _values: List[Param[TC, Any]]
    _where: Constraint[TC] | None = None

    def where(self, constraint: Constraint[TC]) -> 'UpdateQuery[TC]':
        return UpdateQuery(self._model, self._values, constraint)

    def to_sql(self) -> str:
        assert len(self._values) > 0, 'You must set at least one value'
        assignments = ', '.join(f'{p.label} = {_sql_literal(p.value)}' for p in self._values)
        where_clause = '' if self._where is None else (' WHERE ' + self._where.to_sql())
        return f'UPDATE {self._model.__name__.lower()} SET {assignments}{where_clause};'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        assert len(self._values) > 0, 'You must set at least one value'
        assignments = ', '.join(f'{p.label} = %s' for p in self._values)
        params: List[Any] = [p.value for p in self._values]
        if self._where is None:
            return f'UPDATE {self._model.__name__.lower()} SET {assignments};', params
        where_clause, where_params = self._where.to_sql_params()
        return f'UPDATE {self._model.__name__.lower()} SET {assignments} WHERE {where_clause};', params + where_params

@dataclass(frozen=True)
class DeleteQuery(Generic[TC], SqlQuery[None]):
    _model: Type[TC]
    _where: Constraint[TC] | None = None

    def where(self, constraint: Constraint[TC]) -> 'DeleteQuery[TC]':
        return DeleteQuery(self._model, constraint)

    def to_sql(self) -> str:
        where_clause = '' if self._where is None else (' WHERE ' + self._where.to_sql())
        return f'DELETE FROM {self._model.__name__.lower()}{where_clause};'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        if self._where is None:
            return f'DELETE FROM {self._model.__name__.lower()};', []
        where_clause, params = self._where.to_sql_params()
        return f'DELETE FROM {self._model.__name__.lower()} WHERE {where_clause};', params


# --- 2-4 tables: JoinQueryN (builder) -> QueryN (terminal) ---
# Each join step keeps its own JoinType and on-constraints (of the arity active when that table was
# added), since a chained join can mix LEFT/INNER per step and later ON clauses may reference any
# previously joined table. Joining stops at 4 tables; beyond that, compose queries by hand.

@dataclass(frozen=True)
class JoinQuery2(Generic[TC, TC1]):
    table1: Type[TC]
    table2: Type[TC1]
    join_type_2: JoinType
    on_2: Constraint2[TC, TC1] | None
    _selection: Sequence[PropSelect[TC, Any] | PropSelect[TC1, Any]] | None = None

    def select(self, sel: PropSelect[TC, Any] | PropSelect[TC1, Any], *sels: PropSelect[TC, Any] | PropSelect[TC1, Any]) -> 'JoinQuery2[TC, TC1]':
        return JoinQuery2(self.table1, self.table2, self.join_type_2, self.on_2, [sel, *sels])

    def select_more(self, sel: PropSelect[TC, Any] | PropSelect[TC1, Any], *sels: PropSelect[TC, Any] | PropSelect[TC1, Any]) -> 'JoinQuery2[TC, TC1]':
        return JoinQuery2(self.table1, self.table2, self.join_type_2, self.on_2, [*(self._selection or []), sel, *sels])

    def join_inner(self, next: Type[TC2], on: Constraint3[TC, TC1, TC2] | None = None) -> 'JoinQuery3[TC, TC1, TC2]':
        return JoinQuery3(self.table1, self.table2, next, self.join_type_2, self.on_2, JoinType.Inner, on, self._selection)

    def join_left(self, next: Type[TC2], on: Constraint3[TC, TC1, TC2] | None = None) -> 'JoinQuery3[TC, TC1, TC2]':
        return JoinQuery3(self.table1, self.table2, next, self.join_type_2, self.on_2, JoinType.Left, on, self._selection)

    def where(self, constraint: Constraint2[TC, TC1] | None = None) -> 'Query2[TC, TC1]':
        return Query2(self.table1, self.table2, self.join_type_2, self.on_2, _resolve_selection(self._selection, self.table1, self.table2), constraint)

@dataclass(frozen=True)
class Query2(Generic[TC, TC1], SqlQuery[Tuple[PartialModel[TC], PartialModel[TC1]]]):
    table1: Type[TC]
    table2: Type[TC1]
    join_type_2: JoinType
    on_2: Constraint2[TC, TC1] | None
    _selection: Sequence[PropSelect[TC, Any] | PropSelect[TC1, Any]]
    _where: Constraint2[TC, TC1] | None = None

    def select(self, sel: PropSelect[TC, Any] | PropSelect[TC1, Any], *sels: PropSelect[TC, Any] | PropSelect[TC1, Any]) -> 'Query2[TC, TC1]':
        return Query2(self.table1, self.table2, self.join_type_2, self.on_2, [sel, *sels], self._where)

    def select_more(self, sel: PropSelect[TC, Any] | PropSelect[TC1, Any], *sels: PropSelect[TC, Any] | PropSelect[TC1, Any]) -> 'Query2[TC, TC1]':
        return Query2(self.table1, self.table2, self.join_type_2, self.on_2, [*self._selection, sel, *sels], self._where)

    def where(self, constraint: Constraint2[TC, TC1] | None = None) -> 'Query2[TC, TC1]':
        return Query2(self.table1, self.table2, self.join_type_2, self.on_2, self._selection, constraint)

    def to_sql(self) -> str:
        assert len(self._selection) > 0, 'You must select at least one column'
        assert self.on_2 is not None, 'You must specify a join condition for join 2'

        selections = ', '.join(_qualified_label(p) for p in self._selection)
        where_clause = '' if self._where is None else ' WHERE ' + self._where.to_sql()

        from_clause = f'{self.table1.__name__.lower()}'
        on_2_clause = self.on_2.to_sql()
        from_clause += f' {self.join_type_2.value} JOIN {self.table2.__name__.lower()} ON {on_2_clause}'

        return f'SELECT {selections} FROM {from_clause}{where_clause};'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        assert len(self._selection) > 0, 'You must select at least one column'
        assert self.on_2 is not None, 'You must specify a join condition for join 2'

        selections = ', '.join(_qualified_label(p) for p in self._selection)
        params: List[Any] = []

        on_2_clause, on_2_params = self.on_2.to_sql_params()
        params += on_2_params
        from_clause = f'{self.table1.__name__.lower()} {self.join_type_2.value} JOIN {self.table2.__name__.lower()} ON {on_2_clause}'

        if self._where is None:
            return f'SELECT {selections} FROM {from_clause};', params
        where_clause, where_params = self._where.to_sql_params()
        params += where_params
        return f'SELECT {selections} FROM {from_clause} WHERE {where_clause};', params

@dataclass(frozen=True)
class JoinQuery3(Generic[TC, TC1, TC2]):
    table1: Type[TC]
    table2: Type[TC1]
    table3: Type[TC2]
    join_type_2: JoinType
    on_2: Constraint2[TC, TC1] | None
    join_type_3: JoinType
    on_3: Constraint3[TC, TC1, TC2] | None
    _selection: Sequence[PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any]] | None = None

    def select(self, sel: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any], *sels: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any]) -> 'JoinQuery3[TC, TC1, TC2]':
        return JoinQuery3(self.table1, self.table2, self.table3, self.join_type_2, self.on_2, self.join_type_3, self.on_3, [sel, *sels])

    def select_more(self, sel: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any], *sels: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any]) -> 'JoinQuery3[TC, TC1, TC2]':
        return JoinQuery3(self.table1, self.table2, self.table3, self.join_type_2, self.on_2, self.join_type_3, self.on_3, [*(self._selection or []), sel, *sels])

    def join_inner(self, next: Type[TC3], on: Constraint4[TC, TC1, TC2, TC3] | None = None) -> 'JoinQuery4[TC, TC1, TC2, TC3]':
        return JoinQuery4(self.table1, self.table2, self.table3, next, self.join_type_2, self.on_2, self.join_type_3, self.on_3, JoinType.Inner, on, self._selection)

    def join_left(self, next: Type[TC3], on: Constraint4[TC, TC1, TC2, TC3] | None = None) -> 'JoinQuery4[TC, TC1, TC2, TC3]':
        return JoinQuery4(self.table1, self.table2, self.table3, next, self.join_type_2, self.on_2, self.join_type_3, self.on_3, JoinType.Left, on, self._selection)

    def where(self, constraint: Constraint3[TC, TC1, TC2] | None = None) -> 'Query3[TC, TC1, TC2]':
        return Query3(self.table1, self.table2, self.table3, self.join_type_2, self.on_2, self.join_type_3, self.on_3, _resolve_selection(self._selection, self.table1, self.table2, self.table3), constraint)

@dataclass(frozen=True)
class Query3(Generic[TC, TC1, TC2], SqlQuery[Tuple[PartialModel[TC], PartialModel[TC1], PartialModel[TC2]]]):
    table1: Type[TC]
    table2: Type[TC1]
    table3: Type[TC2]
    join_type_2: JoinType
    on_2: Constraint2[TC, TC1] | None
    join_type_3: JoinType
    on_3: Constraint3[TC, TC1, TC2] | None
    _selection: Sequence[PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any]]
    _where: Constraint3[TC, TC1, TC2] | None = None

    def select(self, sel: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any], *sels: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any]) -> 'Query3[TC, TC1, TC2]':
        return Query3(self.table1, self.table2, self.table3, self.join_type_2, self.on_2, self.join_type_3, self.on_3, [sel, *sels], self._where)

    def select_more(self, sel: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any], *sels: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any]) -> 'Query3[TC, TC1, TC2]':
        return Query3(self.table1, self.table2, self.table3, self.join_type_2, self.on_2, self.join_type_3, self.on_3, [*self._selection, sel, *sels], self._where)

    def where(self, constraint: Constraint3[TC, TC1, TC2] | None = None) -> 'Query3[TC, TC1, TC2]':
        return Query3(self.table1, self.table2, self.table3, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self._selection, constraint)

    def to_sql(self) -> str:
        assert len(self._selection) > 0, 'You must select at least one column'
        assert self.on_2 is not None, 'You must specify a join condition for join 2'
        assert self.on_3 is not None, 'You must specify a join condition for join 3'

        selections = ', '.join(_qualified_label(p) for p in self._selection)
        where_clause = '' if self._where is None else ' WHERE ' + self._where.to_sql()

        from_clause = f'{self.table1.__name__.lower()}'
        on_2_clause = self.on_2.to_sql()
        from_clause += f' {self.join_type_2.value} JOIN {self.table2.__name__.lower()} ON {on_2_clause}'
        on_3_clause = self.on_3.to_sql()
        from_clause += f' {self.join_type_3.value} JOIN {self.table3.__name__.lower()} ON {on_3_clause}'

        return f'SELECT {selections} FROM {from_clause}{where_clause};'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        assert len(self._selection) > 0, 'You must select at least one column'
        assert self.on_2 is not None, 'You must specify a join condition for join 2'
        assert self.on_3 is not None, 'You must specify a join condition for join 3'

        selections = ', '.join(_qualified_label(p) for p in self._selection)
        params: List[Any] = []

        on_2_clause, on_2_params = self.on_2.to_sql_params()
        params += on_2_params
        from_clause = f'{self.table1.__name__.lower()} {self.join_type_2.value} JOIN {self.table2.__name__.lower()} ON {on_2_clause}'
        on_3_clause, on_3_params = self.on_3.to_sql_params()
        params += on_3_params
        from_clause += f' {self.join_type_3.value} JOIN {self.table3.__name__.lower()} ON {on_3_clause}'

        if self._where is None:
            return f'SELECT {selections} FROM {from_clause};', params
        where_clause, where_params = self._where.to_sql_params()
        params += where_params
        return f'SELECT {selections} FROM {from_clause} WHERE {where_clause};', params

@dataclass(frozen=True)
class JoinQuery4(Generic[TC, TC1, TC2, TC3]):
    table1: Type[TC]
    table2: Type[TC1]
    table3: Type[TC2]
    table4: Type[TC3]
    join_type_2: JoinType
    on_2: Constraint2[TC, TC1] | None
    join_type_3: JoinType
    on_3: Constraint3[TC, TC1, TC2] | None
    join_type_4: JoinType
    on_4: Constraint4[TC, TC1, TC2, TC3] | None
    _selection: Sequence[PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any] | PropSelect[TC3, Any]] | None = None

    def select(self, sel: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any] | PropSelect[TC3, Any], *sels: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any] | PropSelect[TC3, Any]) -> 'JoinQuery4[TC, TC1, TC2, TC3]':
        return JoinQuery4(self.table1, self.table2, self.table3, self.table4, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self.join_type_4, self.on_4, [sel, *sels])

    def select_more(self, sel: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any] | PropSelect[TC3, Any], *sels: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any] | PropSelect[TC3, Any]) -> 'JoinQuery4[TC, TC1, TC2, TC3]':
        return JoinQuery4(self.table1, self.table2, self.table3, self.table4, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self.join_type_4, self.on_4, [*(self._selection or []), sel, *sels])

    def where(self, constraint: Constraint4[TC, TC1, TC2, TC3] | None = None) -> 'Query4[TC, TC1, TC2, TC3]':
        return Query4(self.table1, self.table2, self.table3, self.table4, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self.join_type_4, self.on_4, _resolve_selection(self._selection, self.table1, self.table2, self.table3, self.table4), constraint)

@dataclass(frozen=True)
class Query4(Generic[TC, TC1, TC2, TC3], SqlQuery[Tuple[PartialModel[TC], PartialModel[TC1], PartialModel[TC2], PartialModel[TC3]]]):
    table1: Type[TC]
    table2: Type[TC1]
    table3: Type[TC2]
    table4: Type[TC3]
    join_type_2: JoinType
    on_2: Constraint2[TC, TC1] | None
    join_type_3: JoinType
    on_3: Constraint3[TC, TC1, TC2] | None
    join_type_4: JoinType
    on_4: Constraint4[TC, TC1, TC2, TC3] | None
    _selection: Sequence[PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any] | PropSelect[TC3, Any]]
    _where: Constraint4[TC, TC1, TC2, TC3] | None = None

    def select(self, sel: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any] | PropSelect[TC3, Any], *sels: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any] | PropSelect[TC3, Any]) -> 'Query4[TC, TC1, TC2, TC3]':
        return Query4(self.table1, self.table2, self.table3, self.table4, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self.join_type_4, self.on_4, [sel, *sels], self._where)

    def select_more(self, sel: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any] | PropSelect[TC3, Any], *sels: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any] | PropSelect[TC3, Any]) -> 'Query4[TC, TC1, TC2, TC3]':
        return Query4(self.table1, self.table2, self.table3, self.table4, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self.join_type_4, self.on_4, [*self._selection, sel, *sels], self._where)

    def where(self, constraint: Constraint4[TC, TC1, TC2, TC3] | None = None) -> 'Query4[TC, TC1, TC2, TC3]':
        return Query4(self.table1, self.table2, self.table3, self.table4, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self.join_type_4, self.on_4, self._selection, constraint)

    def to_sql(self) -> str:
        assert len(self._selection) > 0, 'You must select at least one column'
        assert self.on_2 is not None, 'You must specify a join condition for join 2'
        assert self.on_3 is not None, 'You must specify a join condition for join 3'
        assert self.on_4 is not None, 'You must specify a join condition for join 4'

        selections = ', '.join(_qualified_label(p) for p in self._selection)
        where_clause = '' if self._where is None else ' WHERE ' + self._where.to_sql()

        from_clause = f'{self.table1.__name__.lower()}'
        on_2_clause = self.on_2.to_sql()
        from_clause += f' {self.join_type_2.value} JOIN {self.table2.__name__.lower()} ON {on_2_clause}'
        on_3_clause = self.on_3.to_sql()
        from_clause += f' {self.join_type_3.value} JOIN {self.table3.__name__.lower()} ON {on_3_clause}'
        on_4_clause = self.on_4.to_sql()
        from_clause += f' {self.join_type_4.value} JOIN {self.table4.__name__.lower()} ON {on_4_clause}'

        return f'SELECT {selections} FROM {from_clause}{where_clause};'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        assert len(self._selection) > 0, 'You must select at least one column'
        assert self.on_2 is not None, 'You must specify a join condition for join 2'
        assert self.on_3 is not None, 'You must specify a join condition for join 3'
        assert self.on_4 is not None, 'You must specify a join condition for join 4'

        selections = ', '.join(_qualified_label(p) for p in self._selection)
        params: List[Any] = []

        on_2_clause, on_2_params = self.on_2.to_sql_params()
        params += on_2_params
        from_clause = f'{self.table1.__name__.lower()} {self.join_type_2.value} JOIN {self.table2.__name__.lower()} ON {on_2_clause}'
        on_3_clause, on_3_params = self.on_3.to_sql_params()
        params += on_3_params
        from_clause += f' {self.join_type_3.value} JOIN {self.table3.__name__.lower()} ON {on_3_clause}'
        on_4_clause, on_4_params = self.on_4.to_sql_params()
        params += on_4_params
        from_clause += f' {self.join_type_4.value} JOIN {self.table4.__name__.lower()} ON {on_4_clause}'

        if self._where is None:
            return f'SELECT {selections} FROM {from_clause};', params
        where_clause, where_params = self._where.to_sql_params()
        params += where_params
        return f'SELECT {selections} FROM {from_clause} WHERE {where_clause};', params
