
from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, List, Sequence, Type, TypeVar, cast
from pydoptic import PartialModel
from pydoptic.selector import PropSelect, Prop, PropOpt, Param
from pydoptic_sql import SqlTable
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

A = TypeVar('A')
R = TypeVar('R')
TC = TypeVar('TC', bound=SqlTable, contravariant=True)
TC1 = TypeVar('TC1', bound=SqlTable, contravariant=True)

class SqlQuery(Generic[R]):
    # R is the result type of executing the query (e.g. PartialModel[TC], or None); table type(s) are tracked separately per subclass.
    def to_sql(self) -> str:
        raise NotImplementedError()
    
    @classmethod
    def select(cls, sel: PropSelect[TC, Any], *sels: PropSelect[TC, Any]) -> 'SelectQuery[TC]':
        return SelectQuery(sel.origin, [sel, *sels], None)
    
    # @classmethod
    # def join_left(cls, table: TC1) -> 'JoinQuery'[TC, TC1]:
    #     return JoinQuery(JoinType.Left, table)
    
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


class Constraint(Generic[TC]):
    def to_sql(self) -> str:
        raise NotImplementedError()

    @classmethod
    def any(cls, *constraints: 'Constraint[TC]') -> 'OrConstraint[TC]':
        return OrConstraint(list(constraints))
    
    @classmethod
    def all(cls, *constraints: 'Constraint[TC]') -> 'AndConstraint[TC]':
        return AndConstraint(list(constraints))
    
    @classmethod
    def eq(cls, prop: Prop[TC, A] | PropOpt[TC, A], other: Prop[TC, A] | PropOpt[TC, A] | A) -> 'CompConstraint[TC, A]':
        return CompConstraint(prop, other, Comparison.EQ)
    
    @classmethod
    def gt(cls, prop: Prop[TC, A] | PropOpt[TC, A], other: Prop[TC, A] | PropOpt[TC, A] | A) -> 'CompConstraint[TC, A]':
        return CompConstraint(prop, other, Comparison.GT)
    
    @classmethod
    def gte(cls, prop: Prop[TC, A] | PropOpt[TC, A], other: Prop[TC, A] | PropOpt[TC, A] | A) -> 'CompConstraint[TC, A]':
        return CompConstraint(prop, other, Comparison.GTE)
    
    @classmethod
    def lt(cls, prop: Prop[TC, A] | PropOpt[TC, A], other: Prop[TC, A] | PropOpt[TC, A] | A) -> 'CompConstraint[TC, A]':
        return CompConstraint(prop, other, Comparison.LT)
    
    @classmethod
    def lte(cls, prop: Prop[TC, A] | PropOpt[TC, A], other: Prop[TC, A] | PropOpt[TC, A] | A) -> 'CompConstraint[TC, A]':
        return CompConstraint(prop, other, Comparison.LTE)
    
    @classmethod
    def ne(cls, prop: Prop[TC, A] | PropOpt[TC, A], other: Prop[TC, A] | PropOpt[TC, A] | A) -> 'CompConstraint[TC, A]':
        return CompConstraint(prop, other, Comparison.NE)
    
    @classmethod
    def like(cls, prop: Prop[TC, A] | PropOpt[TC, A], other: Prop[TC, A] | PropOpt[TC, A] | A) -> 'CompConstraint[TC, A]':
        return CompConstraint(prop, other, Comparison.LIKE)

    @classmethod
    def between(cls, prop: Prop[TC, A] | PropOpt[TC, A], lower: Prop[TC, A] | PropOpt[TC, A] | A, upper: Prop[TC, A] | PropOpt[TC, A] | A) -> 'BetweenConstraint[TC, A]':
        return BetweenConstraint(prop, lower, upper)

    @classmethod
    def in_(cls, prop: Prop[TC, A] | PropOpt[TC, A], values: Sequence[Prop[TC, A] | PropOpt[TC, A] | A]) -> 'InConstraint[TC, A]':
        return InConstraint(prop, values)

    def AND(self, other: 'Constraint[TC]') -> 'AndConstraint[TC]':
        return AndConstraint([self, other])

    def OR(self, other: 'Constraint[TC]') -> 'OrConstraint[TC]':
        return OrConstraint([self, other])
    
    @property
    def NOT(self) -> 'NotConstraint[TC]':
        return NotConstraint(self)

@dataclass(frozen=True)
class OrConstraint(Constraint[TC]):
    constraints: List[Constraint[TC]]

    def to_sql(self) -> str:
        return '(' + ' OR '.join(c.to_sql() for c in self.constraints) + ')'

@dataclass(frozen=True)
class AndConstraint(Constraint[TC]):
    constraints: List[Constraint[TC]]

    def to_sql(self) -> str:
        return '(' + ' AND '.join(c.to_sql() for c in self.constraints) + ')'

