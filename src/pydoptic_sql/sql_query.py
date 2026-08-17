
from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, List, Sequence, Tuple, Type, TypeVar, cast
from pydoptic import PartialModel
from pydoptic.selector import PropSelect, Prop, PropOpt, Param
from pydoptic_sql import SqlTable
from pydoptic_sql.sql_constraint import A, TC, TC1, TC2, TC3, Constraint, Constraint2, Constraint3, Constraint4, _qualified_label
from pydoptic_sql.sql_order import Direction, OrderBy
from pydoptic_sql.sql_computed import AggregateFunction, Computed, ComputedResult
from pydoptic_sql.sql_having import HavingConstraint, HavingConstraint2, HavingConstraint3, HavingConstraint4
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
    def from_table(cls, table: Type[TC]) -> 'Query1[TC]':
        return Query1(table)

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

    @classmethod
    def sum(cls, column: Prop[TC, A] | PropOpt[TC, A], alias: str | None = None) -> 'Computed[TC, A]':
        return Computed(column, AggregateFunction.SUM, alias or _default_computed_alias(column, AggregateFunction.SUM), column.target)

    @classmethod
    def avg(cls, column: Prop[TC, Any] | PropOpt[TC, Any], alias: str | None = None) -> 'Computed[TC, float]':
        return Computed(column, AggregateFunction.AVG, alias or _default_computed_alias(column, AggregateFunction.AVG), float)

    @classmethod
    def min(cls, column: Prop[TC, A] | PropOpt[TC, A], alias: str | None = None) -> 'Computed[TC, A]':
        return Computed(column, AggregateFunction.MIN, alias or _default_computed_alias(column, AggregateFunction.MIN), column.target)

    @classmethod
    def max(cls, column: Prop[TC, A] | PropOpt[TC, A], alias: str | None = None) -> 'Computed[TC, A]':
        return Computed(column, AggregateFunction.MAX, alias or _default_computed_alias(column, AggregateFunction.MAX), column.target)

    @classmethod
    def count(cls, table: Type[TC], alias: str | None = None) -> 'Computed[TC, int]':
        return Computed(None, AggregateFunction.COUNT, alias or f'{table.__name__.lower()}_count', int)

    @classmethod
    def count_col(cls, column: Prop[TC, Any] | PropOpt[TC, Any], alias: str | None = None) -> 'Computed[TC, int]':
        return Computed(column, AggregateFunction.COUNT, alias or _default_computed_alias(column, AggregateFunction.COUNT), int)


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

def _order_by_sql(order_by: Sequence[OrderBy[Any]], qualify: bool) -> str:
    """Render an ' ORDER BY ...' clause (leading space included), or '' if there's nothing to order by.
    Qualification (table.column vs. bare column) is decided here by the caller, not by OrderBy itself --
    OrderBy has no arity variants, so it doesn't know which query arity it's being rendered for."""
    if not order_by:
        return ''
    label = _qualified_label if qualify else (lambda p: p.label)
    return ' ORDER BY ' + ', '.join(f'{label(ob.column)} {ob.direction.value}' for ob in order_by)

def _group_by_sql(group_by: Sequence[PropSelect[Any, Any]], qualify: bool) -> str:
    """Render a ' GROUP BY ...' clause (leading space included), or '' if there's nothing to group by.
    Same externalized-qualification approach as _order_by_sql."""
    if not group_by:
        return ''
    label = _qualified_label if qualify else (lambda p: p.label)
    return ' GROUP BY ' + ', '.join(label(p) for p in group_by)

def _default_computed_alias(column: PropSelect[Any, Any], function: AggregateFunction) -> str:
    return f'{column.origin.__name__.lower()}_{column.label}_{function.value.lower()}'

def _computed_sql_parts(computed: Sequence[Computed[Any, Any]], qualify: bool) -> List[str]:
    """Render each computed expression as 'FUNC(col_ref) AS alias' for inclusion in a SELECT list.
    Same externalized-qualification approach as _order_by_sql/_group_by_sql -- Computed has no arity
    variants either, so it doesn't know which query arity it's being rendered for."""
    def render(c: Computed[Any, Any]) -> str:
        col_ref = '*' if c.column is None else (_qualified_label(c.column) if qualify else c.column.label)
        return f'{c.function.value}({col_ref}) AS {c.label}'
    return [render(c) for c in computed]


class JoinType(Enum):
    Left = 'LEFT'
    Inner = 'INNER'


# --- 1-4 tables: QueryN/ComputedQueryN ---
# There used to be a separate "builder" class per arity (SelectQuery/JoinQueryN) that had no
# to_sql()/to_sql_params() of its own -- calling where() was the one-time transition into a "terminal"
# class (QueryN) that did. That split existed because a WHERE/HAVING constraint set before a later
# join_inner()/join_left() couldn't be safely re-typed for the wider arity: ConstraintN/
# HavingConstraintN are distinct, unrelated classes per arity, not one class widened via a union the
# way OrderBy/Computed are.
#
# Constraint.incr_arity()/HavingConstraint.incr_arity() (see sql_constraint.py/sql_having.py) remove
# that obstacle -- a constraint set at arity N can now be safely rewrapped into the arity-(N+1) class,
# with the exact same operands, whenever a join widens the query. So where()/having() no longer need
# to be a special one-time transition: join_inner()/join_left() just carries _where/_having across by
# calling incr_arity() on them when set, and QueryN/ComputedQueryN are directly executable
# (to_sql()/to_sql_params()) at every stage, builder and "terminal" alike -- hence one class per arity
# instead of two. select_computed(_more) still splits off into a separate ComputedQueryN from QueryN,
# since the result type R differs (PartialModel[...] vs Tuple[..., ComputedResult]) and R can't vary
# at runtime for a single dataclass.
#
# _order_by/_group_by/_computed still widen by one union member per table added (rather than gaining
# an arity variant the way Constraint/HavingConstraint do), since none of OrderBy/Computed/a plain
# group-by column ever references more than one table at a time -- an entry set before a join stays
# exactly as valid after it, with no re-wrapping needed.

