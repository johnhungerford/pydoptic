
from dataclasses import dataclass
from typing import Any, Generic, List, Sequence, Tuple, TypeVar

from pydoptic.selector import PropSelect, Prop, PropOpt
from pydoptic_sql import SqlTable
from pydoptic_sql.sql_computed import Computed
from pydoptic_sql.sql_constraint import Comparison, _comparison_symbol, _qualified_label

A = TypeVar('A')
TC = TypeVar('TC', bound=SqlTable, contravariant=True)
TC1 = TypeVar('TC1', bound=SqlTable, contravariant=True)
TC2 = TypeVar('TC2', bound=SqlTable, contravariant=True)
TC3 = TypeVar('TC3', bound=SqlTable, contravariant=True)

# HavingConstraint mirrors Constraint's structure exactly (same arity ladder, same qualify-baked-
# in-per-class rendering), but every operand position also accepts a Computed[TC, A] -- since HAVING
# is the one clause allowed to reference aggregate expressions, unlike WHERE/ON (Constraint) which
# deliberately can't: Computed isn't a PropSelect, so it's statically unusable there. A Computed
# operand renders as its bare function call ("SUM(age)"), never its alias ("worker_age_sum") --
# Postgres doesn't make SELECT-list aliases visible inside HAVING.

def _having_ref_sql(value: 'PropSelect[Any, Any] | Computed[Any, Any]', qualify: bool) -> str:
    """Render an operand that's always a reference (a column or an aggregate expression), never a
    literal -- used for the left-hand side of comparisons and the BETWEEN/IN 'value' operand."""
    if isinstance(value, Computed):
        col_ref = '*' if value.column is None else (_qualified_label(value.column) if qualify else value.column.label)
        return f'{value.function.value}({col_ref})'
    return _qualified_label(value) if qualify else value.label

def _having_display_value(value: Any, target_is_str: bool, qualify: bool) -> str:
    """Render an operand that might be a reference or a literal, for the interpolated (debug/display)
    to_sql() text -- literals are quoted inline here since there's no params list to bind them to."""
    if isinstance(value, (PropSelect, Computed)):
        return _having_ref_sql(value, qualify)
    text = str(value)
    return "'" + text + "'" if target_is_str else text

def _render_having_value(value: Any, qualify: bool) -> Tuple[str, List[Any]]:
    """Render an operand that might be a reference or a literal, for the parameterized to_sql_params()
    -- a literal becomes a `%s` placeholder bound to that value, same as _render_value in sql_constraint.py."""
    if isinstance(value, (PropSelect, Computed)):
        return _having_ref_sql(value, qualify), []
    return '%s', [value]


# --- arity 1: HAVING constraints over a single table ---

class HavingConstraint(Generic[TC]):
    def to_sql(self) -> str:
        raise NotImplementedError()

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        raise NotImplementedError()

    @classmethod
    def any(cls, *constraints: 'HavingConstraint[TC]') -> 'HavingOrConstraint[TC]':
        return HavingOrConstraint(list(constraints))

    @classmethod
    def all(cls, *constraints: 'HavingConstraint[TC]') -> 'HavingAndConstraint[TC]':
        return HavingAndConstraint(list(constraints))

    @classmethod
    def eq(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A], other: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | A) -> 'HavingCompConstraint[TC, A]':
        return HavingCompConstraint(prop, other, Comparison.EQ)

    @classmethod
    def gt(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A], other: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | A) -> 'HavingCompConstraint[TC, A]':
        return HavingCompConstraint(prop, other, Comparison.GT)

    @classmethod
    def gte(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A], other: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | A) -> 'HavingCompConstraint[TC, A]':
        return HavingCompConstraint(prop, other, Comparison.GTE)

    @classmethod
    def lt(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A], other: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | A) -> 'HavingCompConstraint[TC, A]':
        return HavingCompConstraint(prop, other, Comparison.LT)

    @classmethod
    def lte(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A], other: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | A) -> 'HavingCompConstraint[TC, A]':
        return HavingCompConstraint(prop, other, Comparison.LTE)

    @classmethod
    def ne(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A], other: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | A) -> 'HavingCompConstraint[TC, A]':
        return HavingCompConstraint(prop, other, Comparison.NE)

    @classmethod
    def like(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A], other: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | A) -> 'HavingCompConstraint[TC, A]':
        return HavingCompConstraint(prop, other, Comparison.LIKE)

    @classmethod
    def between(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A], lower: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | A, upper: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | A) -> 'HavingBetweenConstraint[TC, A]':
        return HavingBetweenConstraint(prop, lower, upper)

    @classmethod
    def in_(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A], values: Sequence[Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | A]) -> 'HavingInConstraint[TC, A]':
        return HavingInConstraint(prop, values)

    def AND(self, other: 'HavingConstraint[TC]') -> 'HavingAndConstraint[TC]':
        return HavingAndConstraint([self, other])

    def OR(self, other: 'HavingConstraint[TC]') -> 'HavingOrConstraint[TC]':
        return HavingOrConstraint([self, other])

    @property
    def NOT(self) -> 'HavingNotConstraint[TC]':
        return HavingNotConstraint(self)

