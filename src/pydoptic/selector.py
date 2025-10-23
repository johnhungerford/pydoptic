from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import Any, Callable, Dict, Generic, List, Mapping, Tuple, Type, TypeVar, cast, Optional

A = TypeVar('A')
B = TypeVar('B')
C = TypeVar('C')

class Selectable:
    """
    Base class for typed model that can be manipulated by `Select` instances
    """

    def as_mapping(self) -> Mapping[str, Any]:
        """
        Shallow conversion to a dict representation. Properties that are `Selectable` are not converted.
        """
        raise NotImplementedError()
    
    def as_mapping_full(self) -> Mapping[str, Any]:
        """
        Complete conversion to a dict representation. Properties that are `Selectable` are converted recursively.
        """
        mapping: Dict[str, Any] = {}
        for k, v in self.as_mapping().items():
            if isinstance(v, Selectable):
                mapping[k] = v.as_mapping_full()
            else:
                mapping[k] = v
        return mapping

    def __eq__(self, value):
        if isinstance(value, Selectable):
            other_dict = value.as_mapping_full()
        elif isinstance(value, dict):
            other_dict = value
        else:
            return False
        return self.as_mapping_full() == other_dict

@dataclass(frozen=True)
class SelectValue(Generic[A]):
    """
    Represents the result of retrieving nested data, whether a single value, a missing value, or multiple values.
    Boolean flags indicate whether the value might be missing or is a list type, as determined by the `Select` types
    that retrieve it.
    """
    value: A | List[A] | None
    is_opt: bool
    is_arr: bool

    @property
    def as_list(self) -> List[A]:
        """
        Return value as a list. An empty value -> empty list. Single value -> list of length 1.
        """
        if self.value is None:
            return []
        if self.is_arr:
            return cast(List[A], self.value)
        return cast(List[A], [self.value])
    
    @property
    def as_opt(self) -> A | None:
        """
        Return value as an option. An empty list -> None. A non-empty list -> first element.
        """
        if self.value is None:
            return None
        if self.is_arr and isinstance(self.value, list):
            if len(self.value) < 1:
                return None
            return self.value[0]
        return cast(A, self.value)

    def for_each(self, fn: Callable[[A], None]):
        """
        Call a function on every element. If value is None or an empty list it will never be called. 
        If a non-empty list, it will be called on every element. If regular value, it will be called on that value.
        """
        if self.value is None:
            if not self.is_opt:
                raise ValueError()
            return
        if self.is_arr and isinstance(self.value, list):
            for a in self.value:
                fn(a)
            return
        fn(cast(A, self.value))

    def map(self, fn: Callable[[A], 'B']) -> 'SelectValue[B]':
        """
        Apply a function on every element converting each to a new value. If value is None or an empty list nothing will change. 
        If a non-empty list, every element will be converted. If regular value, that value will be converted.
        """
        if self.value is None:
            if not self.is_opt:
                raise ValueError()
            return cast(SelectValue[B], self)
        if self.is_arr and isinstance(self.value, list):
            return SelectValue([fn(v) for v in self.value], self.is_opt, self.is_arr)
        return SelectValue(fn(cast(A, self.value)), self.is_opt, self.is_arr)

    def flat_map(self, fn: Callable[[A], 'SelectValue[B]']) -> 'SelectValue[B]':
        """
        Apply a function on every element A converting it to a `SelectValue[A]`, and then flatten the nested `SelectValue[SelectValue[B]]` into a
        `SelectValue[B]`.
        """
        if self.value is None:
            if not self.is_opt:
                raise ValueError()
            return cast(SelectValue[B], self)
        if self.is_arr and isinstance(self.value, list):
            values = [v for val in self.value for v in fn(val).as_list]
            return SelectValue(values, self.is_opt, self.is_arr)
        result = fn(cast(A, self.value))
        return SelectValue(result.value, result.is_opt or self.is_opt, result.is_arr)


