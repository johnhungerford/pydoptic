
from inspect import isclass
from typing import Any, Dict, List, Type, TypeVar, cast

from pydoptic.selector import ModelLike

from types import NoneType
from typing import Type, Annotated, Any, Tuple, get_origin, get_args, Union, Optional, Callable

A = TypeVar('A')

def unwrap(value: A | None) -> A:
    if value is not None:
        return value
    raise ValueError(f'Unexpected empty value!')


def decompose_optional_type(typ: Type[Any]) -> Type[Any] | None:
    if get_origin(typ) is Union and NoneType in (typ_args := get_args(typ)):
        if len(typ_args) == 2:
            typ = next(iter(a for a in typ_args if a is not NoneType))
        else:
            typ = Union[tuple([a for a in typ_args if a is not NoneType])]  # type: ignore[assignment]
        return typ
    return None

def decompose_list_type(typ: Type[Any]) -> Type[Any] | None:
    """Returns whether the type was a list and the type of the list items (or the original type)."""
    if get_origin(typ) is list:
        return cast(Type[Any], get_args(typ)[0])
    return None

def decompose_annotated_type (typ: Type[Any]) -> Type[Any] | None:
    """Returns whether the type was an annotation, and the type being annotated (or the original type)"""
    if get_origin(typ) is Annotated:
        return cast(Type[Any], get_args(typ)[0])
    return None

Validator = Callable[[Any], str | None]
"""
Validate a value, returning None if valid and an error message if invalid
"""

def validate_type(is_opt: bool, is_arr: bool, selector_target: Type[Any], value: Any, validators: Dict[Type[Any], Validator]) -> str | None:
    if selector_target in validators:
        return validators[selector_target](value)

    value_type = type(value)

    if value is None:
        if is_opt:
            return None
    
    if is_arr:
        list_target_type_1 = List[selector_target] # type: ignore
        if list_target_type_1 in validators:
            return validators[list_target_type_1](value)
        list_target_type_2 = list[selector_target] # type: ignore
        if list_target_type_2 in validators:
            return validators[list_target_type_2](value)
        if not isinstance(value, list):
            return f'expected array value: {value}'
        if len(value) < 1:
            return None
        for i, v in enumerate(value):
            msg = validate_type(False, False, selector_target, v, validators)
            if msg is not None:
                return f'invalid element in array at position {i + 1}: {msg}'
        return None
    
    if selector_target is value_type:
        return None
    
    selector_target_in_opt = decompose_optional_type(selector_target)
    if selector_target_in_opt is not None:
        if value is None:
            return None
        return validate_type(False, False, selector_target_in_opt, value, validators)
    
    if value is None:
        return 'expected non-empty value'
    
    selector_target_in_list = decompose_list_type(selector_target)
    if selector_target_in_list is not None:
        if isinstance(value, list):
            if len(value) < 1:
                return None
            for v in value:
                res = validate_type(False, False, selector_target_in_list, v, validators)
                if res is not None:
                    return res
            return None
        return f'expected a List[{selector_target_in_list}], found {value_type}'
    
    selector_target_in_annot = decompose_annotated_type(selector_target)
    if selector_target_in_annot is not None:
        return validate_type(is_opt, False, selector_target_in_annot, value, validators)

    if isclass(selector_target):
        if not isclass(value_type) or not issubclass(value_type, selector_target):
            return f'expected instance of class {selector_target.__name__}: {value_type}'
        return None

    return f'unable to check if value {value} is instance of {selector_target}'
