
from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, List, Tuple, Type, TypeVar, cast
from pydoptic import PartialModel
from pydoptic.selector import PropSelect, Prop, PropOpt, Param
from pydoptic_sql.sql_constraint import A, TC, TC1, Constraint, Constraint2, _qualified_label
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
        raise NotImplementedError()

    @classmethod
    def select(cls, sel: PropSelect[TC, Any], *sels: PropSelect[TC, Any]) -> 'Query[TC]':
        return Query(sel.origin, [sel, *sels], None)

    @classmethod
    def join_left(cls, table1: Type[TC], table2: Type[TC1]) -> 'Query2[TC, TC1]':
        return Query2(JoinType.Left, table1, table2)

    @classmethod
    def join_inner(cls, table1: Type[TC], table2: Type[TC1]) -> 'Query2[TC, TC1]':
        return Query2(JoinType.Inner, table1, table2)

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


@dataclass(frozen=True)
class Query(Generic[TC], SqlQuery[PartialModel[TC]]):
    _model: Type[TC]
    _selection: List[PropSelect[TC, Any]]
    _where: Constraint[TC] | None = None

    def where(self, constraint: Constraint[TC]) -> 'Query[TC]':
        return Query(self._model, self._selection, constraint)

    def to_sql(self) -> str:
        assert len(self._selection) > 0, 'You must select a value'
        selections = ', '.join(p.label for p in self._selection)
        table_name: str = self._selection[0].origin.__name__.lower()
        where_clause = '' if self._where is None else (' WHERE ' + self._where.to_sql())
        return f'SELECT {selections} FROM {table_name}{where_clause};'

@dataclass
class DropQuery(Generic[TC], SqlQuery[None]):
    _model: Type[TC]

    def to_sql(self) -> str:
        return f'DROP TABLE {self._model.__name__.lower()};'

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


@dataclass(frozen=True)
class InsertQuery(Generic[TC], SqlQuery[None]):
    row: TC

    def to_sql(self) -> str:
        values: List[Any] = []
        for prop in self.row.__class__.properties().values():
            if isinstance(prop, Prop):
                values.append(prop.get_val(self.row))
            elif isinstance(prop, PropOpt):
                values.append(prop.get_val(self.row))
        values_sql = ', '.join(_sql_literal(v) for v in values)
        return f'INSERT INTO {self.row.__class__.__name__.lower()} VALUES ({values_sql});'

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

@dataclass(frozen=True)
class DeleteQuery(Generic[TC], SqlQuery[None]):
    _model: Type[TC]
    _where: Constraint[TC] | None = None

    def where(self, constraint: Constraint[TC]) -> 'DeleteQuery[TC]':
        return DeleteQuery(self._model, constraint)

    def to_sql(self) -> str:
        where_clause = '' if self._where is None else (' WHERE ' + self._where.to_sql())
        return f'DELETE FROM {self._model.__name__.lower()}{where_clause};'

class JoinType(Enum):
    Left = 'LEFT'
    Inner = 'INNER'

@dataclass(frozen=True)
class Query2(Generic[TC, TC1], SqlQuery[Tuple[PartialModel[TC], PartialModel[TC1]]]):
    join_type: JoinType
    table1: Type[TC]
    table2: Type[TC1]

    _selection: List[PropSelect[TC, Any] | PropSelect[TC1, Any]] | None = None
    _where: Constraint2[TC, TC1] | None = None
    _on_left: PropSelect[TC, Any] | None = None
    _on_right: PropSelect[TC1, Any] | None = None

    def columns(self, sel: PropSelect[TC, Any] | PropSelect[TC1, Any], *sels: PropSelect[TC, Any] | PropSelect[TC1, Any]) -> 'Query2[TC, TC1]':
        return Query2(self.join_type, self.table1, self.table2, [sel, *sels], self._where, self._on_left, self._on_right)

    def on(self, left: PropSelect[TC, A], right: PropSelect[TC1, A]) -> 'Query2[TC, TC1]':
        return Query2(self.join_type, self.table1, self.table2, self._selection, self._where, left, right)

    def where(self, constraint: Constraint2[TC, TC1]) -> 'Query2[TC, TC1]':
        return Query2(self.join_type, self.table1, self.table2, self._selection, constraint, self._on_left, self._on_right)

    def to_sql(self) -> str:
        assert self._selection is not None and len(self._selection) > 0, 'You must select a value'
        assert self._on_left is not None and self._on_right is not None, 'You must specify a join condition with on()'

        selections = ', '.join(_qualified_label(p) for p in self._selection)
        table1_name = self.table1.__name__.lower()
        table2_name = self.table2.__name__.lower()
        on_clause = f'{_qualified_label(self._on_left)} = {_qualified_label(self._on_right)}'
        where_clause = '' if self._where is None else ' WHERE ' + self._where.to_sql()

        return (
            f'SELECT {selections} FROM {table1_name} {self.join_type.value} JOIN {table2_name} '
            f'ON {on_clause}{where_clause};'
        )