@dataclass(frozen=True)
class HavingOrConstraint(HavingConstraint[TC]):
    constraints: List[HavingConstraint[TC]]

    def to_sql(self) -> str:
        return '(' + ' OR '.join(c.to_sql() for c in self.constraints) + ')'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        parts_params = [c.to_sql_params() for c in self.constraints]
        sql = '(' + ' OR '.join(part for part, _ in parts_params) + ')'
        params = [p for _, params in parts_params for p in params]
        return sql, params

@dataclass(frozen=True)
class HavingAndConstraint(HavingConstraint[TC]):
    constraints: List[HavingConstraint[TC]]

    def to_sql(self) -> str:
        return '(' + ' AND '.join(c.to_sql() for c in self.constraints) + ')'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        parts_params = [c.to_sql_params() for c in self.constraints]
        sql = '(' + ' AND '.join(part for part, _ in parts_params) + ')'
        params = [p for _, params in parts_params for p in params]
        return sql, params

@dataclass(frozen=True)
class HavingNotConstraint(HavingConstraint[TC]):
    constraint: HavingConstraint[TC]

    def to_sql(self) -> str:
        return 'NOT (' + self.constraint.to_sql() + ')'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        sql, params = self.constraint.to_sql_params()
        return 'NOT (' + sql + ')', params

@dataclass(frozen=True)
class HavingCompConstraint(Generic[TC, A], HavingConstraint[TC]):
    value_1: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A]
    value_2: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | A
    comp: Comparison

    def to_sql(self) -> str:
        value_2 = _having_display_value(self.value_2, self.value_1.target is str, qualify=False)
        return _having_ref_sql(self.value_1, qualify=False) + ' ' + _comparison_symbol(self.comp) + ' ' + value_2

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        value_2, params = _render_having_value(self.value_2, qualify=False)
        return _having_ref_sql(self.value_1, qualify=False) + ' ' + _comparison_symbol(self.comp) + ' ' + value_2, params

@dataclass(frozen=True)
class HavingBetweenConstraint(Generic[TC, A], HavingConstraint[TC]):
    value: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A]
    lower: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | A
    upper: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | A

    def to_sql(self) -> str:
        target_is_str = self.value.target is str
        lower = _having_display_value(self.lower, target_is_str, qualify=False)
        upper = _having_display_value(self.upper, target_is_str, qualify=False)
        return f'{_having_ref_sql(self.value, qualify=False)} BETWEEN {lower} AND {upper}'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        lower, lower_params = _render_having_value(self.lower, qualify=False)
        upper, upper_params = _render_having_value(self.upper, qualify=False)
        return f'{_having_ref_sql(self.value, qualify=False)} BETWEEN {lower} AND {upper}', lower_params + upper_params

@dataclass(frozen=True)
class HavingInConstraint(Generic[TC, A], HavingConstraint[TC]):
    value: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A]
    values: Sequence[Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | A]

    def to_sql(self) -> str:
        target_is_str = self.value.target is str
        values = [_having_display_value(c, target_is_str, qualify=False) for c in self.values]
        return f'{_having_ref_sql(self.value, qualify=False)} IN ({", ".join(values)})'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        rendered = [_render_having_value(c, qualify=False) for c in self.values]
        sql = f'{_having_ref_sql(self.value, qualify=False)} IN ({", ".join(part for part, _ in rendered)})'
        params = [p for _, params in rendered for p in params]
        return sql, params


