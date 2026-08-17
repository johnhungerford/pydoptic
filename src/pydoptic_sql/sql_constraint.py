
from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, List, Sequence, TypeVar

from pydoptic.selector import PropSelect, Prop, PropOpt
from pydoptic_sql import SqlTable

A = TypeVar('A')
TC = TypeVar('TC', bound=SqlTable, contravariant=True)
TC1 = TypeVar('TC1', bound=SqlTable, contravariant=True)
TC2 = TypeVar('TC2', bound=SqlTable, contravariant=True)
TC3 = TypeVar('TC3', bound=SqlTable, contravariant=True)

def _qualified_label(prop: PropSelect[Any, Any]) -> str:
    return f'{prop.origin.__name__.lower()}.{prop.label}'

class Comparison(Enum):
    EQ = 1
    GT = 2
    GTE = 3
    LT = 4
    LTE = 5
    NE = 6
    LIKE = 7

def _comparison_symbol(comp: Comparison) -> str:
    match comp:
        case Comparison.EQ:
            return '='
        case Comparison.LT:
            return '<'
        case Comparison.LTE:
            return '<='
        case Comparison.GT:
            return '>'
        case Comparison.GTE:
            return '>='
        case Comparison.LIKE:
            return 'LIKE'
        case Comparison.NE:
            return '<>'


# --- arity 1: constraints over a single table ---

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

@dataclass(frozen=True)
class CompConstraint(Generic[TC, A], Constraint[TC]):
    value_1: Prop[TC, A] | PropOpt[TC, A]
    value_2: Prop[TC, A] | PropOpt[TC, A] | A
    comp: Comparison

    def to_sql(self) -> str:
        if isinstance(self.value_2, PropSelect):
            value_2 = self.value_2.label
        else:
            value_2 = str(self.value_2)
            if self.value_1.target is str:
                value_2 = "'" + value_2 + "'"
        return self.value_1.label + ' ' + _comparison_symbol(self.comp) + ' ' + value_2

@dataclass(frozen=True)
class BetweenConstraint(Generic[TC, A], Constraint[TC]):
    value: Prop[TC, A] | PropOpt[TC, A]
    lower: Prop[TC, A] | PropOpt[TC, A] | A
    upper: Prop[TC, A] | PropOpt[TC, A] | A

    def to_sql(self) -> str:
        lower = self.lower.label if isinstance(self.lower, PropSelect) else str(self.lower)
        upper = self.upper.label if isinstance(self.upper, PropSelect) else str(self.upper)
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


# --- arity 2: constraints over a pair of joined tables ---
# Column references always render table-qualified ("table.column"), since a constraint here may
# reference either table and there's no other way to disambiguate.

class Constraint2(Generic[TC, TC1]):
    def to_sql(self) -> str:
        raise NotImplementedError()

    @classmethod
    def any(cls, *constraints: 'Constraint2[TC, TC1]') -> 'OrConstraint2[TC, TC1]':
        return OrConstraint2(list(constraints))

    @classmethod
    def all(cls, *constraints: 'Constraint2[TC, TC1]') -> 'AndConstraint2[TC, TC1]':
        return AndConstraint2(list(constraints))

    @classmethod
    def eq(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A], other: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | A) -> 'CompConstraint2[TC, TC1, A]':
        return CompConstraint2(prop, other, Comparison.EQ)

    @classmethod
    def gt(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A], other: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | A) -> 'CompConstraint2[TC, TC1, A]':
        return CompConstraint2(prop, other, Comparison.GT)

    @classmethod
    def gte(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A], other: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | A) -> 'CompConstraint2[TC, TC1, A]':
        return CompConstraint2(prop, other, Comparison.GTE)

    @classmethod
    def lt(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A], other: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | A) -> 'CompConstraint2[TC, TC1, A]':
        return CompConstraint2(prop, other, Comparison.LT)

    @classmethod
    def lte(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A], other: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | A) -> 'CompConstraint2[TC, TC1, A]':
        return CompConstraint2(prop, other, Comparison.LTE)

    @classmethod
    def ne(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A], other: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | A) -> 'CompConstraint2[TC, TC1, A]':
        return CompConstraint2(prop, other, Comparison.NE)

    @classmethod
    def like(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A], other: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | A) -> 'CompConstraint2[TC, TC1, A]':
        return CompConstraint2(prop, other, Comparison.LIKE)

    @classmethod
    def between(
        cls,
        prop: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A],
        lower: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | A,
        upper: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | A,
    ) -> 'BetweenConstraint2[TC, TC1, A]':
        return BetweenConstraint2(prop, lower, upper)

    @classmethod
    def in_(
        cls,
        prop: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A],
        values: Sequence[Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | A],
    ) -> 'InConstraint2[TC, TC1, A]':
        return InConstraint2(prop, values)

    def AND(self, other: 'Constraint2[TC, TC1]') -> 'AndConstraint2[TC, TC1]':
        return AndConstraint2([self, other])

    def OR(self, other: 'Constraint2[TC, TC1]') -> 'OrConstraint2[TC, TC1]':
        return OrConstraint2([self, other])

    @property
    def NOT(self) -> 'NotConstraint2[TC, TC1]':
        return NotConstraint2(self)