@dataclass(frozen=True)
class Query1(Generic[TC], SqlQuery[PartialModel[TC]]):
    table1: Type[TC]
    _selection: Sequence[PropSelect[TC, Any]] | None = None
    _where: Constraint[TC] | None = None
    _order_by: Sequence[OrderBy[TC]] = ()
    _group_by: Sequence[PropSelect[TC, Any]] = ()

    def select(self, sel: PropSelect[TC, Any], *sels: PropSelect[TC, Any]) -> 'Query1[TC]':
        return Query1(self.table1, [sel, *sels], self._where, self._order_by, self._group_by)

    def select_more(self, sel: PropSelect[TC, Any], *sels: PropSelect[TC, Any]) -> 'Query1[TC]':
        return Query1(self.table1, [*(self._selection or []), sel, *sels], self._where, self._order_by, self._group_by)

    def select_computed(self, computed: Computed[TC, Any], *more: Computed[TC, Any]) -> 'ComputedQuery1[TC]':
        return ComputedQuery1(self.table1, self._selection, self._where, self._order_by, self._group_by, [computed, *more])

    def select_computed_more(self, computed: Computed[TC, Any], *more: Computed[TC, Any]) -> 'ComputedQuery1[TC]':
        return ComputedQuery1(self.table1, self._selection, self._where, self._order_by, self._group_by, [computed, *more])

    def order_by(self, *order_by: OrderBy[TC]) -> 'Query1[TC]':
        return Query1(self.table1, self._selection, self._where, list(order_by), self._group_by)

    def order_by_more(self, column: Prop[TC, Any] | PropOpt[TC, Any], direction: Direction = Direction.ASC) -> 'Query1[TC]':
        return Query1(self.table1, self._selection, self._where, [*self._order_by, OrderBy(column, direction)], self._group_by)

    def group_by(self, *group_by: PropSelect[TC, Any]) -> 'Query1[TC]':
        return Query1(self.table1, self._selection, self._where, self._order_by, list(group_by))

    def group_by_more(self, col: PropSelect[TC, Any], *cols: PropSelect[TC, Any]) -> 'Query1[TC]':
        return Query1(self.table1, self._selection, self._where, self._order_by, [*self._group_by, col, *cols])

    def join_inner(self, next: Type[TC1], on: Constraint2[TC, TC1] | None = None) -> 'Query2[TC, TC1]':
        return Query2(self.table1, next, JoinType.Inner, on, self._selection, None if self._where is None else self._where.incr_arity(), self._order_by, self._group_by)

    def join_left(self, next: Type[TC1], on: Constraint2[TC, TC1] | None = None) -> 'Query2[TC, TC1]':
        return Query2(self.table1, next, JoinType.Left, on, self._selection, None if self._where is None else self._where.incr_arity(), self._order_by, self._group_by)

    def where(self, constraint: Constraint[TC] | None = None) -> 'Query1[TC]':
        return Query1(self.table1, self._selection, constraint, self._order_by, self._group_by)

    def where_and(self, constraint: Constraint[TC]) -> 'Query1[TC]':
        return self.where(constraint if self._where is None else self._where.AND(constraint))

    def where_or(self, constraint: Constraint[TC]) -> 'Query1[TC]':
        return self.where(constraint if self._where is None else self._where.OR(constraint))

    def _resolved_selection(self) -> List[PropSelect[Any, Any]]:
        return _resolve_selection(self._selection, self.table1)

    def to_sql(self) -> str:
        selection = self._resolved_selection()
        assert len(selection) > 0, 'You must select at least one column'
        selections = ', '.join(p.label for p in selection)
        where_clause = '' if self._where is None else (' WHERE ' + self._where.to_sql())
        group_by_clause = _group_by_sql(self._group_by, qualify=False)
        order_by_clause = _order_by_sql(self._order_by, qualify=False)
        return f'SELECT {selections} FROM {self.table1.__name__.lower()}{where_clause}{group_by_clause}{order_by_clause};'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        selection = self._resolved_selection()
        assert len(selection) > 0, 'You must select at least one column'
        selections = ', '.join(p.label for p in selection)
        group_by_clause = _group_by_sql(self._group_by, qualify=False)
        order_by_clause = _order_by_sql(self._order_by, qualify=False)
        if self._where is None:
            return f'SELECT {selections} FROM {self.table1.__name__.lower()}{group_by_clause}{order_by_clause};', []
        where_clause, params = self._where.to_sql_params()
        return f'SELECT {selections} FROM {self.table1.__name__.lower()} WHERE {where_clause}{group_by_clause}{order_by_clause};', params

@dataclass(frozen=True)
class ComputedQuery1(Generic[TC], SqlQuery[Tuple[PartialModel[TC], ComputedResult]]):
    table1: Type[TC]
    _selection: Sequence[PropSelect[TC, Any]] | None = None
    _where: Constraint[TC] | None = None
    _order_by: Sequence[OrderBy[TC]] = ()
    _group_by: Sequence[PropSelect[TC, Any]] = ()
    _computed: Sequence[Computed[TC, Any]] = ()
    _having: HavingConstraint[TC] | None = None

    def select(self, sel: PropSelect[TC, Any], *sels: PropSelect[TC, Any]) -> 'ComputedQuery1[TC]':
        return ComputedQuery1(self.table1, [sel, *sels], self._where, self._order_by, self._group_by, self._computed, self._having)

    def select_more(self, sel: PropSelect[TC, Any], *sels: PropSelect[TC, Any]) -> 'ComputedQuery1[TC]':
        return ComputedQuery1(self.table1, [*(self._selection or []), sel, *sels], self._where, self._order_by, self._group_by, self._computed, self._having)

    def select_computed(self, computed: Computed[TC, Any], *more: Computed[TC, Any]) -> 'ComputedQuery1[TC]':
        return ComputedQuery1(self.table1, self._selection, self._where, self._order_by, self._group_by, [computed, *more], self._having)

    def select_computed_more(self, computed: Computed[TC, Any], *more: Computed[TC, Any]) -> 'ComputedQuery1[TC]':
        return ComputedQuery1(self.table1, self._selection, self._where, self._order_by, self._group_by, [*self._computed, computed, *more], self._having)

    def order_by(self, *order_by: OrderBy[TC]) -> 'ComputedQuery1[TC]':
        return ComputedQuery1(self.table1, self._selection, self._where, list(order_by), self._group_by, self._computed, self._having)

    def order_by_more(self, column: Prop[TC, Any] | PropOpt[TC, Any], direction: Direction = Direction.ASC) -> 'ComputedQuery1[TC]':
        return ComputedQuery1(self.table1, self._selection, self._where, [*self._order_by, OrderBy(column, direction)], self._group_by, self._computed, self._having)

    def group_by(self, *group_by: PropSelect[TC, Any]) -> 'ComputedQuery1[TC]':
        return ComputedQuery1(self.table1, self._selection, self._where, self._order_by, list(group_by), self._computed, self._having)

    def group_by_more(self, col: PropSelect[TC, Any], *cols: PropSelect[TC, Any]) -> 'ComputedQuery1[TC]':
        return ComputedQuery1(self.table1, self._selection, self._where, self._order_by, [*self._group_by, col, *cols], self._computed, self._having)

    def having(self, constraint: HavingConstraint[TC] | None = None) -> 'ComputedQuery1[TC]':
        return ComputedQuery1(self.table1, self._selection, self._where, self._order_by, self._group_by, self._computed, constraint)

    def having_and(self, constraint: HavingConstraint[TC]) -> 'ComputedQuery1[TC]':
        return self.having(constraint if self._having is None else self._having.AND(constraint))

    def having_or(self, constraint: HavingConstraint[TC]) -> 'ComputedQuery1[TC]':
        return self.having(constraint if self._having is None else self._having.OR(constraint))

    def where(self, constraint: Constraint[TC] | None = None) -> 'ComputedQuery1[TC]':
        return ComputedQuery1(self.table1, self._selection, constraint, self._order_by, self._group_by, self._computed, self._having)

    def where_and(self, constraint: Constraint[TC]) -> 'ComputedQuery1[TC]':
        return self.where(constraint if self._where is None else self._where.AND(constraint))

    def where_or(self, constraint: Constraint[TC]) -> 'ComputedQuery1[TC]':
        return self.where(constraint if self._where is None else self._where.OR(constraint))

    def join_inner(self, next: Type[TC1], on: Constraint2[TC, TC1] | None = None) -> 'ComputedQuery2[TC, TC1]':
        return ComputedQuery2(
            self.table1, next, JoinType.Inner, on,
            self._selection, None if self._where is None else self._where.incr_arity(),
            self._order_by, self._group_by, self._computed,
            None if self._having is None else self._having.incr_arity(),
        )

    def join_left(self, next: Type[TC1], on: Constraint2[TC, TC1] | None = None) -> 'ComputedQuery2[TC, TC1]':
        return ComputedQuery2(
            self.table1, next, JoinType.Left, on,
            self._selection, None if self._where is None else self._where.incr_arity(),
            self._order_by, self._group_by, self._computed,
            None if self._having is None else self._having.incr_arity(),
        )

    def _resolved_selection(self) -> List[PropSelect[Any, Any]]:
        # Unlike the plain QueryN, an unset selection here defaults to *no* plain columns rather than
        # every column -- SELECT * alongside an aggregate is almost never valid SQL (every
        # unaggregated column would need to be in GROUP BY), so defaulting to "just the computed
        # columns" is far more often what's actually wanted.
        return list(self._selection or [])

    def to_sql(self) -> str:
        selection = self._resolved_selection()
        assert len(selection) > 0 or len(self._computed) > 0, 'You must select at least one column or computed value'
        selections = ', '.join([*(p.label for p in selection), *_computed_sql_parts(self._computed, qualify=False)])
        where_clause = '' if self._where is None else (' WHERE ' + self._where.to_sql())
        group_by_clause = _group_by_sql(self._group_by, qualify=False)
        having_clause = '' if self._having is None else (' HAVING ' + self._having.to_sql())
        order_by_clause = _order_by_sql(self._order_by, qualify=False)
        return f'SELECT {selections} FROM {self.table1.__name__.lower()}{where_clause}{group_by_clause}{having_clause}{order_by_clause};'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        selection = self._resolved_selection()
        assert len(selection) > 0 or len(self._computed) > 0, 'You must select at least one column or computed value'
        selections = ', '.join([*(p.label for p in selection), *_computed_sql_parts(self._computed, qualify=False)])
        group_by_clause = _group_by_sql(self._group_by, qualify=False)
        order_by_clause = _order_by_sql(self._order_by, qualify=False)
        params: List[Any] = []
        where_clause = ''
        if self._where is not None:
            where_sql, where_params = self._where.to_sql_params()
            where_clause = ' WHERE ' + where_sql
            params += where_params
        having_clause = ''
        if self._having is not None:
            having_sql, having_params = self._having.to_sql_params()
            having_clause = ' HAVING ' + having_sql
            params += having_params
        return f'SELECT {selections} FROM {self.table1.__name__.lower()}{where_clause}{group_by_clause}{having_clause}{order_by_clause};', params


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