# --- arity 2: HAVING constraints over a pair of joined tables ---
# Column/computed references always render table-qualified, since an operand here may reference
# either table and there's no other way to disambiguate.

class HavingConstraint2(Generic[TC, TC1]):
    def to_sql(self) -> str:
        raise NotImplementedError()

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        raise NotImplementedError()

    @classmethod
    def any(cls, *constraints: 'HavingConstraint2[TC, TC1]') -> 'HavingOrConstraint2[TC, TC1]':
        return HavingOrConstraint2(list(constraints))

    @classmethod
    def all(cls, *constraints: 'HavingConstraint2[TC, TC1]') -> 'HavingAndConstraint2[TC, TC1]':
        return HavingAndConstraint2(list(constraints))

    @classmethod
    def eq(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A], other: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | A) -> 'HavingCompConstraint2[TC, TC1, A]':
        return HavingCompConstraint2(prop, other, Comparison.EQ)

    @classmethod
    def gt(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A], other: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | A) -> 'HavingCompConstraint2[TC, TC1, A]':
        return HavingCompConstraint2(prop, other, Comparison.GT)

    @classmethod
    def gte(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A], other: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | A) -> 'HavingCompConstraint2[TC, TC1, A]':
        return HavingCompConstraint2(prop, other, Comparison.GTE)

    @classmethod
    def lt(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A], other: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | A) -> 'HavingCompConstraint2[TC, TC1, A]':
        return HavingCompConstraint2(prop, other, Comparison.LT)

    @classmethod
    def lte(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A], other: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | A) -> 'HavingCompConstraint2[TC, TC1, A]':
        return HavingCompConstraint2(prop, other, Comparison.LTE)

    @classmethod
    def ne(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A], other: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | A) -> 'HavingCompConstraint2[TC, TC1, A]':
        return HavingCompConstraint2(prop, other, Comparison.NE)

    @classmethod
    def like(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A], other: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | A) -> 'HavingCompConstraint2[TC, TC1, A]':
        return HavingCompConstraint2(prop, other, Comparison.LIKE)

    @classmethod
    def between(
        cls,
        prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A],
        lower: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | A,
        upper: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | A,
    ) -> 'HavingBetweenConstraint2[TC, TC1, A]':
        return HavingBetweenConstraint2(prop, lower, upper)

    @classmethod
    def in_(
        cls,
        prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A],
        values: Sequence[Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | A],
    ) -> 'HavingInConstraint2[TC, TC1, A]':
        return HavingInConstraint2(prop, values)

    def AND(self, other: 'HavingConstraint2[TC, TC1]') -> 'HavingAndConstraint2[TC, TC1]':
        return HavingAndConstraint2([self, other])

    def OR(self, other: 'HavingConstraint2[TC, TC1]') -> 'HavingOrConstraint2[TC, TC1]':
        return HavingOrConstraint2([self, other])

    @property
    def NOT(self) -> 'HavingNotConstraint2[TC, TC1]':
        return HavingNotConstraint2(self)

@dataclass(frozen=True)
class HavingOrConstraint2(HavingConstraint2[TC, TC1]):
    constraints: List[HavingConstraint2[TC, TC1]]

    def to_sql(self) -> str:
        return '(' + ' OR '.join(c.to_sql() for c in self.constraints) + ')'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        parts_params = [c.to_sql_params() for c in self.constraints]
        sql = '(' + ' OR '.join(part for part, _ in parts_params) + ')'
        params = [p for _, params in parts_params for p in params]
        return sql, params

@dataclass(frozen=True)
class HavingAndConstraint2(HavingConstraint2[TC, TC1]):
    constraints: List[HavingConstraint2[TC, TC1]]

    def to_sql(self) -> str:
        return '(' + ' AND '.join(c.to_sql() for c in self.constraints) + ')'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        parts_params = [c.to_sql_params() for c in self.constraints]
        sql = '(' + ' AND '.join(part for part, _ in parts_params) + ')'
        params = [p for _, params in parts_params for p in params]
        return sql, params

@dataclass(frozen=True)
class HavingNotConstraint2(HavingConstraint2[TC, TC1]):
    constraint: HavingConstraint2[TC, TC1]

    def to_sql(self) -> str:
        return 'NOT (' + self.constraint.to_sql() + ')'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        sql, params = self.constraint.to_sql_params()
        return 'NOT (' + sql + ')', params

