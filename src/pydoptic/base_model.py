from __future__ import annotations
from pydoptic.selector import Select, AttributeSelect, SelectVal, SelectOpt, SelectArr, SelectOptArr, Selectable, SelectValue, A, B

from dataclasses import dataclass
from inspect import isclass
from typing import Any, Callable, Dict, Generic, List, Self, Set, Type, TypeVar, TypedDict, get_args, get_origin, get_type_hints

from pydoptic.validate_types import validate_type, Validator


@dataclass(frozen=True)
class SelectProxy(Generic[B]):
    name: str | None
    data: Dict[str, Any]

def select(name: str | None = None, **data) -> Any:
    return SelectProxy(name=name, data=data)

def _selector_from_select_proxy(name: str, select_type: Type[Select[Any, Any]], origin: Type[Any], target: Type[Any], proxy: SelectProxy) -> AttributeSelect[Any, Any]:
    if issubclass(select_type, SelectVal):
        return AttributeSelect.val(proxy.name or name, origin, target, proxy.data) # type: ignore
    if issubclass(select_type, SelectOpt):
        return AttributeSelect.opt(proxy.name or name, origin, target, proxy.data) # type: ignore
    if issubclass(select_type, SelectArr):
        return AttributeSelect.arr(proxy.name or name, origin, target, proxy.data) # type: ignore
    if issubclass(select_type, SelectOptArr):
        return AttributeSelect.opt_arr(proxy.name or name, origin, target, proxy.data) # type: ignore
    
    raise ValueError(f'Unsupported subtype of Select: {select_type.__name__}. Use Prop, PropOpt, PropArr, or PropOptArr')


class BaseModelMeta(type):
    def __getattribute__(cls, name_to_get: str):
        if cls is not BaseModel:
            try:
                _selectors: Dict[Type[Any], Dict[str, AttributeSelect[Any, Any]]] = type.__getattribute__(cls, '_selectors')
            except AttributeError:
                _selectors = {}
                setattr(cls, '_selectors', {})

            if cls not in _selectors:
                selectors: Dict[str, AttributeSelect[Any, Any]] = {}
                _selectors[cls] = selectors

                cls_name = cls.__name__
                type_hints = get_type_hints(cls, include_extras=True)
                print(type_hints)
                for name, _type in type_hints.items():
                    origin = get_origin(_type)
                    type_params = get_args(_type)
                    if isclass(origin) and issubclass(origin, Select):
                        assert len(type_params) > 1, f'Selector {name} on model {cls_name} is missing one or more of the three required type paramaters: {_type}'
                        assert len(type_params) == 2, f'Selector {name} on model {cls_name} has more than three type paramaters: {_type}'
                        assert issubclass(cls, type_params[0]), f'Selector {name} on model {cls_name} selects from {type_params[0]} instead of {cls_name}: {_type}'
                        target = type_params[1]
                        given_selector: Any | None = None
                        if hasattr(cls, name):
                            given_selector = getattr(cls, name)
                            if given_selector is not None:
                                if isinstance(given_selector, SelectProxy):
                                    selector = _selector_from_select_proxy(name, origin, cls, target, given_selector)
                                elif isinstance(given_selector, AttributeSelect):
                                    selector = given_selector
                                else:
                                    raise ValueError(f'Invalid selector assigned to {name}: {given_selector}')
                            else:
                                raise ValueError(f'To configure a selector on {cls_name} use select(), select_opt(), select_arr(), or select_arr()')
                        else:
                            selector = _selector_from_select_proxy(name, origin, cls, target, SelectProxy(None, {}))
                        setattr(cls, name, selector)
                        selectors[selector._label] = selector

        return type.__getattribute__(cls, name_to_get)

def _fully_validate(target: Type[M], value: Any, validators: Dict[Type[Any], Validator]) -> M:
    if isinstance(value, target):
        return value
    elif isinstance(value, PartialModel):
        if not issubclass(value.model, target):
            raise ValueError(f'received partial model of {value.model} instead of expected model {target}')
        return target(**value.as_mapping, _allow_extra_args=True, _validators=validators)
    elif isinstance(value, dict):
        return target(**value, _validators=validators)
    else:
        raise ValueError(f'expected type {target.__name__} (or dict) but received: {type(value).__name__}.')