# --- 2 tables ---

@dataclass(frozen=True)
class Query2(Generic[TC, TC1], SqlQuery[Tuple[PartialModel[TC], PartialModel[TC1]]]):
    table1: Type[TC]
    table2: Type[TC1]
    join_type_2: JoinType
    on_2: Constraint2[TC, TC1] | None
    _selection: Sequence[PropSelect[TC, Any] | PropSelect[TC1, Any]] | None = None
    _where: Constraint2[TC, TC1] | None = None
    _order_by: Sequence[OrderBy[TC] | OrderBy[TC1]] = ()
    _group_by: Sequence[PropSelect[TC, Any] | PropSelect[TC1, Any]] = ()

    def select(self, sel: PropSelect[TC, Any] | PropSelect[TC1, Any], *sels: PropSelect[TC, Any] | PropSelect[TC1, Any]) -> 'Query2[TC, TC1]':
        return Query2(self.table1, self.table2, self.join_type_2, self.on_2, [sel, *sels], self._where, self._order_by, self._group_by)

    def select_more(self, sel: PropSelect[TC, Any] | PropSelect[TC1, Any], *sels: PropSelect[TC, Any] | PropSelect[TC1, Any]) -> 'Query2[TC, TC1]':
        return Query2(self.table1, self.table2, self.join_type_2, self.on_2, [*(self._selection or []), sel, *sels], self._where, self._order_by, self._group_by)

    def select_computed(self, computed: Computed[TC, Any] | Computed[TC1, Any], *more: Computed[TC, Any] | Computed[TC1, Any]) -> 'ComputedQuery2[TC, TC1]':
        return ComputedQuery2(self.table1, self.table2, self.join_type_2, self.on_2, self._selection, self._where, self._order_by, self._group_by, [computed, *more])

    def select_computed_more(self, computed: Computed[TC, Any] | Computed[TC1, Any], *more: Computed[TC, Any] | Computed[TC1, Any]) -> 'ComputedQuery2[TC, TC1]':
        return ComputedQuery2(self.table1, self.table2, self.join_type_2, self.on_2, self._selection, self._where, self._order_by, self._group_by, [computed, *more])

    def order_by(self, *order_by: OrderBy[TC] | OrderBy[TC1]) -> 'Query2[TC, TC1]':
        return Query2(self.table1, self.table2, self.join_type_2, self.on_2, self._selection, self._where, list(order_by), self._group_by)

    def order_by_more(self, column: Prop[TC, Any] | PropOpt[TC, Any] | Prop[TC1, Any] | PropOpt[TC1, Any], direction: Direction = Direction.ASC) -> 'Query2[TC, TC1]':
        new_entry: OrderBy[TC] | OrderBy[TC1] = OrderBy(column, direction) # type: ignore[assignment]
        return Query2(self.table1, self.table2, self.join_type_2, self.on_2, self._selection, self._where, [*self._order_by, new_entry], self._group_by)

    def group_by(self, *group_by: PropSelect[TC, Any] | PropSelect[TC1, Any]) -> 'Query2[TC, TC1]':
        return Query2(self.table1, self.table2, self.join_type_2, self.on_2, self._selection, self._where, self._order_by, list(group_by))

    def group_by_more(self, col: PropSelect[TC, Any] | PropSelect[TC1, Any], *cols: PropSelect[TC, Any] | PropSelect[TC1, Any]) -> 'Query2[TC, TC1]':
        return Query2(self.table1, self.table2, self.join_type_2, self.on_2, self._selection, self._where, self._order_by, [*self._group_by, col, *cols])

    def join_inner(self, next: Type[TC2], on: Constraint3[TC, TC1, TC2] | None = None) -> 'Query3[TC, TC1, TC2]':
        return Query3(
            self.table1, self.table2, next, self.join_type_2, self.on_2, JoinType.Inner, on,
            self._selection, None if self._where is None else self._where.incr_arity(),
            self._order_by, self._group_by,
        )

    def join_left(self, next: Type[TC2], on: Constraint3[TC, TC1, TC2] | None = None) -> 'Query3[TC, TC1, TC2]':
        return Query3(
            self.table1, self.table2, next, self.join_type_2, self.on_2, JoinType.Left, on,
            self._selection, None if self._where is None else self._where.incr_arity(),
            self._order_by, self._group_by,
        )

    def where(self, constraint: Constraint2[TC, TC1] | None = None) -> 'Query2[TC, TC1]':
        return Query2(self.table1, self.table2, self.join_type_2, self.on_2, self._selection, constraint, self._order_by, self._group_by)

    def where_and(self, constraint: Constraint2[TC, TC1]) -> 'Query2[TC, TC1]':
        return self.where(constraint if self._where is None else self._where.AND(constraint))

    def where_or(self, constraint: Constraint2[TC, TC1]) -> 'Query2[TC, TC1]':
        return self.where(constraint if self._where is None else self._where.OR(constraint))

    def _resolved_selection(self) -> List[PropSelect[Any, Any]]:
        return _resolve_selection(self._selection, self.table1, self.table2)

    def to_sql(self) -> str:
        selection = self._resolved_selection()
        assert len(selection) > 0, 'You must select at least one column'
        assert self.on_2 is not None, 'You must specify a join condition for join 2'

        selections = ', '.join(_qualified_label(p) for p in selection)
        where_clause = '' if self._where is None else ' WHERE ' + self._where.to_sql()
        group_by_clause = _group_by_sql(self._group_by, qualify=True)
        order_by_clause = _order_by_sql(self._order_by, qualify=True)

        from_clause = f'{self.table1.__name__.lower()}'
        on_2_clause = self.on_2.to_sql()
        from_clause += f' {self.join_type_2.value} JOIN {self.table2.__name__.lower()} ON {on_2_clause}'

        return f'SELECT {selections} FROM {from_clause}{where_clause}{group_by_clause}{order_by_clause};'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        selection = self._resolved_selection()
        assert len(selection) > 0, 'You must select at least one column'
        assert self.on_2 is not None, 'You must specify a join condition for join 2'

        selections = ', '.join(_qualified_label(p) for p in selection)
        group_by_clause = _group_by_sql(self._group_by, qualify=True)
        order_by_clause = _order_by_sql(self._order_by, qualify=True)
        params: List[Any] = []

        on_2_clause, on_2_params = self.on_2.to_sql_params()
        params += on_2_params
        from_clause = f'{self.table1.__name__.lower()} {self.join_type_2.value} JOIN {self.table2.__name__.lower()} ON {on_2_clause}'

        if self._where is None:
            return f'SELECT {selections} FROM {from_clause}{group_by_clause}{order_by_clause};', params
        where_clause, where_params = self._where.to_sql_params()
        params += where_params
        return f'SELECT {selections} FROM {from_clause} WHERE {where_clause}{group_by_clause}{order_by_clause};', params

