
from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, TypeVar

from pydoptic.selector import Prop, PropOpt
from pydoptic_sql import SqlTable

TC = TypeVar('TC', bound=SqlTable, contravariant=True)

class Direction(Enum):
    ASC = 'ASC'
    DESC = 'DESC'

@dataclass(frozen=True)
class OrderBy(Generic[TC]):
    """
    A single ORDER BY entry. Unlike `Constraint`, this never needs arity variants (`OrderBy2`, ...)
    since it only ever wraps one column -- ordering by a cross-table comparison isn't a thing. A
    joined query's `_order_by` is instead typed as a union, e.g. `Sequence[OrderBy[TC] | OrderBy[TC1]]`,
    so entries set before a join carry over unchanged and rendering (qualified vs. not) is decided
    by the query class doing the rendering, same as `PropSelect`/`_qualified_label` already work.
    """
    column: Prop[TC, Any] | PropOpt[TC, Any]
    direction: Direction = Direction.ASC

    def to_sql(self) -> str:
        return f'{self.column.label} {self.direction.value}'