class Select(Generic[A, B]):
    """
    A reference to nested data that can be used to (1) retrieve and mutate that data and (2) specify the nested properties in any API that may need
    to refer to them (e.g., querying properties in a database).

    Every `Select[A, B]` value has an origin type `A` and target type `B` specified by its type parameters. `A` (origin) is the type that the referenced data 
    is nested on, and `B` (target) is the type of the nested data.

    The base type `Select` does not specify whether the nested data is optional or array-like. For more precisely typed variants, see `SelectVal`, `SelectOpt`,
    `SelectArr`, and `SelectOptArr`.
    """
    def __call__(self, next: 'Select[B, C]') -> 'Select[A, C]':
        """
        Link to another Select whose origin matches this target.
        """
        match next:
            case PropSelect():
                return LinkedSelect(self, next)
            case LinkedSelect(select_1=select_1, select_2=select_2):
                return LinkedSelect(self(select_1), select_2)
            case _:
                raise ValueError()

    def __hash__(self):
        match self:
            case PropSelect():
                return hash((self.label, self.origin, self.target, self.is_arr, self.is_opt))
            case LinkedSelect(select_1=sel_1, select_2=sel_2):
                return hash((sel_1, sel_2))
            case _:
                raise ValueError()

    @cached_property
    def attributes(self) -> List['PropSelect[Any, Any]']:
        """
        All the components of the select as a list of `PropSelect`s.
        """
        match self:
            case PropSelect():
                return [self]
            case LinkedSelect(select_1=select_1, select_2=select_2):
                return [*(attr for attr in select_1.attributes), select_2]
            case _:
                raise ValueError()
            
    @property
    def path(self) -> str:
        """
        The property path of the select in the form "prop_1.prop_2.prop_3".
        """
        return '.'.join(attr.label for attr in self.attributes)

    @property
    def target(self) -> Type[B]:
        """
        The target type
        """
        match self:
            case PropSelect():
                return self.target
            case LinkedSelect(select_2=select_2):
                return select_2.target
            case _:
                raise ValueError()

    @property
    def origin(self) -> Type[A]:
        """
        The origin type
        """
        return self.attributes[0].origin

    def get_safe(self, target: Selectable | Dict[str, Any]) -> SelectValue[B]:
        """
        Retrieve the selected value from potentially incomplete data. Returns an empty `SelectValue` if the value is inaccessible due to invalid data.
        """
        try:
            return self.get_unsafe(target)
        except ValueError:
            return SelectValue(None, True, False)
    
    def get_unsafe(self, target: Selectable | Dict[str, Any]) -> SelectValue[B]:
        """
        Retrieve the selected value from potentially incomplete data. Raises `ValueError` if the value is inaccessible due to invalid data.
        """

        match self:
            case PropSelect():
                if isinstance(target, Selectable):
                    try:
                        result = getattr(target, self.label)
                    except AttributeError:
                        if self.is_opt:
                            result = None
                        else:
                            raise ValueError(f'Unexpected empty value for required property {self.label}')
                elif isinstance(target, dict):
                    result = target.get(self.label)
                else:
                    raise ValueError(f'Value must be model or dict')
                if result is None and not self.is_opt:
                    raise ValueError(f'Unexpected empty value for attribute {self.label}')
                if result is not None and self.is_arr and not isinstance(result, list):
                    raise ValueError(f'Array selector returned non-array value: {result}')
                return SelectValue(result, self.is_opt, self.is_arr)
            case LinkedSelect(select_1=select_1, select_2=select_2):
                result = select_1.get_unsafe(target).flat_map(lambda b: select_2.get_unsafe(b))
                return result
            case _:
                raise ValueError()

    def get(self, target: A) -> SelectValue[B]:
        """
        Retrieve the selected value from complete, validated data.
        """
        
        match self:
            case PropSelect():
                if isinstance(target, Selectable):
                    result = getattr(target, self.label)
                elif isinstance(target, dict):
                    result = target.get(self.label)
                else:
                    raise ValueError(f'Value must be model or dict')
                if result is None and not self.is_opt:
                    raise ValueError(f'Unexpected empty value for attribute {self.label}')
                if result is not None and self.is_arr and not isinstance(result, list):
                    raise ValueError(f'Array selector returned non-array value: {result}')
                return SelectValue(result, self.is_opt, self.is_arr)
            case LinkedSelect(select_1=select_1, select_2=select_2):
                result = select_1.get(target).flat_map(lambda b: select_2.get(b))
                return result
            case _:
                raise ValueError()

    def set_safe(self, target: Selectable | Dict[str, Any], value: B):
        """
        Set the selected value within potentially incomplete data. Does nothing if the value cannot be set due to invalid data.

        For array selectors, this will set every existing element in the array to the new value. To set an array value as a whole,
        use a non-array selector, typically by converting a `PropArr[A]` to a `Prop[List[A]]` via the `value` method.
        """

        match self:
            case PropSelect():
                if self.is_arr:
                    list_value = self.get_safe(target).as_list
                    updated: Any = [value for _ in list_value]
                else:
                    updated = value
                if isinstance(target, Selectable):
                    setattr(target, self.label, updated)
                elif isinstance(target, dict):
                    target[self.label] = updated
                else:
                    return
            case LinkedSelect(select_1=select_1, select_2=select_2):
                select_1.get_safe(target).for_each(lambda b: select_2.set_safe(b, value))
            case _:
                raise ValueError()

    def set_unsafe(self, target: Selectable | Dict[str, Any], value: B):
        """
        Set the selected value within potentially incomplete data. Raises `ValueError` if the value cannot be set due to invalid data.

        For array selectors, this will set every existing element in the array to the new value. To set an array value as a whole,
        use a non-array selector, typically by converting a `PropArr[A]` to a `Prop[List[A]]` via the `value` method.
        """

        match self:
            case PropSelect():
                if self.is_arr:
                    list_value = self.get_unsafe(target).as_list
                    updated: Any = [value for _ in list_value]
                else:
                    updated = value
                if isinstance(target, Selectable):
                    setattr(target, self.label, updated)
                elif isinstance(target, dict):
                    target[self.label] = updated
                else:
                    raise ValueError(f'Value must be model or dict')
            case LinkedSelect(select_1=select_1, select_2=select_2):
                select_1.get_unsafe(target).for_each(lambda b: select_2.set_unsafe(b, value))
            case _:
                raise ValueError()

    def set(self, target: A, value: B):
        """
        Set the selected value within complete, validated data.

        For array selectors, this will set every existing element in the array to the new value. To set an array value as a whole,
        use a non-array selector, typically by converting a `PropArr[A]` to a `Prop[List[A]]` via the `value` method.
        """

        match self:
            case PropSelect():
                if self.is_arr:
                    list_value = self.get(target).as_list
                    updated: Any = [value for _ in list_value]
                else:
                    updated = value
                if isinstance(target, Selectable):
                    setattr(target, self.label, updated)
                else:
                    raise ValueError(f'Value must be model')
            case LinkedSelect(select_1=select_1, select_2=select_2):
                select_1.get(target).for_each(lambda b: select_2.set(b, value))
            case _:
                raise ValueError()

    def update_safe(self, target: Selectable | Dict[str, Any], fn: Callable[[B], B]):
        """
        Update any and every selected element within potentially incomplete data. Does nothing if the value cannot be set due to invalid data.

        For array selectors, this will update every element in every array the selector targets. For non-array selectors, it will update elements
        if they are not None.
        """

        match self:
            case PropSelect():
                select_value = self.get_safe(target)
                updated = select_value.map(fn)
                if isinstance(target, Selectable):
                    setattr(target, self.label, updated.value)
                elif isinstance(target, dict):
                    target[self.label] = updated.value
                else:
                    return
            case LinkedSelect(select_1=select_1, select_2=select_2):
                select_1.get_safe(target).for_each(lambda b: select_2.update_safe(b, fn))
            case _:
                raise ValueError()

    def update_unsafe(self, target: Selectable | Dict[str, Any], fn: Callable[[B], B]):
        """
        Update any and every selected element within potentially incomplete data. Raises a `ValueError` if the value cannot be set due to invalid data.

        For array selectors, this will update every element in every array the selector targets. For non-array selectors, it will update elements
        if they are not None.
        """

        match self:
            case PropSelect():
                select_value = self.get_unsafe(target)
                updated = select_value.map(fn)
                if isinstance(target, Selectable):
                    setattr(target, self.label, updated.value)
                elif isinstance(target, dict):
                    target[self.label] = updated.value
                else:
                    raise ValueError(f'Value must be model or dict')
            case LinkedSelect(select_1=select_1, select_2=select_2):
                select_1.get_unsafe(target).for_each(lambda b: select_2.update_unsafe(b, fn))
            case _:
                raise ValueError()

    def update(self, target: A, fn: Callable[[B], B]):
        """
        Update any and every selected element within valid, complete data.

        For array selectors, this will update every element in every array the selector targets. For non-array selectors, it will update elements
        if they are not None.
        """

        match self:
            case PropSelect():
                select_value = self.get(target)
                updated = select_value.map(fn)
                if isinstance(target, Selectable):
                    setattr(target, self.label, updated.value)
                else:
                    raise ValueError(f'Value must be model')
            case LinkedSelect(select_1=select_1, select_2=select_2):
                select_1.get(target).for_each(lambda b: select_2.update(b, fn))
            case _:
                raise ValueError()

    def clear_safe(self, target: Selectable | Dict[str, Any]):
        """
        Clear the selected value within incomplete data, even if this makes the data invalid with respect to the selector.
        Does nothing is selected value is unreachable due to invalid data.
        """

        match self:
            case PropSelect():
                if isinstance(target, Selectable):
                    setattr(target, self.label, None)
                elif isinstance(target, dict):
                    del target[self.label]
                else:
                    return
            case LinkedSelect(select_1=select_1, select_2=select_2):
                select_1.get_safe(target).for_each(lambda b: select_2.clear_safe(b))
            case _:
                raise ValueError()

    def clear_safe_strict(self, target: Selectable | Dict[str, Any]):
        """
        Clear the selected value within incomplete data, finding the closest optional or array property that it can clear.
        Clears optional properties by setting to None and clears array properties by setting to empty list.
        Does nothing is selected value is unreachable due to invalid data or if no property is clearable.
        """

        match self:
            case PropSelect():
                if not self.is_opt and not self.is_arr:
                    return
                if isinstance(target, Selectable):
                    if self.is_opt:
                        setattr(target, self.label, None)
                    else:
                        setattr(target, self.label, [])
                elif isinstance(target, dict):
                    if self.is_opt:
                        del target[self.label]
                    else:
                        target[self.label] = []
                else:
                    return
            case LinkedSelect():
                current_select: Select[A, Any] = self
                while True:
                    match current_select:
                        case PropSelect():
                            return
                        case PropSelect():
                            return current_select.clear_safe_strict(target)
                        case LinkedSelect(select_1=select_1, select_2=select_2):
                            if select_2.is_opt or select_2.is_arr:
                                return select_1.get_safe(target).for_each(lambda b: select_2.clear_safe_strict(b))
                            current_select = select_1
            case _:
                raise ValueError()

    def clear_unsafe(self, target: Selectable | Dict[str, Any]):
        """
        Clear the selected value within incomplete data, even if this makes the data invalid with respect to the selector.
        Raises a value error if selected value is unreachable due to invalid data.
        """
        match self:
            case PropSelect():
                if isinstance(target, Selectable):
                    setattr(target, self.label, None)
                elif isinstance(target, dict):
                    del target[self.label]
                else:
                    return
            case LinkedSelect(select_1=select_1, select_2=select_2):
                select_1.get_unsafe(target).for_each(lambda b: select_2.clear_unsafe(b))
            case _:
                raise ValueError()

    def clear_unsafe_strict(self, target: Selectable | Dict[str, Any]):
        """
        Clear the selected value within incomplete data, finding the closest optional or array property that it can clear.
        Clears optional properties by setting to None and clears array properties by setting to empty list.
        Raises a value error if selected value is unreachable due to invalid data.
        """
        match self:
            case PropSelect():
                if not self.is_opt and not self.is_arr:
                    raise ValueError('Selector does not contain required property')
                if isinstance(target, Selectable):
                    if self.is_opt:
                        setattr(target, self.label, None)
                    else:
                        setattr(target, self.label, [])
                elif isinstance(target, dict):
                    if self.is_opt:
                        del target[self.label]
                    else:
                        target[self.label] = []
                else:
                    raise ValueError(f'Value must be model or dict')
            case LinkedSelect():
                current_select: Select[A, Any] = self
                while True:
                    match current_select:
                        case PropSelect():
                            raise ValueError(
                                f'Unable to clear value: selector path `{self.path}` does not contain clearable element')
                        case PropSelect():
                            return current_select.clear_unsafe_strict(target)
                        case LinkedSelect(select_1=select_1, select_2=select_2):
                            if select_2.is_opt or select_2.is_arr:
                                return select_1.get_unsafe(target).for_each(lambda b: select_2.clear_unsafe(b))
                            current_select = select_1
            case _:
                raise ValueError()

    def clear(self, target: A):
        """
        Clear the selected value within complete, validated data, finding the closest optional or array property that it can clear.
        Clears optional properties by setting to None and clears array properties by setting to empty list.
        """
        match self:
            case PropSelect():
                if not self.is_opt and not self.is_arr:
                    raise ValueError('Selector does not contain required property')
                if isinstance(target, Selectable):
                    if self.is_opt:
                        setattr(target, self.label, None)
                    else:
                        setattr(target, self.label, [])
                elif isinstance(target, dict):
                    if self.is_opt:
                        del target[self.label]
                    else:
                        target[self.label] = []
                else:
                    raise ValueError(f'Value must be model or dict')
            case LinkedSelect():
                current_select: Select[A, Any] = self
                while True:
                    match current_select:
                        case PropSelect():
                            raise ValueError(f'Unable to clear value: selector path `{self.path}` does not contain clearable element')
                        case PropSelect():
                            return current_select.clear(target)
                        case LinkedSelect(select_1=select_1, select_2=select_2):
                            if select_2.is_opt or select_2.is_arr:
                                return select_1.get(target).for_each(lambda b: select_2.clear(b))
                            current_select = select_1
            case _:
                raise ValueError()

    def copy_to_safe(self, source: Selectable | Dict[str, Any], target: Dict[str, Any]):
        """
        Copies selected value from a potentially incomplete data source to a dict target. Preserves
        intermediate data structures, while only copying selected properties. Overwrites existing properties.
        Does nothing if selected data cannot be accessed due to invalid data in source. 
        """
        match self:
            case PropSelect():
                value = self.get_safe(source).value
                target[self.label] = value
            case LinkedSelect(select_1=select_1, select_2=select_2):
                current_target = target
                current_sel_1: Select[Any, Any] = select_1
                current_sel_2: Select[Any, Any] = select_2
                while True:
                    match current_sel_1:
                        case LinkedSelect(select_1=select_1a, select_2=select_2a):
                            current_sel_1 = select_1a
                            current_sel_2 = select_2a(current_sel_2)
                        case PropSelect():
                            value = current_sel_1.get_safe(source)
                            if current_sel_1.label not in current_target or not isinstance(current_target[current_sel_1.label], dict):
                                current_target[current_sel_1.label] = {}
                            return value.for_each(lambda b: current_sel_2.copy_to_safe(b, current_target[current_sel_1.label]))
            case _:
                raise ValueError()

    def copy_to_unsafe(self, source: Selectable | Dict[str, Any], target: Dict[str, Any]):
        """
        Copies selected value from a potentially incomplete data source to a dict target. Preserves
        intermediate data structures, while only copying selected properties. Overwrites existing properties.
        Raises `ValueError` if selected data cannot be accessed due to invalid data in source. 
        """

        match self:
            case PropSelect():
                value = self.get_unsafe(source).value
                target[self.label] = value
            case LinkedSelect(select_1=select_1, select_2=select_2):
                current_target = target
                current_sel_1: Select[Any, Any] = select_1
                current_sel_2: Select[Any, Any] = select_2
                while True:
                    match current_sel_1:
                        case LinkedSelect(select_1=select_1a, select_2=select_2a):
                            current_sel_1 = select_1a
                            current_sel_2 = select_2a(current_sel_2)
                        case PropSelect():
                            value = current_sel_1.get_unsafe(source)
                            if current_sel_1.label not in current_target or not isinstance(current_target[current_sel_1.label], dict):
                                current_target[current_sel_1.label] = {}
                            return value.for_each(lambda b: current_sel_2.copy_to_unsafe(b, current_target[current_sel_1.label]))
            case _:
                raise ValueError()

    def copy_to(self, source: A, target: Dict[str, Any]):
        """
        Copies selected value from a complete, validated data source to a dict target. Preserves
        intermediate data structures, while only copying selected properties. Overwrites existing properties.
        """
        match self:
            case PropSelect():
                value = self.get(source).value
                target[self.label] = value
            case LinkedSelect(select_1=select_1, select_2=select_2):
                current_target = target
                current_sel_1: Select[Any, Any] = select_1
                current_sel_2: Select[Any, Any] = select_2
                while True:
                    match current_sel_1:
                        case LinkedSelect(select_1=select_1a, select_2=select_2a):
                            current_sel_1 = select_1a
                            current_sel_2 = select_2a(current_sel_2)
                        case PropSelect():
                            value = current_sel_1.get(source)
                            if current_sel_1.label not in current_target or not isinstance(current_target[current_sel_1.label], dict):
                                current_target[current_sel_1.label] = {}
                            return value.for_each(lambda b: current_sel_2.copy_to(b, current_target[current_sel_1.label]))
            case _:
                raise ValueError()