@dataclass(frozen=True)
class ComputedQuery2(Generic[TC, TC1], SqlQuery[Tuple[PartialModel[TC], PartialModel[TC1], ComputedResult]]):
    table1: Type[TC]
    table2: Type[TC1]
    join_type_2: JoinType
    on_2: Constraint2[TC, TC1] | None
    _selection: Sequence[PropSelect[TC, Any] | PropSelect[TC1, Any]] | None = None
    _where: Constraint2[TC, TC1] | None = None
    _order_by: Sequence[OrderBy[TC] | OrderBy[TC1]] = ()
    _group_by: Sequence[PropSelect[TC, Any] | PropSelect[TC1, Any]] = ()
    _computed: Sequence[Computed[TC, Any] | Computed[TC1, Any]] = ()
    _having: HavingConstraint2[TC, TC1] | None = None

    def select(self, sel: PropSelect[TC, Any] | PropSelect[TC1, Any], *sels: PropSelect[TC, Any] | PropSelect[TC1, Any]) -> 'ComputedQuery2[TC, TC1]':
        return ComputedQuery2(self.table1, self.table2, self.join_type_2, self.on_2, [sel, *sels], self._where, self._order_by, self._group_by, self._computed, self._having)

    def select_more(self, sel: PropSelect[TC, Any] | PropSelect[TC1, Any], *sels: PropSelect[TC, Any] | PropSelect[TC1, Any]) -> 'ComputedQuery2[TC, TC1]':
        return ComputedQuery2(self.table1, self.table2, self.join_type_2, self.on_2, [*(self._selection or []), sel, *sels], self._where, self._order_by, self._group_by, self._computed, self._having)

    def select_computed(self, computed: Computed[TC, Any] | Computed[TC1, Any], *more: Computed[TC, Any] | Computed[TC1, Any]) -> 'ComputedQuery2[TC, TC1]':
        return ComputedQuery2(self.table1, self.table2, self.join_type_2, self.on_2, self._selection, self._where, self._order_by, self._group_by, [computed, *more], self._having)

    def select_computed_more(self, computed: Computed[TC, Any] | Computed[TC1, Any], *more: Computed[TC, Any] | Computed[TC1, Any]) -> 'ComputedQuery2[TC, TC1]':
        return ComputedQuery2(self.table1, self.table2, self.join_type_2, self.on_2, self._selection, self._where, self._order_by, self._group_by, [*self._computed, computed, *more], self._having)

    def order_by(self, *order_by: OrderBy[TC] | OrderBy[TC1]) -> 'ComputedQuery2[TC, TC1]':
        return ComputedQuery2(self.table1, self.table2, self.join_type_2, self.on_2, self._selection, self._where, list(order_by), self._group_by, self._computed, self._having)

    def order_by_more(self, column: Prop[TC, Any] | PropOpt[TC, Any] | Prop[TC1, Any] | PropOpt[TC1, Any], direction: Direction = Direction.ASC) -> 'ComputedQuery2[TC, TC1]':
        new_entry: OrderBy[TC] | OrderBy[TC1] = OrderBy(column, direction) # type: ignore[assignment]
        return ComputedQuery2(self.table1, self.table2, self.join_type_2, self.on_2, self._selection, self._where, [*self._order_by, new_entry], self._group_by, self._computed, self._having)

    def group_by(self, *group_by: PropSelect[TC, Any] | PropSelect[TC1, Any]) -> 'ComputedQuery2[TC, TC1]':
        return ComputedQuery2(self.table1, self.table2, self.join_type_2, self.on_2, self._selection, self._where, self._order_by, list(group_by), self._computed, self._having)

    def group_by_more(self, col: PropSelect[TC, Any] | PropSelect[TC1, Any], *cols: PropSelect[TC, Any] | PropSelect[TC1, Any]) -> 'ComputedQuery2[TC, TC1]':
        return ComputedQuery2(self.table1, self.table2, self.join_type_2, self.on_2, self._selection, self._where, self._order_by, [*self._group_by, col, *cols], self._computed, self._having)

    def having(self, constraint: HavingConstraint2[TC, TC1] | None = None) -> 'ComputedQuery2[TC, TC1]':
        return ComputedQuery2(self.table1, self.table2, self.join_type_2, self.on_2, self._selection, self._where, self._order_by, self._group_by, self._computed, constraint)

    def having_and(self, constraint: HavingConstraint2[TC, TC1]) -> 'ComputedQuery2[TC, TC1]':
        return self.having(constraint if self._having is None else self._having.AND(constraint))

    def having_or(self, constraint: HavingConstraint2[TC, TC1]) -> 'ComputedQuery2[TC, TC1]':
        return self.having(constraint if self._having is None else self._having.OR(constraint))

    def where(self, constraint: Constraint2[TC, TC1] | None = None) -> 'ComputedQuery2[TC, TC1]':
        return ComputedQuery2(self.table1, self.table2, self.join_type_2, self.on_2, self._selection, constraint, self._order_by, self._group_by, self._computed, self._having)

    def where_and(self, constraint: Constraint2[TC, TC1]) -> 'ComputedQuery2[TC, TC1]':
        return self.where(constraint if self._where is None else self._where.AND(constraint))

    def where_or(self, constraint: Constraint2[TC, TC1]) -> 'ComputedQuery2[TC, TC1]':
        return self.where(constraint if self._where is None else self._where.OR(constraint))

    def join_inner(self, next: Type[TC2], on: Constraint3[TC, TC1, TC2] | None = None) -> 'ComputedQuery3[TC, TC1, TC2]':
        return ComputedQuery3(
            self.table1, self.table2, next, self.join_type_2, self.on_2, JoinType.Inner, on,
            self._selection, None if self._where is None else self._where.incr_arity(),
            self._order_by, self._group_by, self._computed,
            None if self._having is None else self._having.incr_arity(),
        )

    def join_left(self, next: Type[TC2], on: Constraint3[TC, TC1, TC2] | None = None) -> 'ComputedQuery3[TC, TC1, TC2]':
        return ComputedQuery3(
            self.table1, self.table2, next, self.join_type_2, self.on_2, JoinType.Left, on,
            self._selection, None if self._where is None else self._where.incr_arity(),
            self._order_by, self._group_by, self._computed,
            None if self._having is None else self._having.incr_arity(),
        )

    def _resolved_selection(self) -> List[PropSelect[Any, Any]]:
        return list(self._selection or [])

    def to_sql(self) -> str:
        selection = self._resolved_selection()
        assert len(selection) > 0 or len(self._computed) > 0, 'You must select at least one column or computed value'
        assert self.on_2 is not None, 'You must specify a join condition for join 2'

        selections = ', '.join([*(_qualified_label(p) for p in selection), *_computed_sql_parts(self._computed, qualify=True)])
        where_clause = '' if self._where is None else ' WHERE ' + self._where.to_sql()
        group_by_clause = _group_by_sql(self._group_by, qualify=True)
        having_clause = '' if self._having is None else ' HAVING ' + self._having.to_sql()
        order_by_clause = _order_by_sql(self._order_by, qualify=True)

        from_clause = f'{self.table1.__name__.lower()}'
        on_2_clause = self.on_2.to_sql()
        from_clause += f' {self.join_type_2.value} JOIN {self.table2.__name__.lower()} ON {on_2_clause}'

        return f'SELECT {selections} FROM {from_clause}{where_clause}{group_by_clause}{having_clause}{order_by_clause};'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        selection = self._resolved_selection()
        assert len(selection) > 0 or len(self._computed) > 0, 'You must select at least one column or computed value'
        assert self.on_2 is not None, 'You must specify a join condition for join 2'

        selections = ', '.join([*(_qualified_label(p) for p in selection), *_computed_sql_parts(self._computed, qualify=True)])
        group_by_clause = _group_by_sql(self._group_by, qualify=True)
        order_by_clause = _order_by_sql(self._order_by, qualify=True)
        params: List[Any] = []

        on_2_clause, on_2_params = self.on_2.to_sql_params()
        params += on_2_params
        from_clause = f'{self.table1.__name__.lower()} {self.join_type_2.value} JOIN {self.table2.__name__.lower()} ON {on_2_clause}'

        where_clause = ''
        if self._where is not None:
            where_sql, where_params = self._where.to_sql_params()
            where_clause = ' WHERE ' + where_sql
            params += where_params
        having_clause = ''
        if self._having is not None:
            having_sql, having_params = self._having.to_sql_params()
            having_clause = ' HAVING ' + having_sql
            params += having_params
        return f'SELECT {selections} FROM {from_clause}{where_clause}{group_by_clause}{having_clause}{order_by_clause};', params


# --- 3 tables ---