@dataclass(frozen=True)
class HavingCompConstraint2(Generic[TC, TC1, A], HavingConstraint2[TC, TC1]):
    value_1: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A]
    value_2: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | A
    comp: Comparison

    def to_sql(self) -> str:
        value_2 = _having_display_value(self.value_2, self.value_1.target is str, qualify=True)
        return _having_ref_sql(self.value_1, qualify=True) + ' ' + _comparison_symbol(self.comp) + ' ' + value_2

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        value_2, params = _render_having_value(self.value_2, qualify=True)
        return _having_ref_sql(self.value_1, qualify=True) + ' ' + _comparison_symbol(self.comp) + ' ' + value_2, params

@dataclass(frozen=True)
class HavingBetweenConstraint2(Generic[TC, TC1, A], HavingConstraint2[TC, TC1]):
    value: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A]
    lower: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | A
    upper: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | A

    def to_sql(self) -> str:
        target_is_str = self.value.target is str
        lower = _having_display_value(self.lower, target_is_str, qualify=True)
        upper = _having_display_value(self.upper, target_is_str, qualify=True)
        return f'{_having_ref_sql(self.value, qualify=True)} BETWEEN {lower} AND {upper}'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        lower, lower_params = _render_having_value(self.lower, qualify=True)
        upper, upper_params = _render_having_value(self.upper, qualify=True)
        return f'{_having_ref_sql(self.value, qualify=True)} BETWEEN {lower} AND {upper}', lower_params + upper_params

@dataclass(frozen=True)
class HavingInConstraint2(Generic[TC, TC1, A], HavingConstraint2[TC, TC1]):
    value: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A]
    values: Sequence[Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | A]

    def to_sql(self) -> str:
        target_is_str = self.value.target is str
        values = [_having_display_value(c, target_is_str, qualify=True) for c in self.values]
        return f'{_having_ref_sql(self.value, qualify=True)} IN ({", ".join(values)})'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        rendered = [_render_having_value(c, qualify=True) for c in self.values]
        sql = f'{_having_ref_sql(self.value, qualify=True)} IN ({", ".join(part for part, _ in rendered)})'
        params = [p for _, params in rendered for p in params]
        return sql, params


# --- arity 3: HAVING constraints over 3 joined tables ---

class HavingConstraint3(Generic[TC, TC1, TC2]):
    def to_sql(self) -> str:
        raise NotImplementedError()

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        raise NotImplementedError()

    @classmethod
    def any(cls, *constraints: 'HavingConstraint3[TC, TC1, TC2]') -> 'HavingOrConstraint3[TC, TC1, TC2]':
        return HavingOrConstraint3(list(constraints))

    @classmethod
    def all(cls, *constraints: 'HavingConstraint3[TC, TC1, TC2]') -> 'HavingAndConstraint3[TC, TC1, TC2]':
        return HavingAndConstraint3(list(constraints))

    @classmethod
    def eq(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A], other: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | A) -> 'HavingCompConstraint3[TC, TC1, TC2, A]':
        return HavingCompConstraint3(prop, other, Comparison.EQ)

    @classmethod
    def gt(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A], other: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | A) -> 'HavingCompConstraint3[TC, TC1, TC2, A]':
        return HavingCompConstraint3(prop, other, Comparison.GT)

    @classmethod
    def gte(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A], other: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | A) -> 'HavingCompConstraint3[TC, TC1, TC2, A]':
        return HavingCompConstraint3(prop, other, Comparison.GTE)

    @classmethod
    def lt(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A], other: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | A) -> 'HavingCompConstraint3[TC, TC1, TC2, A]':
        return HavingCompConstraint3(prop, other, Comparison.LT)

    @classmethod
    def lte(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A], other: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | A) -> 'HavingCompConstraint3[TC, TC1, TC2, A]':
        return HavingCompConstraint3(prop, other, Comparison.LTE)

    @classmethod
    def ne(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A], other: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | A) -> 'HavingCompConstraint3[TC, TC1, TC2, A]':
        return HavingCompConstraint3(prop, other, Comparison.NE)

    @classmethod
    def like(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A], other: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | A) -> 'HavingCompConstraint3[TC, TC1, TC2, A]':
        return HavingCompConstraint3(prop, other, Comparison.LIKE)

    @classmethod
    def between(
        cls,
        prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A],
        lower: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | A,
        upper: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | A,
    ) -> 'HavingBetweenConstraint3[TC, TC1, TC2, A]':
        return HavingBetweenConstraint3(prop, lower, upper)

    @classmethod
    def in_(
        cls,
        prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A],
        values: Sequence[Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | A],
    ) -> 'HavingInConstraint3[TC, TC1, TC2, A]':
        return HavingInConstraint3(prop, values)

    def AND(self, other: 'HavingConstraint3[TC, TC1, TC2]') -> 'HavingAndConstraint3[TC, TC1, TC2]':
        return HavingAndConstraint3([self, other])

    def OR(self, other: 'HavingConstraint3[TC, TC1, TC2]') -> 'HavingOrConstraint3[TC, TC1, TC2]':
        return HavingOrConstraint3([self, other])

    @property
    def NOT(self) -> 'HavingNotConstraint3[TC, TC1, TC2]':
        return HavingNotConstraint3(self)

