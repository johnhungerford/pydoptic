
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Generic, Mapping, Type, TypeVar

from pydoptic.selector import Prop, PropOpt, SelectVal, SelectValue, Selectable
from pydoptic_sql import SqlTable

TC = TypeVar('TC', bound=SqlTable, contravariant=True)
A = TypeVar('A')

class AggregateFunction(Enum):
    SUM = 'SUM'
    COUNT = 'COUNT'
    AVG = 'AVG'
    MIN = 'MIN'
    MAX = 'MAX'

class ComputedResult(Selectable['ComputedResult']):
    """
    Dict-backed holder for the computed (aggregate) columns of a query result row, keyed by each
    `Computed`'s alias. Mirrors `PartialModel`'s shape but isn't backed by a model class -- there's
    no schema behind an aggregate expression, just whatever aliases the query selected.
    """
    __slots__ = ['_dict']
    _dict: Dict[str, Any]

    def __init__(self, **kwargs: Any):
        object.__setattr__(self, '_dict', dict(kwargs))

    def __repr__(self) -> str:
        return 'ComputedResult(' + ', '.join(f'{k}={v}' for k, v in self._dict.items()) + ')'

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ComputedResult) and self._dict == other._dict

    def __getattr__(self, item: str) -> Any:
        try:
            return object.__getattribute__(self, '_dict')[item]
        except KeyError:
            raise AttributeError(item)

    def as_dict(self) -> Mapping[str, Any]:
        return self._dict

@dataclass(frozen=True, slots=True)
class Computed(Generic[TC, A], SelectVal[ComputedResult, A]):
    """
    An aggregate expression (SUM/COUNT/AVG/MIN/MAX) over a column, constructed via `SqlQuery.sum`/
    `.count`/etc., selected into a query via `select_computed`/`select_computed_more`, and extracted
    from a `ComputedResult` via `get_val`/`get_val_safe` -- same as a plain `Prop` extracts a value
    from a model. `column` is `None` only for `SqlQuery.count(table)` (`COUNT(*)`), which doesn't
    reference any particular column.

    `TC` is phantom bookkeeping, not part of the `Select[ComputedResult, A]` shape it's used as --
    it exists purely so `select_computed_more`'s signature can restrict which joined table(s) a given
    `Computed` may reference, the same way `OrderBy`'s `TC` does. Like `OrderBy`, `Computed` has no
    arity variants of its own: a joined query's computed selection is typed as a union of
    `Computed[<each joined table>, Any]`, so an entry set for one table stays valid unchanged as more
    tables get joined in, and qualification (`table.column` vs. bare) is decided by whichever class
    renders it, not by `Computed` itself.
    """
    column: Prop[TC, Any] | PropOpt[TC, Any] | None
    function: AggregateFunction
    label: str
    _target: Type[A]

    @property
    def origin(self) -> Type[ComputedResult]:
        return ComputedResult

    @property
    def target(self) -> Type[A]:
        return self._target

    def get_unsafe(self, value: 'Selectable[ComputedResult] | Dict[str, Any]') -> SelectValue[A]:
        if isinstance(value, dict):
            if self.label not in value:
                raise ValueError(f'Unexpected empty value for computed column {self.label}')
            result = value[self.label]
        else:
            try:
                result = getattr(value, self.label)
            except AttributeError:
                raise ValueError(f'Unexpected empty value for computed column {self.label}')
        return SelectValue(result, False, False)

    def get(self, value: ComputedResult) -> SelectValue[A]:
        return SelectValue(getattr(value, self.label), False, False)

    def to_sql(self) -> str:
        col_ref = '*' if self.column is None else self.column.label
        return f'{self.function.value}({col_ref}) AS {self.label}'