@dataclass(frozen=True)
class OrConstraint2(Constraint2[TC, TC1]):
    constraints: List[Constraint2[TC, TC1]]

    def to_sql(self) -> str:
        return '(' + ' OR '.join(c.to_sql() for c in self.constraints) + ')'

@dataclass(frozen=True)
class AndConstraint2(Constraint2[TC, TC1]):
    constraints: List[Constraint2[TC, TC1]]

    def to_sql(self) -> str:
        return '(' + ' AND '.join(c.to_sql() for c in self.constraints) + ')'

@dataclass(frozen=True)
class NotConstraint2(Constraint2[TC, TC1]):
    constraint: Constraint2[TC, TC1]

    def to_sql(self) -> str:
        return 'NOT (' + self.constraint.to_sql() + ')'

@dataclass(frozen=True)
class CompConstraint2(Generic[TC, TC1, A], Constraint2[TC, TC1]):
    value_1: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A]
    value_2: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | A
    comp: Comparison

    def to_sql(self) -> str:
        if isinstance(self.value_2, PropSelect):
            value_2 = _qualified_label(self.value_2)
        else:
            value_2 = str(self.value_2)
            if self.value_1.target is str:
                value_2 = "'" + value_2 + "'"
        return _qualified_label(self.value_1) + ' ' + _comparison_symbol(self.comp) + ' ' + value_2

@dataclass(frozen=True)
class BetweenConstraint2(Generic[TC, TC1, A], Constraint2[TC, TC1]):
    value: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A]
    lower: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | A
    upper: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | A

    def to_sql(self) -> str:
        lower = _qualified_label(self.lower) if isinstance(self.lower, PropSelect) else str(self.lower)
        upper = _qualified_label(self.upper) if isinstance(self.upper, PropSelect) else str(self.upper)
        return f'{_qualified_label(self.value)} BETWEEN {lower} AND {upper}'

@dataclass(frozen=True)
class InConstraint2(Generic[TC, TC1, A], Constraint2[TC, TC1]):
    value: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A]
    values: Sequence[Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | A]

    def to_sql(self) -> str:
        def render(c: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | A) -> str:
            if isinstance(c, PropSelect):
                return _qualified_label(c)
            value = str(c)
            if self.value.target is str:
                value = "'" + value + "'"
            return value

        values = [render(c) for c in self.values]
        return f'{_qualified_label(self.value)} IN ({", ".join(values)})'

# --- arity 3: constraints over 3 joined tables ---
# Column references always render table-qualified ("table.column"), since a constraint here may
# reference any of the joined tables and there's no other way to disambiguate.

class Constraint3(Generic[TC, TC1, TC2]):
    def to_sql(self) -> str:
        raise NotImplementedError()

    @classmethod
    def any(cls, *constraints: 'Constraint3[TC, TC1, TC2]') -> 'OrConstraint3[TC, TC1, TC2]':
        return OrConstraint3(list(constraints))

    @classmethod
    def all(cls, *constraints: 'Constraint3[TC, TC1, TC2]') -> 'AndConstraint3[TC, TC1, TC2]':
        return AndConstraint3(list(constraints))

    @classmethod
    def eq(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A], other: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | A) -> 'CompConstraint3[TC, TC1, TC2, A]':
        return CompConstraint3(prop, other, Comparison.EQ)

    @classmethod
    def gt(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A], other: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | A) -> 'CompConstraint3[TC, TC1, TC2, A]':
        return CompConstraint3(prop, other, Comparison.GT)

    @classmethod
    def gte(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A], other: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | A) -> 'CompConstraint3[TC, TC1, TC2, A]':
        return CompConstraint3(prop, other, Comparison.GTE)

    @classmethod
    def lt(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A], other: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | A) -> 'CompConstraint3[TC, TC1, TC2, A]':
        return CompConstraint3(prop, other, Comparison.LT)

    @classmethod
    def lte(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A], other: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | A) -> 'CompConstraint3[TC, TC1, TC2, A]':
        return CompConstraint3(prop, other, Comparison.LTE)

    @classmethod
    def ne(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A], other: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | A) -> 'CompConstraint3[TC, TC1, TC2, A]':
        return CompConstraint3(prop, other, Comparison.NE)

    @classmethod
    def like(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A], other: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | A) -> 'CompConstraint3[TC, TC1, TC2, A]':
        return CompConstraint3(prop, other, Comparison.LIKE)

    @classmethod
    def between(
        cls,
        prop: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A],
        lower: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | A,
        upper: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | A,
    ) -> 'BetweenConstraint3[TC, TC1, TC2, A]':
        return BetweenConstraint3(prop, lower, upper)

    @classmethod
    def in_(
        cls,
        prop: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A],
        values: Sequence[Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | A],
    ) -> 'InConstraint3[TC, TC1, TC2, A]':
        return InConstraint3(prop, values)

    def AND(self, other: 'Constraint3[TC, TC1, TC2]') -> 'AndConstraint3[TC, TC1, TC2]':
        return AndConstraint3([self, other])

    def OR(self, other: 'Constraint3[TC, TC1, TC2]') -> 'OrConstraint3[TC, TC1, TC2]':
        return OrConstraint3([self, other])

    @property
    def NOT(self) -> 'NotConstraint3[TC, TC1, TC2]':
        return NotConstraint3(self)