class SelectVal(Generic[A, B], Select[A, B]):
    def get_val_safe(self, value: Selectable | Dict[str, Any]) -> B | None:
        """
        Get value directly (i.e., without wrapping in `SelectValue`) from potentially incomplete data source. Returns None if value is missing.
        """
        return self.get_safe(value).as_opt

    def get_val_unsafe(self, value: Selectable | Dict[str, Any]) -> B:
        """
        Get value directly (i.e., without wrapping in `SelectValue`) from potentially incomplete data source. Raises `ValueError` if value is missing.
        """
        result = self.get_unsafe(value).value # type: ignore
        if result is None:
            raise ValueError('Unexpected empty value')
        return cast(B, result)

    def get_val(self, value: A) -> B:
        """
        Get value directly (i.e., without wrapping in `SelectValue`) from complete, validated data.
        """
        return self.get(value).value # type: ignore

    def then_val(self, next: SelectVal[B, C]) -> SelectVal[A, C]:
        """
        Compose with another `SelectVal` to produce a linked `SelectVal`. Use this to preserve access to `get_val` and its variants.
        """
        match next:
            case Prop():
                return LinkedSelectVal(self, next)
            case LinkedSelectVal(select_1=select_1, select_2=select_2):
                return LinkedSelectVal(self(select_1), select_2)
            case _:
                raise ValueError()
    
    def then_opt(self, next: SelectOpt[B, C]) -> SelectOpt[A, C]:
        """
        Compose with a `SelectOpt` to produce a linked `SelectOpt`. Use this to preserve access to `get_val` and its variants.
        """
        match next:
            case PropOpt():
                return LinkedSelectOpt(self, next)
            case LinkedSelectOpt(select_1=select_1, select_2=select_2):
                return LinkedSelectOpt(self(select_1), select_2)
            case _:
                raise ValueError()
    
    def then_arr(self, next: SelectArr[B, C]) -> SelectArr[A, C]:
        """
        Compose with a `SelectArr` to produce a linked `SelectArr`. Use this to preserve access to `get_val` and its variants.
        """
        match next:
            case PropArr():
                return LinkedSelectArr(self, next)
            case LinkedSelectArr(select_1=select_1, select_2=select_2):
                return LinkedSelectArr(self(select_1), select_2)
            case _:
                raise ValueError()
    
    def then_opt_arr(self, next: SelectOptArr[B, C]) -> SelectOptArr[A, C]:
        """
        Compose with a `SelectOptArr` to produce a linked `SelectOptArr`. Use this to preserve access to `get_val` and its variants.
        """
        match next:
            case PropOptArr():
                return LinkedSelectOptArr(self, next)
            case LinkedSelectOptArr(select_1=select_1, select_2=select_2):
                return LinkedSelectOptArr(self(select_1), select_2)
            case _:
                raise ValueError()