@dataclass(frozen=True)
class NotConstraint(Constraint[TC]):
    constraint: Constraint[TC]

    def to_sql(self) -> str:
        return 'NOT (' + self.constraint.to_sql() + ')'

class Comparison(Enum):
    EQ = 1
    GT = 2
    GTE = 3
    LT = 4
    LTE = 5
    NE = 6
    LIKE = 7

@dataclass(frozen=True)
class CompConstraint(Generic[TC, A], Constraint[TC]):
    value_1: Prop[TC, A] | PropOpt[TC, A]
    value_2: Prop[TC, A] | PropOpt[TC, A] | A
    comp: Comparison

    def to_sql(self) -> str:
        comp_str: str = ''
        match self.comp:
            case Comparison.EQ:
                comp_str = '='
            case Comparison.LT:
                comp_str = '<'
            case Comparison.LTE:
                comp_str = '<='
            case Comparison.GT:
                comp_str = '>'
            case Comparison.GTE:
                comp_str = '>='
            case Comparison.LIKE:
                comp_str = 'LIKE'
            case Comparison.NE:
                comp_str = '<>'
                
        value_2 = self.value_2.label if isinstance(self.value_2, PropSelect) else str(self.value_2)
        if self.value_1.target is str and not isinstance(self.value_2, PropSelect):
            value_2 = "'" + value_2 + "'"
        return self.value_1.label + ' ' + comp_str + ' ' + value_2

@dataclass(frozen=True)
class BetweenConstraint(Generic[TC, A], Constraint[TC]):
    value: Prop[TC, A] | PropOpt[TC, A]
    lower: Prop[TC, A] | PropOpt[TC, A] | A
    upper: Prop[TC, A] | PropOpt[TC, A] | A

    def to_sql(self) -> str:
        if isinstance(self.lower, PropSelect):
            lower = self.lower.label 
        else:
            lower = str(self.lower)
        if isinstance(self.upper, PropSelect):
            upper = self.upper.label 
        else:
            upper = str(self.upper)
        return f'{self.value.label} BETWEEN {lower} AND {upper}'

@dataclass(frozen=True)
class InConstraint(Generic[TC, A], Constraint[TC]):
    value: Prop[TC, A] | PropOpt[TC, A]
    values: Sequence[Prop[TC, A] | PropOpt[TC, A] | A]

    def to_sql(self) -> str:
        def render(c: Prop[TC, A] | PropOpt[TC, A] | A) -> str:
            if isinstance(c, PropSelect):
                return c.label
            value = str(c)
            if self.value.target is str:
                value = "'" + value + "'"
            return value

        values = [render(c) for c in self.values]
        return f'{self.value.label} IN ({", ".join(values)})'

@dataclass(frozen=True)
class SelectQuery(Generic[TC], SqlQuery[PartialModel[TC]]):
    _model: Type[TC]
    _selection: List[PropSelect[TC, Any]]
    _where: Constraint[TC] | None = None

    def where(self, constraint: Constraint[TC]) -> 'SelectQuery[TC]':
        return SelectQuery(self._model, self._selection, constraint)

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
class JoinQuery(Generic[TC, TC1]):
    join_type: JoinType
    table1: Type[TC]
    table2: Type[TC1]

    _selection: List[PropSelect[TC, Any] | PropSelect[TC1, Any]] | None = None
    _where_left: Constraint[TC] | None = None
    _where_right: Constraint[TC1] | None = None
    _on_left: PropSelect[TC, Any] | None = None
    _on_right: PropSelect[TC1, Any] | None = None

    def select(self, sel: PropSelect[TC, Any] | PropSelect[TC1, Any], *sels: PropSelect[TC, Any] | PropSelect[TC1, Any]) -> 'JoinQuery[TC, TC1]':
        return JoinQuery(self.join_type, self.table1, self.table2, [sel, *sels], self._where_left, self._where_right, self._on_left, self._on_right)
    
    def on(self, left: PropSelect[TC, A], right: PropSelect[TC1, A]) -> 'JoinQuery[TC, TC1]':
        return JoinQuery(self.join_type, self.table1, self.table2, self._selection, self._where_left, self._where_right, left, right)
    
    def where_left(self, constraint: Constraint[TC]) -> 'JoinQuery[TC, TC1]':
        return JoinQuery(self.join_type, self.table1, self.table2, self._selection, constraint, self._where_right, self._on_left, self._on_right)
    
    def where_right(self, constraint: Constraint[TC1]) -> 'JoinQuery[TC, TC1]':
        return JoinQuery(self.join_type, self.table1, self.table2, self._selection, self._where_left, constraint, self._on_left, self._on_right)