@dataclass(frozen=True)
class OrConstraint3(Constraint3[TC, TC1, TC2]):
    constraints: List[Constraint3[TC, TC1, TC2]]

    def to_sql(self) -> str:
        return '(' + ' OR '.join(c.to_sql() for c in self.constraints) + ')'

@dataclass(frozen=True)
class AndConstraint3(Constraint3[TC, TC1, TC2]):
    constraints: List[Constraint3[TC, TC1, TC2]]

    def to_sql(self) -> str:
        return '(' + ' AND '.join(c.to_sql() for c in self.constraints) + ')'

@dataclass(frozen=True)
class NotConstraint3(Constraint3[TC, TC1, TC2]):
    constraint: Constraint3[TC, TC1, TC2]

    def to_sql(self) -> str:
        return 'NOT (' + self.constraint.to_sql() + ')'

@dataclass(frozen=True)
class CompConstraint3(Generic[TC, TC1, TC2, A], Constraint3[TC, TC1, TC2]):
    value_1: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A]
    value_2: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | A
    comp: Comparison

    def to_sql(self) -> str:
        if isinstance(self.value_2, PropSelect):
            value_2 = _qualified_label(self.value_2)
        else:
            value_2 = str(self.value_2)
            if self.value_1.target is str:
                value_2 = "'" + value_2 + "'"
        return _qualified_label(self.value_1) + ' ' + _comparison_symbol(self.comp) + ' ' + value_2

@dataclass(frozen=True)
class BetweenConstraint3(Generic[TC, TC1, TC2, A], Constraint3[TC, TC1, TC2]):
    value: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A]
    lower: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | A
    upper: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | A

    def to_sql(self) -> str:
        lower = _qualified_label(self.lower) if isinstance(self.lower, PropSelect) else str(self.lower)
        upper = _qualified_label(self.upper) if isinstance(self.upper, PropSelect) else str(self.upper)
        return f'{_qualified_label(self.value)} BETWEEN {lower} AND {upper}'

@dataclass(frozen=True)
class InConstraint3(Generic[TC, TC1, TC2, A], Constraint3[TC, TC1, TC2]):
    value: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A]
    values: Sequence[Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | A]

    def to_sql(self) -> str:
        def render(c: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | A) -> str:
            if isinstance(c, PropSelect):
                return _qualified_label(c)
            value = str(c)
            if self.value.target is str:
                value = "'" + value + "'"
            return value

        values = [render(c) for c in self.values]
        return f'{_qualified_label(self.value)} IN ({", ".join(values)})'

# --- arity 4: constraints over 4 joined tables ---
# Column references always render table-qualified ("table.column"), since a constraint here may
# reference any of the joined tables and there's no other way to disambiguate.