class SelectOpt(Generic[A, B], Select[A, B]):
    def get_val_safe(self, value: Selectable | Dict[str, Any]) -> B | None:
        """
        Get value directly (i.e., without wrapping in `SelectValue`) from potentially incomplete data source. Returns None if value is missing due to invalid data.
        """
        return self.get_safe(value).as_opt

    def get_val_unsafe(self, value: Selectable | Dict[str, Any]) -> B | None:
        """
        Get value directly (i.e., without wrapping in `SelectValue`) from potentially incomplete data source. Raises `ValueError` if value is missing due to invalid data.
        """
        return self.get_unsafe(value).value # type: ignore

    def get_val(self, value: A | Dict[str, Any]) -> B | None:
        """
        Get value directly (i.e., without wrapping in `SelectValue`) from complete, validated data.
        """
        return self.get(value).value # type: ignore

    def then_val(self, next: SelectVal[B, C]) -> SelectOpt[A, C]:
        """
        Compose with a `SelectVal` to produce a linked `SelectOpt`. Use this to preserve access to `get_val` and its variants.
        """
        match next:
            case Prop():
                return LinkedSelectOpt(self, next)
            case LinkedSelectVal(select_1=select_1, select_2=select_2):
                return LinkedSelectOpt(self(select_1), select_2)
            case _:
                raise ValueError()
    
    def then_opt(self, next: SelectOpt[B, C]) -> SelectOpt[A, C]:
        """
        Compose with another `SelectOpt` to produce a linked `SelectOpt`. Use this to preserve access to `get_val` and its variants.
        """
        match next:
            case PropOpt():
                return LinkedSelectOpt(self, next)
            case LinkedSelectOpt(select_1=select_1, select_2=select_2):
                return LinkedSelectOpt(self(select_1), select_2)
            case _:
                raise ValueError()
    
    def then_arr(self, next: SelectArr[B, C]) -> SelectOptArr[A, C]:
        """
        Compose with a `SelectArr` to produce a linked `SelectOptArr`. Use this to preserve access to `get_val` and its variants.
        """
        match next:
            case PropArr():
                return LinkedSelectOptArr(self, next)
            case LinkedSelectArr(select_1=select_1, select_2=select_2):
                return LinkedSelectOptArr(self(select_1), select_2)
            case _:
                raise ValueError()
    
    def then_opt_arr(self, next: SelectOptArr[B, C]) -> SelectOptArr[A, C]:
        """
        Compose with a `SelectOptArr` to produce a linked `SelectOptArr`. Use this to preserve access to `get_val` and its variants.
        """
        match next:
            case PropOptArr():
                return LinkedSelectOptArr(self, next)
            case LinkedSelectOptArr(select_1=select_1, select_2=select_2):
                return LinkedSelectOptArr(self(select_1), select_2)
            case _:
                raise ValueError()