@dataclass(frozen=True)
class Query3(Generic[TC, TC1, TC2], SqlQuery[Tuple[PartialModel[TC], PartialModel[TC1], PartialModel[TC2]]]):
    table1: Type[TC]
    table2: Type[TC1]
    table3: Type[TC2]
    join_type_2: JoinType
    on_2: Constraint2[TC, TC1] | None
    join_type_3: JoinType
    on_3: Constraint3[TC, TC1, TC2] | None
    _selection: Sequence[PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any]] | None = None
    _where: Constraint3[TC, TC1, TC2] | None = None
    _order_by: Sequence[OrderBy[TC] | OrderBy[TC1] | OrderBy[TC2]] = ()
    _group_by: Sequence[PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any]] = ()

    def select(self, sel: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any], *sels: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any]) -> 'Query3[TC, TC1, TC2]':
        return Query3(self.table1, self.table2, self.table3, self.join_type_2, self.on_2, self.join_type_3, self.on_3, [sel, *sels], self._where, self._order_by, self._group_by)

    def select_more(self, sel: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any], *sels: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any]) -> 'Query3[TC, TC1, TC2]':
        return Query3(self.table1, self.table2, self.table3, self.join_type_2, self.on_2, self.join_type_3, self.on_3, [*(self._selection or []), sel, *sels], self._where, self._order_by, self._group_by)

    def select_computed(self, computed: Computed[TC, Any] | Computed[TC1, Any] | Computed[TC2, Any], *more: Computed[TC, Any] | Computed[TC1, Any] | Computed[TC2, Any]) -> 'ComputedQuery3[TC, TC1, TC2]':
        return ComputedQuery3(self.table1, self.table2, self.table3, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self._selection, self._where, self._order_by, self._group_by, [computed, *more])

    def select_computed_more(self, computed: Computed[TC, Any] | Computed[TC1, Any] | Computed[TC2, Any], *more: Computed[TC, Any] | Computed[TC1, Any] | Computed[TC2, Any]) -> 'ComputedQuery3[TC, TC1, TC2]':
        return ComputedQuery3(self.table1, self.table2, self.table3, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self._selection, self._where, self._order_by, self._group_by, [computed, *more])

    def order_by(self, *order_by: OrderBy[TC] | OrderBy[TC1] | OrderBy[TC2]) -> 'Query3[TC, TC1, TC2]':
        return Query3(self.table1, self.table2, self.table3, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self._selection, self._where, list(order_by), self._group_by)

    def order_by_more(self, column: Prop[TC, Any] | PropOpt[TC, Any] | Prop[TC1, Any] | PropOpt[TC1, Any] | Prop[TC2, Any] | PropOpt[TC2, Any], direction: Direction = Direction.ASC) -> 'Query3[TC, TC1, TC2]':
        new_entry: OrderBy[TC] | OrderBy[TC1] | OrderBy[TC2] = OrderBy(column, direction) # type: ignore[assignment]
        return Query3(self.table1, self.table2, self.table3, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self._selection, self._where, [*self._order_by, new_entry], self._group_by)

    def group_by(self, *group_by: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any]) -> 'Query3[TC, TC1, TC2]':
        return Query3(self.table1, self.table2, self.table3, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self._selection, self._where, self._order_by, list(group_by))

    def group_by_more(self, col: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any], *cols: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any]) -> 'Query3[TC, TC1, TC2]':
        return Query3(self.table1, self.table2, self.table3, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self._selection, self._where, self._order_by, [*self._group_by, col, *cols])

    def join_inner(self, next: Type[TC3], on: Constraint4[TC, TC1, TC2, TC3] | None = None) -> 'Query4[TC, TC1, TC2, TC3]':
        return Query4(
            self.table1, self.table2, self.table3, next, self.join_type_2, self.on_2, self.join_type_3, self.on_3, JoinType.Inner, on,
            self._selection, None if self._where is None else self._where.incr_arity(),
            self._order_by, self._group_by,
        )

    def join_left(self, next: Type[TC3], on: Constraint4[TC, TC1, TC2, TC3] | None = None) -> 'Query4[TC, TC1, TC2, TC3]':
        return Query4(
            self.table1, self.table2, self.table3, next, self.join_type_2, self.on_2, self.join_type_3, self.on_3, JoinType.Left, on,
            self._selection, None if self._where is None else self._where.incr_arity(),
            self._order_by, self._group_by,
        )

    def where(self, constraint: Constraint3[TC, TC1, TC2] | None = None) -> 'Query3[TC, TC1, TC2]':
        return Query3(self.table1, self.table2, self.table3, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self._selection, constraint, self._order_by, self._group_by)

    def where_and(self, constraint: Constraint3[TC, TC1, TC2]) -> 'Query3[TC, TC1, TC2]':
        return self.where(constraint if self._where is None else self._where.AND(constraint))

    def where_or(self, constraint: Constraint3[TC, TC1, TC2]) -> 'Query3[TC, TC1, TC2]':
        return self.where(constraint if self._where is None else self._where.OR(constraint))

    def _resolved_selection(self) -> List[PropSelect[Any, Any]]:
        return _resolve_selection(self._selection, self.table1, self.table2, self.table3)

    def to_sql(self) -> str:
        selection = self._resolved_selection()
        assert len(selection) > 0, 'You must select at least one column'
        assert self.on_2 is not None, 'You must specify a join condition for join 2'
        assert self.on_3 is not None, 'You must specify a join condition for join 3'

        selections = ', '.join(_qualified_label(p) for p in selection)
        where_clause = '' if self._where is None else ' WHERE ' + self._where.to_sql()
        group_by_clause = _group_by_sql(self._group_by, qualify=True)
        order_by_clause = _order_by_sql(self._order_by, qualify=True)

        from_clause = f'{self.table1.__name__.lower()}'
        on_2_clause = self.on_2.to_sql()
        from_clause += f' {self.join_type_2.value} JOIN {self.table2.__name__.lower()} ON {on_2_clause}'
        on_3_clause = self.on_3.to_sql()
        from_clause += f' {self.join_type_3.value} JOIN {self.table3.__name__.lower()} ON {on_3_clause}'

        return f'SELECT {selections} FROM {from_clause}{where_clause}{group_by_clause}{order_by_clause};'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        selection = self._resolved_selection()
        assert len(selection) > 0, 'You must select at least one column'
        assert self.on_2 is not None, 'You must specify a join condition for join 2'
        assert self.on_3 is not None, 'You must specify a join condition for join 3'

        selections = ', '.join(_qualified_label(p) for p in selection)
        group_by_clause = _group_by_sql(self._group_by, qualify=True)
        order_by_clause = _order_by_sql(self._order_by, qualify=True)
        params: List[Any] = []

        on_2_clause, on_2_params = self.on_2.to_sql_params()
        params += on_2_params
        from_clause = f'{self.table1.__name__.lower()} {self.join_type_2.value} JOIN {self.table2.__name__.lower()} ON {on_2_clause}'
        on_3_clause, on_3_params = self.on_3.to_sql_params()
        params += on_3_params
        from_clause += f' {self.join_type_3.value} JOIN {self.table3.__name__.lower()} ON {on_3_clause}'

        if self._where is None:
            return f'SELECT {selections} FROM {from_clause}{group_by_clause}{order_by_clause};', params
        where_clause, where_params = self._where.to_sql_params()
        params += where_params
        return f'SELECT {selections} FROM {from_clause} WHERE {where_clause}{group_by_clause}{order_by_clause};', params