@dataclass(frozen=True)
class HavingOrConstraint3(HavingConstraint3[TC, TC1, TC2]):
    constraints: List[HavingConstraint3[TC, TC1, TC2]]

    def to_sql(self) -> str:
        return '(' + ' OR '.join(c.to_sql() for c in self.constraints) + ')'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        parts_params = [c.to_sql_params() for c in self.constraints]
        sql = '(' + ' OR '.join(part for part, _ in parts_params) + ')'
        params = [p for _, params in parts_params for p in params]
        return sql, params

@dataclass(frozen=True)
class HavingAndConstraint3(HavingConstraint3[TC, TC1, TC2]):
    constraints: List[HavingConstraint3[TC, TC1, TC2]]

    def to_sql(self) -> str:
        return '(' + ' AND '.join(c.to_sql() for c in self.constraints) + ')'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        parts_params = [c.to_sql_params() for c in self.constraints]
        sql = '(' + ' AND '.join(part for part, _ in parts_params) + ')'
        params = [p for _, params in parts_params for p in params]
        return sql, params

@dataclass(frozen=True)
class HavingNotConstraint3(HavingConstraint3[TC, TC1, TC2]):
    constraint: HavingConstraint3[TC, TC1, TC2]

    def to_sql(self) -> str:
        return 'NOT (' + self.constraint.to_sql() + ')'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        sql, params = self.constraint.to_sql_params()
        return 'NOT (' + sql + ')', params

@dataclass(frozen=True)
class HavingCompConstraint3(Generic[TC, TC1, TC2, A], HavingConstraint3[TC, TC1, TC2]):
    value_1: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A]
    value_2: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | A
    comp: Comparison

    def to_sql(self) -> str:
        value_2 = _having_display_value(self.value_2, self.value_1.target is str, qualify=True)
        return _having_ref_sql(self.value_1, qualify=True) + ' ' + _comparison_symbol(self.comp) + ' ' + value_2

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        value_2, params = _render_having_value(self.value_2, qualify=True)
        return _having_ref_sql(self.value_1, qualify=True) + ' ' + _comparison_symbol(self.comp) + ' ' + value_2, params

@dataclass(frozen=True)
class HavingBetweenConstraint3(Generic[TC, TC1, TC2, A], HavingConstraint3[TC, TC1, TC2]):
    value: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A]
    lower: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | A
    upper: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | A

    def to_sql(self) -> str:
        target_is_str = self.value.target is str
        lower = _having_display_value(self.lower, target_is_str, qualify=True)
        upper = _having_display_value(self.upper, target_is_str, qualify=True)
        return f'{_having_ref_sql(self.value, qualify=True)} BETWEEN {lower} AND {upper}'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        lower, lower_params = _render_having_value(self.lower, qualify=True)
        upper, upper_params = _render_having_value(self.upper, qualify=True)
        return f'{_having_ref_sql(self.value, qualify=True)} BETWEEN {lower} AND {upper}', lower_params + upper_params