class SelectArr(Generic[A, B], Select[A, B]):
    def get_val_safe(self, value: Selectable | Dict[str, Any]) -> List[B]:
        """
        Get values directly (i.e., without wrapping in `SelectValue`) from potentially incomplete data source. Returns empty list if value is missing due to invalid data.
        """
        return self.get_safe(value).as_list

    def get_val_unsafe(self, value: Selectable | Dict[str, Any]) -> List[B]:
        """
        Get values directly (i.e., without wrapping in `SelectValue`) from potentially incomplete data source. Raises `ValueError` if value is missing due to invalid data.
        """
        result = self.get_unsafe(value).value # type: ignore
        if result is None:
            raise ValueError('Unexpected empty value')
        if not isinstance(result, list):
            raise ValueError('Retrieved non-list value')
        return result

    def get_val(self, value: A) -> List[B]:
        """
        Get values directly (i.e., without wrapping in `SelectValue`) from complete, validated data.
        """
        return self.get(value).value # type: ignore

    def then_val(self, next: SelectVal[B, C]) -> SelectArr[A, C]:
        """
        Compose with a `SelectVal` to produce a linked `SelectArr`. Use this to preserve access to `get_val` and its variants.
        """

        match next:
            case Prop():
                return LinkedSelectArr(self, next)
            case LinkedSelectVal(select_1=select_1, select_2=select_2):
                return LinkedSelectArr(self(select_1), select_2)
            case _:
                raise ValueError()

    def then_opt(self, next: SelectOpt[B, C]) -> SelectOptArr[A, C]:
        """
        Compose with a `SelectOpt` to produce a linked `SelectOptArr`. Use this to preserve access to `get_val` and its variants.
        """

        match next:
            case PropOpt():
                return LinkedSelectOptArr(self, next)
            case LinkedSelectOpt(select_1=select_1, select_2=select_2):
                return LinkedSelectOptArr(self(select_1), select_2)
            case _:
                raise ValueError()

    def then_arr(self, next: SelectArr[B, C]) -> SelectArr[A, C]:
        """
        Compose with a `SelectArr` to produce a linked `SelectArr`. Use this to preserve access to `get_val` and its variants.
        """

        match next:
            case PropArr():
                return LinkedSelectArr(self, next)
            case LinkedSelectArr(select_1=select_1, select_2=select_2):
                return LinkedSelectArr(self(select_1), select_2)
            case _:
                raise ValueError()
    
    def then_opt_arr(self, next: SelectOptArr[B, C]) -> SelectOptArr[A, C]:
        """
        Compose with a `SelectOptArr` to produce a linked `SelectOptArr`. Use this to preserve access to `get_val` and its variants.
        """

        match next:
            case PropOptArr():
                return LinkedSelectOptArr(self, next)
            case LinkedSelectOptArr(select_1=select_1, select_2=select_2):
                return LinkedSelectOptArr(self(select_1), select_2)
            case _:
                raise ValueError()