@dataclass(frozen=True)
class ComputedQuery3(Generic[TC, TC1, TC2], SqlQuery[Tuple[PartialModel[TC], PartialModel[TC1], PartialModel[TC2], ComputedResult]]):
    table1: Type[TC]
    table2: Type[TC1]
    table3: Type[TC2]
    join_type_2: JoinType
    on_2: Constraint2[TC, TC1] | None
    join_type_3: JoinType
    on_3: Constraint3[TC, TC1, TC2] | None
    _selection: Sequence[PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any]] | None = None
    _where: Constraint3[TC, TC1, TC2] | None = None
    _order_by: Sequence[OrderBy[TC] | OrderBy[TC1] | OrderBy[TC2]] = ()
    _group_by: Sequence[PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any]] = ()
    _computed: Sequence[Computed[TC, Any] | Computed[TC1, Any] | Computed[TC2, Any]] = ()
    _having: HavingConstraint3[TC, TC1, TC2] | None = None

    def select(self, sel: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any], *sels: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any]) -> 'ComputedQuery3[TC, TC1, TC2]':
        return ComputedQuery3(self.table1, self.table2, self.table3, self.join_type_2, self.on_2, self.join_type_3, self.on_3, [sel, *sels], self._where, self._order_by, self._group_by, self._computed, self._having)

    def select_more(self, sel: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any], *sels: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any]) -> 'ComputedQuery3[TC, TC1, TC2]':
        return ComputedQuery3(self.table1, self.table2, self.table3, self.join_type_2, self.on_2, self.join_type_3, self.on_3, [*(self._selection or []), sel, *sels], self._where, self._order_by, self._group_by, self._computed, self._having)

    def select_computed(self, computed: Computed[TC, Any] | Computed[TC1, Any] | Computed[TC2, Any], *more: Computed[TC, Any] | Computed[TC1, Any] | Computed[TC2, Any]) -> 'ComputedQuery3[TC, TC1, TC2]':
        return ComputedQuery3(self.table1, self.table2, self.table3, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self._selection, self._where, self._order_by, self._group_by, [computed, *more], self._having)

    def select_computed_more(self, computed: Computed[TC, Any] | Computed[TC1, Any] | Computed[TC2, Any], *more: Computed[TC, Any] | Computed[TC1, Any] | Computed[TC2, Any]) -> 'ComputedQuery3[TC, TC1, TC2]':
        return ComputedQuery3(self.table1, self.table2, self.table3, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self._selection, self._where, self._order_by, self._group_by, [*self._computed, computed, *more], self._having)

    def order_by(self, *order_by: OrderBy[TC] | OrderBy[TC1] | OrderBy[TC2]) -> 'ComputedQuery3[TC, TC1, TC2]':
        return ComputedQuery3(self.table1, self.table2, self.table3, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self._selection, self._where, list(order_by), self._group_by, self._computed, self._having)

    def order_by_more(self, column: Prop[TC, Any] | PropOpt[TC, Any] | Prop[TC1, Any] | PropOpt[TC1, Any] | Prop[TC2, Any] | PropOpt[TC2, Any], direction: Direction = Direction.ASC) -> 'ComputedQuery3[TC, TC1, TC2]':
        new_entry: OrderBy[TC] | OrderBy[TC1] | OrderBy[TC2] = OrderBy(column, direction) # type: ignore[assignment]
        return ComputedQuery3(self.table1, self.table2, self.table3, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self._selection, self._where, [*self._order_by, new_entry], self._group_by, self._computed, self._having)

    def group_by(self, *group_by: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any]) -> 'ComputedQuery3[TC, TC1, TC2]':
        return ComputedQuery3(self.table1, self.table2, self.table3, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self._selection, self._where, self._order_by, list(group_by), self._computed, self._having)

    def group_by_more(self, col: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any], *cols: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any]) -> 'ComputedQuery3[TC, TC1, TC2]':
        return ComputedQuery3(self.table1, self.table2, self.table3, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self._selection, self._where, self._order_by, [*self._group_by, col, *cols], self._computed, self._having)

    def having(self, constraint: HavingConstraint3[TC, TC1, TC2] | None = None) -> 'ComputedQuery3[TC, TC1, TC2]':
        return ComputedQuery3(self.table1, self.table2, self.table3, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self._selection, self._where, self._order_by, self._group_by, self._computed, constraint)

    def having_and(self, constraint: HavingConstraint3[TC, TC1, TC2]) -> 'ComputedQuery3[TC, TC1, TC2]':
        return self.having(constraint if self._having is None else self._having.AND(constraint))

    def having_or(self, constraint: HavingConstraint3[TC, TC1, TC2]) -> 'ComputedQuery3[TC, TC1, TC2]':
        return self.having(constraint if self._having is None else self._having.OR(constraint))

    def where(self, constraint: Constraint3[TC, TC1, TC2] | None = None) -> 'ComputedQuery3[TC, TC1, TC2]':
        return ComputedQuery3(self.table1, self.table2, self.table3, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self._selection, constraint, self._order_by, self._group_by, self._computed, self._having)

    def where_and(self, constraint: Constraint3[TC, TC1, TC2]) -> 'ComputedQuery3[TC, TC1, TC2]':
        return self.where(constraint if self._where is None else self._where.AND(constraint))

    def where_or(self, constraint: Constraint3[TC, TC1, TC2]) -> 'ComputedQuery3[TC, TC1, TC2]':
        return self.where(constraint if self._where is None else self._where.OR(constraint))

    def join_inner(self, next: Type[TC3], on: Constraint4[TC, TC1, TC2, TC3] | None = None) -> 'ComputedQuery4[TC, TC1, TC2, TC3]':
        return ComputedQuery4(
            self.table1, self.table2, self.table3, next, self.join_type_2, self.on_2, self.join_type_3, self.on_3, JoinType.Inner, on,
            self._selection, None if self._where is None else self._where.incr_arity(),
            self._order_by, self._group_by, self._computed,
            None if self._having is None else self._having.incr_arity(),
        )

    def join_left(self, next: Type[TC3], on: Constraint4[TC, TC1, TC2, TC3] | None = None) -> 'ComputedQuery4[TC, TC1, TC2, TC3]':
        return ComputedQuery4(
            self.table1, self.table2, self.table3, next, self.join_type_2, self.on_2, self.join_type_3, self.on_3, JoinType.Left, on,
            self._selection, None if self._where is None else self._where.incr_arity(),
            self._order_by, self._group_by, self._computed,
            None if self._having is None else self._having.incr_arity(),
        )

    def _resolved_selection(self) -> List[PropSelect[Any, Any]]:
        return list(self._selection or [])

    def to_sql(self) -> str:
        selection = self._resolved_selection()
        assert len(selection) > 0 or len(self._computed) > 0, 'You must select at least one column or computed value'
        assert self.on_2 is not None, 'You must specify a join condition for join 2'
        assert self.on_3 is not None, 'You must specify a join condition for join 3'

        selections = ', '.join([*(_qualified_label(p) for p in selection), *_computed_sql_parts(self._computed, qualify=True)])
        where_clause = '' if self._where is None else ' WHERE ' + self._where.to_sql()
        group_by_clause = _group_by_sql(self._group_by, qualify=True)
        having_clause = '' if self._having is None else ' HAVING ' + self._having.to_sql()
        order_by_clause = _order_by_sql(self._order_by, qualify=True)

        from_clause = f'{self.table1.__name__.lower()}'
        on_2_clause = self.on_2.to_sql()
        from_clause += f' {self.join_type_2.value} JOIN {self.table2.__name__.lower()} ON {on_2_clause}'
        on_3_clause = self.on_3.to_sql()
        from_clause += f' {self.join_type_3.value} JOIN {self.table3.__name__.lower()} ON {on_3_clause}'

        return f'SELECT {selections} FROM {from_clause}{where_clause}{group_by_clause}{having_clause}{order_by_clause};'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        selection = self._resolved_selection()
        assert len(selection) > 0 or len(self._computed) > 0, 'You must select at least one column or computed value'
        assert self.on_2 is not None, 'You must specify a join condition for join 2'
        assert self.on_3 is not None, 'You must specify a join condition for join 3'

        selections = ', '.join([*(_qualified_label(p) for p in selection), *_computed_sql_parts(self._computed, qualify=True)])
        group_by_clause = _group_by_sql(self._group_by, qualify=True)
        order_by_clause = _order_by_sql(self._order_by, qualify=True)
        params: List[Any] = []

        on_2_clause, on_2_params = self.on_2.to_sql_params()
        params += on_2_params
        from_clause = f'{self.table1.__name__.lower()} {self.join_type_2.value} JOIN {self.table2.__name__.lower()} ON {on_2_clause}'
        on_3_clause, on_3_params = self.on_3.to_sql_params()
        params += on_3_params
        from_clause += f' {self.join_type_3.value} JOIN {self.table3.__name__.lower()} ON {on_3_clause}'

        where_clause = ''
        if self._where is not None:
            where_sql, where_params = self._where.to_sql_params()
            where_clause = ' WHERE ' + where_sql
            params += where_params
        having_clause = ''
        if self._having is not None:
            having_sql, having_params = self._having.to_sql_params()
            having_clause = ' HAVING ' + having_sql
            params += having_params
        return f'SELECT {selections} FROM {from_clause}{where_clause}{group_by_clause}{having_clause}{order_by_clause};', params