@dataclass(frozen=True)
class HavingInConstraint3(Generic[TC, TC1, TC2, A], HavingConstraint3[TC, TC1, TC2]):
    value: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A]
    values: Sequence[Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | A]

    def to_sql(self) -> str:
        target_is_str = self.value.target is str
        values = [_having_display_value(c, target_is_str, qualify=True) for c in self.values]
        return f'{_having_ref_sql(self.value, qualify=True)} IN ({", ".join(values)})'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        rendered = [_render_having_value(c, qualify=True) for c in self.values]
        sql = f'{_having_ref_sql(self.value, qualify=True)} IN ({", ".join(part for part, _ in rendered)})'
        params = [p for _, params in rendered for p in params]
        return sql, params


# --- arity 4: HAVING constraints over 4 joined tables ---

class HavingConstraint4(Generic[TC, TC1, TC2, TC3]):
    def to_sql(self) -> str:
        raise NotImplementedError()

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        raise NotImplementedError()

    @classmethod
    def any(cls, *constraints: 'HavingConstraint4[TC, TC1, TC2, TC3]') -> 'HavingOrConstraint4[TC, TC1, TC2, TC3]':
        return HavingOrConstraint4(list(constraints))

    @classmethod
    def all(cls, *constraints: 'HavingConstraint4[TC, TC1, TC2, TC3]') -> 'HavingAndConstraint4[TC, TC1, TC2, TC3]':
        return HavingAndConstraint4(list(constraints))

    @classmethod
    def eq(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | Computed[TC3, A], other: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | Computed[TC3, A] | A) -> 'HavingCompConstraint4[TC, TC1, TC2, TC3, A]':
        return HavingCompConstraint4(prop, other, Comparison.EQ)

    @classmethod
    def gt(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | Computed[TC3, A], other: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | Computed[TC3, A] | A) -> 'HavingCompConstraint4[TC, TC1, TC2, TC3, A]':
        return HavingCompConstraint4(prop, other, Comparison.GT)

    @classmethod
    def gte(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | Computed[TC3, A], other: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | Computed[TC3, A] | A) -> 'HavingCompConstraint4[TC, TC1, TC2, TC3, A]':
        return HavingCompConstraint4(prop, other, Comparison.GTE)

    @classmethod
    def lt(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | Computed[TC3, A], other: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | Computed[TC3, A] | A) -> 'HavingCompConstraint4[TC, TC1, TC2, TC3, A]':
        return HavingCompConstraint4(prop, other, Comparison.LT)

    @classmethod
    def lte(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | Computed[TC3, A], other: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | Computed[TC3, A] | A) -> 'HavingCompConstraint4[TC, TC1, TC2, TC3, A]':
        return HavingCompConstraint4(prop, other, Comparison.LTE)

    @classmethod
    def ne(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | Computed[TC3, A], other: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | Computed[TC3, A] | A) -> 'HavingCompConstraint4[TC, TC1, TC2, TC3, A]':
        return HavingCompConstraint4(prop, other, Comparison.NE)

    @classmethod
    def like(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | Computed[TC3, A], other: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | Computed[TC3, A] | A) -> 'HavingCompConstraint4[TC, TC1, TC2, TC3, A]':
        return HavingCompConstraint4(prop, other, Comparison.LIKE)

    @classmethod
    def between(
        cls,
        prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | Computed[TC3, A],
        lower: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | Computed[TC3, A] | A,
        upper: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | Computed[TC3, A] | A,
    ) -> 'HavingBetweenConstraint4[TC, TC1, TC2, TC3, A]':
        return HavingBetweenConstraint4(prop, lower, upper)

    @classmethod
    def in_(
        cls,
        prop: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | Computed[TC3, A],
        values: Sequence[Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | Computed[TC3, A] | A],
    ) -> 'HavingInConstraint4[TC, TC1, TC2, TC3, A]':
        return HavingInConstraint4(prop, values)

    def AND(self, other: 'HavingConstraint4[TC, TC1, TC2, TC3]') -> 'HavingAndConstraint4[TC, TC1, TC2, TC3]':
        return HavingAndConstraint4([self, other])

    def OR(self, other: 'HavingConstraint4[TC, TC1, TC2, TC3]') -> 'HavingOrConstraint4[TC, TC1, TC2, TC3]':
        return HavingOrConstraint4([self, other])

    @property
    def NOT(self) -> 'HavingNotConstraint4[TC, TC1, TC2, TC3]':
        return HavingNotConstraint4(self)