class SelectOptArr(Generic[A, B], Select[A, B]):
    def get_val_safe(self, value: Selectable | Dict[str, Any]) -> List[B] | None:
        """
        Get values (or empty value) directly (i.e., without wrapping in `SelectValue`) from potentially incomplete data source.
        Returns None if value is missing due to invalid data.
        """

        result = self.get_safe(value).value
        if result is not None and not isinstance(result, list):
            return None
        return result

    def get_val_unsafe(self, value: Selectable | Dict[str, Any]) -> List[B] | None:
        """
        Get values (or empty value) directly (i.e., without wrapping in `SelectValue`) from potentially incomplete data source.
        Raises a `ValueError` if value is missing due to invalid data.
        """
        result = self.get_unsafe(value).value
        if result is not None and not isinstance(result, list):
            raise ValueError('Unexpected non-list value')
        return result

    def get_val(self, value: A) -> List[B] | None:
        """
        Get values (or empty value) directly (i.e., without wrapping in `SelectValue`) from complete, validated data source.
        """
        return self.get(value).value # type: ignore

    def get_arr_safe(self, value: Selectable | Dict[str, Any]) -> List[B]:
        """
        Get values (or empty value) directly (i.e., without wrapping in `SelectValue`) from potentially incomplete data source,
        converting an empty result to an empty list. Returns an empty list if values are missing due to invalid data.
        """
        return self.get_safe(value).as_list

    def get_arr_unsafe(self, value: Selectable | Dict[str, Any]) -> List[B]:
        """
        Get values (or empty value) directly (i.e., without wrapping in `SelectValue`) from potentially incomplete data source,
        converting an empty result to an empty list. Raises a `ValueError` if values are missing due to invalid data.
        """
        res = self.get_unsafe(value).value
        if res is not None and not isinstance(res, list):
            raise ValueError('Unexpected non-list value')
        return cast(List[B], res)

    def get_arr(self, value: A) -> List[B]:
        """
        Get values (or empty value) directly (i.e., without wrapping in `SelectValue`) from potentially incomplete data source,
        converting an empty result to an empty list.
        """
        return self.get_val(value) or [] # type: ignore

    def then(self, next: Select[B, C]) -> SelectOptArr[A, C]:
        """
        Compose with any `Select` to produce a linked `SelectOptArr`. Use this to preserve access to `get_val` and its variants.
        """

        match next:
            case PropSelect():
                return LinkedSelectOptArr(self, next)
            case LinkedSelectArr(select_1=select_1, select_2=select_2):
                return LinkedSelectOptArr(self(select_1), select_2)
            case _:
                raise ValueError()