# --- 4 tables ---

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
    _selection: Sequence[PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any] | PropSelect[TC3, Any]] | None = None
    _where: Constraint4[TC, TC1, TC2, TC3] | None = None
    _order_by: Sequence[OrderBy[TC] | OrderBy[TC1] | OrderBy[TC2] | OrderBy[TC3]] = ()
    _group_by: Sequence[PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any] | PropSelect[TC3, Any]] = ()

    def select(self, sel: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any] | PropSelect[TC3, Any], *sels: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any] | PropSelect[TC3, Any]) -> 'Query4[TC, TC1, TC2, TC3]':
        return Query4(self.table1, self.table2, self.table3, self.table4, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self.join_type_4, self.on_4, [sel, *sels], self._where, self._order_by, self._group_by)

    def select_more(self, sel: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any] | PropSelect[TC3, Any], *sels: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any] | PropSelect[TC3, Any]) -> 'Query4[TC, TC1, TC2, TC3]':
        return Query4(self.table1, self.table2, self.table3, self.table4, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self.join_type_4, self.on_4, [*(self._selection or []), sel, *sels], self._where, self._order_by, self._group_by)

    def select_computed(self, computed: Computed[TC, Any] | Computed[TC1, Any] | Computed[TC2, Any] | Computed[TC3, Any], *more: Computed[TC, Any] | Computed[TC1, Any] | Computed[TC2, Any] | Computed[TC3, Any]) -> 'ComputedQuery4[TC, TC1, TC2, TC3]':
        return ComputedQuery4(self.table1, self.table2, self.table3, self.table4, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self.join_type_4, self.on_4, self._selection, self._where, self._order_by, self._group_by, [computed, *more])

    def select_computed_more(self, computed: Computed[TC, Any] | Computed[TC1, Any] | Computed[TC2, Any] | Computed[TC3, Any], *more: Computed[TC, Any] | Computed[TC1, Any] | Computed[TC2, Any] | Computed[TC3, Any]) -> 'ComputedQuery4[TC, TC1, TC2, TC3]':
        return ComputedQuery4(self.table1, self.table2, self.table3, self.table4, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self.join_type_4, self.on_4, self._selection, self._where, self._order_by, self._group_by, [computed, *more])

    def order_by(self, *order_by: OrderBy[TC] | OrderBy[TC1] | OrderBy[TC2] | OrderBy[TC3]) -> 'Query4[TC, TC1, TC2, TC3]':
        return Query4(self.table1, self.table2, self.table3, self.table4, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self.join_type_4, self.on_4, self._selection, self._where, list(order_by), self._group_by)

    def order_by_more(self, column: Prop[TC, Any] | PropOpt[TC, Any] | Prop[TC1, Any] | PropOpt[TC1, Any] | Prop[TC2, Any] | PropOpt[TC2, Any] | Prop[TC3, Any] | PropOpt[TC3, Any], direction: Direction = Direction.ASC) -> 'Query4[TC, TC1, TC2, TC3]':
        new_entry: OrderBy[TC] | OrderBy[TC1] | OrderBy[TC2] | OrderBy[TC3] = OrderBy(column, direction) # type: ignore[assignment]
        return Query4(self.table1, self.table2, self.table3, self.table4, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self.join_type_4, self.on_4, self._selection, self._where, [*self._order_by, new_entry], self._group_by)

    def group_by(self, *group_by: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any] | PropSelect[TC3, Any]) -> 'Query4[TC, TC1, TC2, TC3]':
        return Query4(self.table1, self.table2, self.table3, self.table4, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self.join_type_4, self.on_4, self._selection, self._where, self._order_by, list(group_by))

    def group_by_more(self, col: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any] | PropSelect[TC3, Any], *cols: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any] | PropSelect[TC3, Any]) -> 'Query4[TC, TC1, TC2, TC3]':
        return Query4(self.table1, self.table2, self.table3, self.table4, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self.join_type_4, self.on_4, self._selection, self._where, self._order_by, [*self._group_by, col, *cols])

    def where(self, constraint: Constraint4[TC, TC1, TC2, TC3] | None = None) -> 'Query4[TC, TC1, TC2, TC3]':
        return Query4(self.table1, self.table2, self.table3, self.table4, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self.join_type_4, self.on_4, self._selection, constraint, self._order_by, self._group_by)

    def where_and(self, constraint: Constraint4[TC, TC1, TC2, TC3]) -> 'Query4[TC, TC1, TC2, TC3]':
        return self.where(constraint if self._where is None else self._where.AND(constraint))

    def where_or(self, constraint: Constraint4[TC, TC1, TC2, TC3]) -> 'Query4[TC, TC1, TC2, TC3]':
        return self.where(constraint if self._where is None else self._where.OR(constraint))

    def _resolved_selection(self) -> List[PropSelect[Any, Any]]:
        return _resolve_selection(self._selection, self.table1, self.table2, self.table3, self.table4)

    def to_sql(self) -> str:
        selection = self._resolved_selection()
        assert len(selection) > 0, 'You must select at least one column'
        assert self.on_2 is not None, 'You must specify a join condition for join 2'
        assert self.on_3 is not None, 'You must specify a join condition for join 3'
        assert self.on_4 is not None, 'You must specify a join condition for join 4'

        selections = ', '.join(_qualified_label(p) for p in selection)
        where_clause = '' if self._where is None else ' WHERE ' + self._where.to_sql()
        group_by_clause = _group_by_sql(self._group_by, qualify=True)
        order_by_clause = _order_by_sql(self._order_by, qualify=True)

        from_clause = f'{self.table1.__name__.lower()}'
        on_2_clause = self.on_2.to_sql()
        from_clause += f' {self.join_type_2.value} JOIN {self.table2.__name__.lower()} ON {on_2_clause}'
        on_3_clause = self.on_3.to_sql()
        from_clause += f' {self.join_type_3.value} JOIN {self.table3.__name__.lower()} ON {on_3_clause}'
        on_4_clause = self.on_4.to_sql()
        from_clause += f' {self.join_type_4.value} JOIN {self.table4.__name__.lower()} ON {on_4_clause}'

        return f'SELECT {selections} FROM {from_clause}{where_clause}{group_by_clause}{order_by_clause};'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        selection = self._resolved_selection()
        assert len(selection) > 0, 'You must select at least one column'
        assert self.on_2 is not None, 'You must specify a join condition for join 2'
        assert self.on_3 is not None, 'You must specify a join condition for join 3'
        assert self.on_4 is not None, 'You must specify a join condition for join 4'

        selections = ', '.join(_qualified_label(p) for p in selection)
        group_by_clause = _group_by_sql(self._group_by, qualify=True)
        order_by_clause = _order_by_sql(self._order_by, qualify=True)
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
            return f'SELECT {selections} FROM {from_clause}{group_by_clause}{order_by_clause};', params
        where_clause, where_params = self._where.to_sql_params()
        params += where_params
        return f'SELECT {selections} FROM {from_clause} WHERE {where_clause}{group_by_clause}{order_by_clause};', params