class BaseModel(Selectable, metaclass=BaseModelMeta):
    _selectors: Dict[Type[Any], Dict[str, AttributeSelect[Any, Any]]]
    validators: Dict[Type[Any], Validator]

    @classmethod
    def selectors(cls) -> Dict[str, AttributeSelect[Any, Any]]:
        return cls._selectors[cls]

    @classmethod
    def partial(cls, **kwargs) -> PartialModel[Self]:
        return PartialModel(cls, **kwargs)

    @classmethod
    def construct_partial(cls, values: Dict[AttributeSelect[Self, Any], Any], **kwargs) -> PartialModel[Self]:
        return PartialModel(cls, **{sel._label: val for sel, val in values.items()}, **kwargs)

    @classmethod
    def construct(cls, values: Dict[AttributeSelect[Self, Any], Any], **kwargs) -> Self:
        return cls(**{sel._label: val for sel, val in values.items()}, **kwargs)

    def as_partial(self) -> PartialModel[Self]:
        return PartialModel(self.__class__, **self.as_mapping)

    def __init__(self, **kwargs):
        self._dict: Dict[str, Any] = {}
        allow_extra_args = kwargs.get('_allow_extra_args', False)
        if '_allow_extra_args' in kwargs:
            del kwargs['_allow_extra_args']
        validators = getattr(self.__class__, 'validators', {})
        if '_validators' in kwargs:
            validators.update(kwargs['_validators'])
            del kwargs['_validators']
        for selector in self.__class__.selectors().values():
            if selector._label not in kwargs and not selector._is_opt:
                raise ValueError(f'Missing required parameter {selector._label}')
            if selector._label not in kwargs:
                setattr(self, selector._label, None)
            else:
                value = kwargs[selector._label]
                del kwargs[selector._label]
                if value is None and not selector._is_opt:
                    raise ValueError(f'Received empty value for required parameter {selector._label}')
                if value is None:
                    setattr(self, selector._label, None)
                else:
                    if isclass(selector.target) and issubclass(selector.target, BaseModel):
                        if selector._is_arr:
                            if not isinstance(value, list):
                                raise ValueError(f'Received non-array value for array field {selector._label}')
                            updated_values = []
                            for i, v in enumerate(value):
                                try:
                                    updated_values.append(_fully_validate(selector.target, v, validators))
                                except ValueError as ve:
                                    raise ValueError(f'Property {selector._label} contains invalid element at index {i}: {ve}')
                            self._dict[selector._label] = updated_values
                            setattr(self, selector._label, updated_values)
                        else:
                            try:
                                valid_value = _fully_validate(selector.target, value, validators)
                                self._dict[selector._label] = valid_value
                                setattr(self, selector._label, valid_value)     
                            except ValueError as ve:
                                raise ValueError(f'Invalid property {selector._label}: {ve}')            
                    else:
                        error_message = validate_type(selector._is_opt, selector._is_arr, selector.target, value, validators)
                        if error_message is not None:
                            message = f'Invalid property {selector._label}: {error_message}'
                            raise ValueError(message)
                        self._dict[selector._label] = value
                        setattr(self, selector._label, value)      

        if not allow_extra_args:
            for k, v in kwargs.items():
                if k not in self.__class__.selectors():
                    raise ValueError(f'Unrecognized parameter {k} provided (value: {v})')

    def __repr__(self):
        return self.__class__.__name__ + '(' + ', '.join(f'{k}={v}' for k, v in self._dict.items()) + ')'

    def set_mapping(self, key, value):
        super().set_mapping(key, value)
        setattr(self, key, value)

    def select_partial(self, *selectors: Select[Self, Any]) -> PartialModel[Self]:
        data: Dict[str, Any] = {}
        for selector in selectors:
            selector.copy_to(self, data)
        return self.__class__.partial(**data)

def _partly_validate(target: Type[M], value: Any, validators: Dict[Type[Any], Validator]) -> M | PartialModel[M]:
    if isinstance(value, target):
        return value
    elif isinstance(value, PartialModel):
        if not issubclass(value.model, target):
            raise ValueError(f'received partial model of {value.model} instead of expected model {target}')
        return value
    elif isinstance(value, dict):
        return target.partial(**value, _validators=validators)
    else:
        raise ValueError(f'expected type {target.__name__} (or dict) but received: {type(value).__name__}.')

M = TypeVar('M', bound=BaseModel)

class PartialModel(Generic[M], Selectable):
    def as_model(self, **extra_args) -> M:
        return self.model(**self._dict, **extra_args)

    def construct_as_model(self, values: Dict[AttributeSelect[Self, Any], Any], **extra_args) -> M:
        return self.model(**{sel._label: val for sel, val in values.items()}, **self._dict, **extra_args)

    def __init__(self, model: Type[M], **kwargs):
        self.model = model
        validators = getattr(model, 'validators', {})
        if '__validators' in kwargs:
            validators.update(kwargs['__validators'])
            del kwargs['__validators']
        self._dict: Dict[str, Any] = {}
        for selector in model.selectors().values():
            if selector._label not in kwargs:
                setattr(self, selector._label, None)
                continue
            else:
                value = kwargs[selector._label]
                if value is None:
                    setattr(self, selector._label, None)
                else:
                    if isclass(selector.target) and issubclass(selector.target, BaseModel):
                        if selector._is_arr:
                            if not isinstance(value, list):
                                raise ValueError(f'Received non-array value for array field {selector._label}')
                            updated_values = []
                            for i, v in enumerate(value):
                                try:
                                    updated_values.append(_partly_validate(selector.target, v, validators))
                                except ValueError as ve:
                                    raise ValueError(f'Property {selector._label} contains invalid element at index {i}: {ve}')
                            self._dict[selector._label] = updated_values
                            setattr(self, selector._label, updated_values)
                        else:
                            try:
                                valid_value = _partly_validate(selector.target, value, validators)
                                self._dict[selector._label] = valid_value
                                setattr(self, selector._label, valid_value)     
                            except ValueError as ve:
                                raise ValueError(f'Invalid property {selector._label}: {ve}')            
                    else:
                        error_message = validate_type(selector._is_opt, selector._is_arr, selector.target, value, validators)
                        if error_message is not None:
                            message = f'Invalid property {selector._label}: {error_message}'
                            raise ValueError(message)
                        self._dict[selector._label] = value
                        setattr(self, selector._label, value)  

    def __repr__(self):
        return 'Partial' + self.model.__name__ + '(' + ', '.join(f'{k}={v}' for k, v in self._dict.items()) + ')'
    
    def select_partial(self, *selectors: Select[M, Any]) -> PartialModel[M]:
        data: Dict[str, Any] = {}
        for selector in selectors:
            selector.copy_to_safe(self, data)
        return self.model.partial(**data)