@dataclass(frozen=True)
class PropSelect(Generic[A, B], Select[A, B]):
    __label: str
    __origin: Type[A]
    __target: Type[B]
    __data: Dict[str, Any]
    __is_opt: bool
    __is_arr: bool

    def __init__(self, l: str, o: Type[A], t: Type[B], d: Dict[str, Any], io: bool, ia: bool):
        raise NotImplementedError('Abstract base class AttributeSelect should not be implemented directly')
    
    @property
    def label(self) -> str:
        """
        Property name, corresponding to attribute or key in an in-memory data source, or a field in a databases
        """
        return self.__label
    
    @property
    def data(self) -> Dict[str, Any]:
        """
        Arbitrary data attached to the selector. Can be used for integrations.
        """
        return self.__data

    @property
    def is_opt(self) -> bool:
        """
        Whether the property is optional
        """
        return self.__is_opt

    @property
    def is_arr(self) -> bool:
        """
        Whether the property is an array (or `List`) type
        """
        return self.__is_arr
    
    @property
    def target(self) -> Type[B]:
        return self.__target
    
    @property
    def origin(self) -> Type[A]:
        return self.__origin

    @classmethod
    def val(cls, _label: str, _origin: Type[A], _target: Type[B], _data: Dict[str, Any]) -> Prop[A, B]:
        """
        Manually construct a `Prop`
        """
        return Prop(_label, _origin, _target, _data, False, False) # type: ignore
    
    @classmethod
    def opt(cls, _label: str, _origin: Type[A], _target: Type[B], _data: Dict[str, Any]) -> PropOpt[A, B]:
        """
        Manually construct a `PropOpt`
        """
        return PropOpt(_label, _origin, _target, _data, True, False) # type: ignore
    
    @classmethod
    def arr(cls, _label: str, _origin: Type[A], _target: Type[B], _data: Dict[str, Any]) -> PropArr[A, B]:
        """
        Manually construct a `PropArr`
        """
        return PropArr(_label, _origin, _target, _data, False, True) # type: ignore
    
    @classmethod
    def opt_arr(cls, _label: str, _origin: Type[A], _target: Type[B], _data: Dict[str, Any]) -> PropOptArr[A, B]:
        """
        Manually construct a `PropOptArr`
        """
        return PropOptArr(_label, _origin, _target, _data, True, True) # type: ignore