class Constraint4(Generic[TC, TC1, TC2, TC3]):
    def to_sql(self) -> str:
        raise NotImplementedError()

    @classmethod
    def any(cls, *constraints: 'Constraint4[TC, TC1, TC2, TC3]') -> 'OrConstraint4[TC, TC1, TC2, TC3]':
        return OrConstraint4(list(constraints))

    @classmethod
    def all(cls, *constraints: 'Constraint4[TC, TC1, TC2, TC3]') -> 'AndConstraint4[TC, TC1, TC2, TC3]':
        return AndConstraint4(list(constraints))

    @classmethod
    def eq(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A], other: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | A) -> 'CompConstraint4[TC, TC1, TC2, TC3, A]':
        return CompConstraint4(prop, other, Comparison.EQ)

    @classmethod
    def gt(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A], other: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | A) -> 'CompConstraint4[TC, TC1, TC2, TC3, A]':
        return CompConstraint4(prop, other, Comparison.GT)

    @classmethod
    def gte(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A], other: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | A) -> 'CompConstraint4[TC, TC1, TC2, TC3, A]':
        return CompConstraint4(prop, other, Comparison.GTE)

    @classmethod
    def lt(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A], other: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | A) -> 'CompConstraint4[TC, TC1, TC2, TC3, A]':
        return CompConstraint4(prop, other, Comparison.LT)

    @classmethod
    def lte(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A], other: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | A) -> 'CompConstraint4[TC, TC1, TC2, TC3, A]':
        return CompConstraint4(prop, other, Comparison.LTE)

    @classmethod
    def ne(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A], other: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | A) -> 'CompConstraint4[TC, TC1, TC2, TC3, A]':
        return CompConstraint4(prop, other, Comparison.NE)

    @classmethod
    def like(cls, prop: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A], other: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | A) -> 'CompConstraint4[TC, TC1, TC2, TC3, A]':
        return CompConstraint4(prop, other, Comparison.LIKE)

    @classmethod
    def between(
        cls,
        prop: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A],
        lower: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | A,
        upper: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | A,
    ) -> 'BetweenConstraint4[TC, TC1, TC2, TC3, A]':
        return BetweenConstraint4(prop, lower, upper)

    @classmethod
    def in_(
        cls,
        prop: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A],
        values: Sequence[Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | A],
    ) -> 'InConstraint4[TC, TC1, TC2, TC3, A]':
        return InConstraint4(prop, values)

    def AND(self, other: 'Constraint4[TC, TC1, TC2, TC3]') -> 'AndConstraint4[TC, TC1, TC2, TC3]':
        return AndConstraint4([self, other])

    def OR(self, other: 'Constraint4[TC, TC1, TC2, TC3]') -> 'OrConstraint4[TC, TC1, TC2, TC3]':
        return OrConstraint4([self, other])

    @property
    def NOT(self) -> 'NotConstraint4[TC, TC1, TC2, TC3]':
        return NotConstraint4(self)

@dataclass(frozen=True)
class OrConstraint4(Constraint4[TC, TC1, TC2, TC3]):
    constraints: List[Constraint4[TC, TC1, TC2, TC3]]

    def to_sql(self) -> str:
        return '(' + ' OR '.join(c.to_sql() for c in self.constraints) + ')'

@dataclass(frozen=True)
class AndConstraint4(Constraint4[TC, TC1, TC2, TC3]):
    constraints: List[Constraint4[TC, TC1, TC2, TC3]]

    def to_sql(self) -> str:
        return '(' + ' AND '.join(c.to_sql() for c in self.constraints) + ')'

@dataclass(frozen=True)
class NotConstraint4(Constraint4[TC, TC1, TC2, TC3]):
    constraint: Constraint4[TC, TC1, TC2, TC3]

    def to_sql(self) -> str:
        return 'NOT (' + self.constraint.to_sql() + ')'

@dataclass(frozen=True)
class CompConstraint4(Generic[TC, TC1, TC2, TC3, A], Constraint4[TC, TC1, TC2, TC3]):
    value_1: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A]
    value_2: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | A
    comp: Comparison

    def to_sql(self) -> str:
        if isinstance(self.value_2, PropSelect):
            value_2 = _qualified_label(self.value_2)
        else:
            value_2 = str(self.value_2)
            if self.value_1.target is str:
                value_2 = "'" + value_2 + "'"
        return _qualified_label(self.value_1) + ' ' + _comparison_symbol(self.comp) + ' ' + value_2

@dataclass(frozen=True)
class BetweenConstraint4(Generic[TC, TC1, TC2, TC3, A], Constraint4[TC, TC1, TC2, TC3]):
    value: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A]
    lower: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | A
    upper: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | A

    def to_sql(self) -> str:
        lower = _qualified_label(self.lower) if isinstance(self.lower, PropSelect) else str(self.lower)
        upper = _qualified_label(self.upper) if isinstance(self.upper, PropSelect) else str(self.upper)
        return f'{_qualified_label(self.value)} BETWEEN {lower} AND {upper}'

@dataclass(frozen=True)
class InConstraint4(Generic[TC, TC1, TC2, TC3, A], Constraint4[TC, TC1, TC2, TC3]):
    value: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A]
    values: Sequence[Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | A]

    def to_sql(self) -> str:
        def render(c: Prop[TC, A] | PropOpt[TC, A] | Prop[TC1, A] | PropOpt[TC1, A] | Prop[TC2, A] | PropOpt[TC2, A] | Prop[TC3, A] | PropOpt[TC3, A] | A) -> str:
            if isinstance(c, PropSelect):
                return _qualified_label(c)
            value = str(c)
            if self.value.target is str:
                value = "'" + value + "'"
            return value

        values = [render(c) for c in self.values]
        return f'{_qualified_label(self.value)} IN ({", ".join(values)})'