@dataclass(frozen=True)
class ComputedQuery4(Generic[TC, TC1, TC2, TC3], SqlQuery[Tuple[PartialModel[TC], PartialModel[TC1], PartialModel[TC2], PartialModel[TC3], ComputedResult]]):
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
    _where: Constraint4[TC, TC1, TC2, TC3] | None = None
    _order_by: Sequence[OrderBy[TC] | OrderBy[TC1] | OrderBy[TC2] | OrderBy[TC3]] = ()
    _group_by: Sequence[PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any] | PropSelect[TC3, Any]] = ()
    _computed: Sequence[Computed[TC, Any] | Computed[TC1, Any] | Computed[TC2, Any] | Computed[TC3, Any]] = ()
    _having: HavingConstraint4[TC, TC1, TC2, TC3] | None = None

    def select(self, sel: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any] | PropSelect[TC3, Any], *sels: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any] | PropSelect[TC3, Any]) -> 'ComputedQuery4[TC, TC1, TC2, TC3]':
        return ComputedQuery4(self.table1, self.table2, self.table3, self.table4, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self.join_type_4, self.on_4, [sel, *sels], self._where, self._order_by, self._group_by, self._computed, self._having)

    def select_more(self, sel: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any] | PropSelect[TC3, Any], *sels: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any] | PropSelect[TC3, Any]) -> 'ComputedQuery4[TC, TC1, TC2, TC3]':
        return ComputedQuery4(self.table1, self.table2, self.table3, self.table4, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self.join_type_4, self.on_4, [*(self._selection or []), sel, *sels], self._where, self._order_by, self._group_by, self._computed, self._having)

    def select_computed(self, computed: Computed[TC, Any] | Computed[TC1, Any] | Computed[TC2, Any] | Computed[TC3, Any], *more: Computed[TC, Any] | Computed[TC1, Any] | Computed[TC2, Any] | Computed[TC3, Any]) -> 'ComputedQuery4[TC, TC1, TC2, TC3]':
        return ComputedQuery4(self.table1, self.table2, self.table3, self.table4, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self.join_type_4, self.on_4, self._selection, self._where, self._order_by, self._group_by, [computed, *more], self._having)

    def select_computed_more(self, computed: Computed[TC, Any] | Computed[TC1, Any] | Computed[TC2, Any] | Computed[TC3, Any], *more: Computed[TC, Any] | Computed[TC1, Any] | Computed[TC2, Any] | Computed[TC3, Any]) -> 'ComputedQuery4[TC, TC1, TC2, TC3]':
        return ComputedQuery4(self.table1, self.table2, self.table3, self.table4, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self.join_type_4, self.on_4, self._selection, self._where, self._order_by, self._group_by, [*self._computed, computed, *more], self._having)

    def order_by(self, *order_by: OrderBy[TC] | OrderBy[TC1] | OrderBy[TC2] | OrderBy[TC3]) -> 'ComputedQuery4[TC, TC1, TC2, TC3]':
        return ComputedQuery4(self.table1, self.table2, self.table3, self.table4, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self.join_type_4, self.on_4, self._selection, self._where, list(order_by), self._group_by, self._computed, self._having)

    def order_by_more(self, column: Prop[TC, Any] | PropOpt[TC, Any] | Prop[TC1, Any] | PropOpt[TC1, Any] | Prop[TC2, Any] | PropOpt[TC2, Any] | Prop[TC3, Any] | PropOpt[TC3, Any], direction: Direction = Direction.ASC) -> 'ComputedQuery4[TC, TC1, TC2, TC3]':
        new_entry: OrderBy[TC] | OrderBy[TC1] | OrderBy[TC2] | OrderBy[TC3] = OrderBy(column, direction) # type: ignore[assignment]
        return ComputedQuery4(self.table1, self.table2, self.table3, self.table4, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self.join_type_4, self.on_4, self._selection, self._where, [*self._order_by, new_entry], self._group_by, self._computed, self._having)

    def group_by(self, *group_by: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any] | PropSelect[TC3, Any]) -> 'ComputedQuery4[TC, TC1, TC2, TC3]':
        return ComputedQuery4(self.table1, self.table2, self.table3, self.table4, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self.join_type_4, self.on_4, self._selection, self._where, self._order_by, list(group_by), self._computed, self._having)

    def group_by_more(self, col: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any] | PropSelect[TC3, Any], *cols: PropSelect[TC, Any] | PropSelect[TC1, Any] | PropSelect[TC2, Any] | PropSelect[TC3, Any]) -> 'ComputedQuery4[TC, TC1, TC2, TC3]':
        return ComputedQuery4(self.table1, self.table2, self.table3, self.table4, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self.join_type_4, self.on_4, self._selection, self._where, self._order_by, [*self._group_by, col, *cols], self._computed, self._having)

    def having(self, constraint: HavingConstraint4[TC, TC1, TC2, TC3] | None = None) -> 'ComputedQuery4[TC, TC1, TC2, TC3]':
        return ComputedQuery4(self.table1, self.table2, self.table3, self.table4, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self.join_type_4, self.on_4, self._selection, self._where, self._order_by, self._group_by, self._computed, constraint)

    def having_and(self, constraint: HavingConstraint4[TC, TC1, TC2, TC3]) -> 'ComputedQuery4[TC, TC1, TC2, TC3]':
        return self.having(constraint if self._having is None else self._having.AND(constraint))

    def having_or(self, constraint: HavingConstraint4[TC, TC1, TC2, TC3]) -> 'ComputedQuery4[TC, TC1, TC2, TC3]':
        return self.having(constraint if self._having is None else self._having.OR(constraint))

    def where(self, constraint: Constraint4[TC, TC1, TC2, TC3] | None = None) -> 'ComputedQuery4[TC, TC1, TC2, TC3]':
        return ComputedQuery4(self.table1, self.table2, self.table3, self.table4, self.join_type_2, self.on_2, self.join_type_3, self.on_3, self.join_type_4, self.on_4, self._selection, constraint, self._order_by, self._group_by, self._computed, self._having)

    def where_and(self, constraint: Constraint4[TC, TC1, TC2, TC3]) -> 'ComputedQuery4[TC, TC1, TC2, TC3]':
        return self.where(constraint if self._where is None else self._where.AND(constraint))

    def where_or(self, constraint: Constraint4[TC, TC1, TC2, TC3]) -> 'ComputedQuery4[TC, TC1, TC2, TC3]':
        return self.where(constraint if self._where is None else self._where.OR(constraint))

    def _resolved_selection(self) -> List[PropSelect[Any, Any]]:
        return list(self._selection or [])

    def to_sql(self) -> str:
        selection = self._resolved_selection()
        assert len(selection) > 0 or len(self._computed) > 0, 'You must select at least one column or computed value'
        assert self.on_2 is not None, 'You must specify a join condition for join 2'
        assert self.on_3 is not None, 'You must specify a join condition for join 3'
        assert self.on_4 is not None, 'You must specify a join condition for join 4'

        selections = ', '.join([*(_qualified_label(p) for p in selection), *_computed_sql_parts(self._computed, qualify=True)])
        where_clause = '' if self._where is None else ' WHERE ' + self._where.to_sql()
        group_by_clause = _group_by_sql(self._group_by, qualify=True)
        having_clause = '' if self._having is None else ' HAVING ' + self._having.to_sql()
        order_by_clause = _order_by_sql(self._order_by, qualify=True)

        from_clause = f'{self.table1.__name__.lower()}'
        on_2_clause = self.on_2.to_sql()
        from_clause += f' {self.join_type_2.value} JOIN {self.table2.__name__.lower()} ON {on_2_clause}'
        on_3_clause = self.on_3.to_sql()
        from_clause += f' {self.join_type_3.value} JOIN {self.table3.__name__.lower()} ON {on_3_clause}'
        on_4_clause = self.on_4.to_sql()
        from_clause += f' {self.join_type_4.value} JOIN {self.table4.__name__.lower()} ON {on_4_clause}'

        return f'SELECT {selections} FROM {from_clause}{where_clause}{group_by_clause}{having_clause}{order_by_clause};'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        selection = self._resolved_selection()
        assert len(selection) > 0 or len(self._computed) > 0, 'You must select at least one column or computed value'
        assert self.on_2 is not None, 'You must specify a join condition for join 2'
        assert self.on_3 is not None, 'You must specify a join condition for join 3'
        assert self.on_4 is not None, 'You must specify a join condition for join 4'

        selections = ', '.join([*(_qualified_label(p) for p in selection), *_computed_sql_parts(self._computed, qualify=True)])
        group_by_clause = _group_by_sql(self._group_by, qualify=True)
        order_by_clause = _order_by_sql(self._order_by, qualify=True)
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

        where_clause = ''
        if self._where is not None:
            where_sql, where_params = self._where.to_sql_params()
            where_clause = ' WHERE ' + where_sql
            params += where_params
        having_clause = ''
        if self._having is not None:
            having_sql, having_params = self._having.to_sql_params()
            having_clause = ' HAVING ' + having_sql
            params += having_params
        return f'SELECT {selections} FROM {from_clause}{where_clause}{group_by_clause}{having_clause}{order_by_clause};', params