@dataclass(frozen=True)
class Prop(Generic[A, B], SelectVal[A, B], PropSelect[A, B]):
    """
    A required, non-array property
    """
    _is_opt = False
    _is_arr = False

@dataclass(frozen=True)
class PropOpt(Generic[A, B], PropSelect[A, B], SelectOpt[A, B]):
    """
    An optional, non-array property
    """
    _is_opt = True
    _is_arr = False

    @property
    def value(self) -> Prop[A, Optional[B]]:
        """
        A "required" version of the optional property, exposing the optional union as the target type. Limited composition, but can provide greater
        control when setting/updating/clearing values.
        """
        return Prop(self.label, self.origin, Optional[self.target], self.data, False, False) # type: ignore

@dataclass(frozen=True)
class PropArr(Generic[A, B], PropSelect[A, B], SelectArr[A, B]):
    """
    A required, array (or `List`) property
    """
    @property
    def value(self) -> Prop[A, List[B]]:
        """
        A non-array version of the array property, exposing `List` in the target type. Limited composition, but can provide greater
        control when setting/updating/clearing values.
        """
        return Prop(self.label, self.origin, List[self.target], self.data, False, False) # type: ignore

@dataclass(frozen=True)
class PropOptArr(Generic[A, B], PropSelect[A, B], SelectOptArr[A, B]):
    """
    An optional, array (or `List`) property
    """
    @property
    def option(self) -> Prop[A, List[B]]:
        """
        An optional, non-array version of the array property, exposing the `List` in the target type. 
        Limited composition, but can provide greater control when setting/updating/clearing values.
        """
        return Prop(self.label, self.origin, List[self.target], self.data, False, False) # type: ignore

    @property
    def value(self) -> Prop[A, List[B] | None]:
        """
        A non-optional, non-array version of the array property, exposing both the optional union and `List` in the target type. 
        Limited composition, but can provide greater control when setting/updating/clearing values.
        """
        return Prop(self.label, self.origin, Optional[List[self.target]], self.data, False, False) # type: ignore

@dataclass(frozen=True)
class LinkedSelect(Generic[A, B, C], Select[A, C]):
    select_1: Select[A, B]
    select_2: PropSelect[B, C]

@dataclass(frozen=True)
class LinkedSelectVal(Generic[A, B, C], LinkedSelect[A, B, C], SelectVal[A, C]):
    ...

@dataclass(frozen=True)
class LinkedSelectOpt(Generic[A, B, C], LinkedSelect[A, B, C], SelectOpt[A, C]):
    ...

@dataclass(frozen=True)
class LinkedSelectArr(Generic[A, B, C], LinkedSelect[A, B, C], SelectArr[A, C]):
    ...

@dataclass(frozen=True)
class LinkedSelectOptArr(Generic[A, B, C], LinkedSelect[A, B, C], SelectOptArr[A, C]):
    ...