@dataclass(frozen=True)
class HavingOrConstraint4(HavingConstraint4[TC, TC1, TC2, TC3]):
    constraints: List[HavingConstraint4[TC, TC1, TC2, TC3]]

    def to_sql(self) -> str:
        return '(' + ' OR '.join(c.to_sql() for c in self.constraints) + ')'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        parts_params = [c.to_sql_params() for c in self.constraints]
        sql = '(' + ' OR '.join(part for part, _ in parts_params) + ')'
        params = [p for _, params in parts_params for p in params]
        return sql, params

@dataclass(frozen=True)
class HavingAndConstraint4(HavingConstraint4[TC, TC1, TC2, TC3]):
    constraints: List[HavingConstraint4[TC, TC1, TC2, TC3]]

    def to_sql(self) -> str:
        return '(' + ' AND '.join(c.to_sql() for c in self.constraints) + ')'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        parts_params = [c.to_sql_params() for c in self.constraints]
        sql = '(' + ' AND '.join(part for part, _ in parts_params) + ')'
        params = [p for _, params in parts_params for p in params]
        return sql, params

@dataclass(frozen=True)
class HavingNotConstraint4(HavingConstraint4[TC, TC1, TC2, TC3]):
    constraint: HavingConstraint4[TC, TC1, TC2, TC3]

    def to_sql(self) -> str:
        return 'NOT (' + self.constraint.to_sql() + ')'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        sql, params = self.constraint.to_sql_params()
        return 'NOT (' + sql + ')', params

@dataclass(frozen=True)
class HavingCompConstraint4(Generic[TC, TC1, TC2, TC3, A], HavingConstraint4[TC, TC1, TC2, TC3]):
    value_1: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | Computed[TC3, A]
    value_2: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | Computed[TC3, A] | A
    comp: Comparison

    def to_sql(self) -> str:
        value_2 = _having_display_value(self.value_2, self.value_1.target is str, qualify=True)
        return _having_ref_sql(self.value_1, qualify=True) + ' ' + _comparison_symbol(self.comp) + ' ' + value_2

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        value_2, params = _render_having_value(self.value_2, qualify=True)
        return _having_ref_sql(self.value_1, qualify=True) + ' ' + _comparison_symbol(self.comp) + ' ' + value_2, params

@dataclass(frozen=True)
class HavingBetweenConstraint4(Generic[TC, TC1, TC2, TC3, A], HavingConstraint4[TC, TC1, TC2, TC3]):
    value: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | Computed[TC3, A]
    lower: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | Computed[TC3, A] | A
    upper: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | Computed[TC3, A] | A

    def to_sql(self) -> str:
        target_is_str = self.value.target is str
        lower = _having_display_value(self.lower, target_is_str, qualify=True)
        upper = _having_display_value(self.upper, target_is_str, qualify=True)
        return f'{_having_ref_sql(self.value, qualify=True)} BETWEEN {lower} AND {upper}'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        lower, lower_params = _render_having_value(self.lower, qualify=True)
        upper, upper_params = _render_having_value(self.upper, qualify=True)
        return f'{_having_ref_sql(self.value, qualify=True)} BETWEEN {lower} AND {upper}', lower_params + upper_params

@dataclass(frozen=True)
class HavingInConstraint4(Generic[TC, TC1, TC2, TC3, A], HavingConstraint4[TC, TC1, TC2, TC3]):
    value: Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | Computed[TC3, A]
    values: Sequence[Prop[TC, A] | PropOpt[TC, A] | Computed[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Computed[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Computed[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | Computed[TC3, A] | A]

    def to_sql(self) -> str:
        target_is_str = self.value.target is str
        values = [_having_display_value(c, target_is_str, qualify=True) for c in self.values]
        return f'{_having_ref_sql(self.value, qualify=True)} IN ({", ".join(values)})'

    def to_sql_params(self) -> Tuple[str, List[Any]]:
        rendered = [_render_having_value(c, qualify=True) for c in self.values]
        sql = f'{_having_ref_sql(self.value, qualify=True)} IN ({", ".join(part for part, _ in rendered)})'
        params = [p for _, params in rendered for p in params]
        return sql, params
