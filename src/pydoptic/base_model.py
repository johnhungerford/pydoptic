from __future__ import annotations
from pydoptic.selector import Discrim, Param, Prop, Select, PropSelect, SelectVal, SelectOpt, SelectArr, SelectOptArr, ModelLike, SelectValue, A, B, Selectable

from dataclasses import dataclass
from inspect import isclass
from typing import Any, Callable, Dict, Generic, List, Self, Set, Type, TypeVar, TypedDict, get_args, get_origin, \
    get_type_hints, Mapping, Tuple

from pydoptic.validate_types import validate_type, Validator

X = TypeVar("X")
Y = TypeVar("Y")

@dataclass(frozen=True)
class SelectProxy(Generic[B]):
    name: str | None
    data: Dict[str, Any]

def select(name: str | None = None, **data) -> Any:
    return SelectProxy(name=name, data=data)

def _selector_from_select_proxy(name: str, select_type: Type[Select[Any, Any]], origin: Type[Any], target: Type[Any], proxy: SelectProxy) -> PropSelect[Any, Any]:
    if issubclass(select_type, SelectVal):
        return PropSelect.val(proxy.name or name, origin, target, proxy.data) # type: ignore
    if issubclass(select_type, SelectOpt):
        return PropSelect.opt(proxy.name or name, origin, target, proxy.data) # type: ignore
    if issubclass(select_type, SelectArr):
        return PropSelect.arr(proxy.name or name, origin, target, proxy.data) # type: ignore
    if issubclass(select_type, SelectOptArr):
        return PropSelect.opt_arr(proxy.name or name, origin, target, proxy.data) # type: ignore
    
    raise ValueError(f'Unsupported subtype of Select: {select_type.__name__}. Use Prop, PropOpt, PropArr, or PropOptArr')


class BaseModelMeta(type):
    def __new__(mcls, class_name, bases, dct: Dict[str, Any]):
        annos: Dict[str, Type[Any]] = dct.get('__annotations__', {})
        slots: List[str] = []
        print(dct.get('__slots__', None))
        dct['__slots__'] = slots
        for name, tpe in annos.items():
            if isclass(tpe) and issubclass(tpe, PropSelect):
                if name in dct:
                    given_prop = dct[name]
                    if isinstance(given_prop, SelectProxy):
                        slots.append(given_prop.name or name)
                    elif isinstance(given_prop, PropSelect):
                        slots.append(given_prop.label)
                    else:
                        slots.append(name)
        # Call the parent metaclass's __new__ to create the class
        return super().__new__(mcls, class_name, bases, dct)

    def __getattribute__(cls, name_to_get: str):
        if cls is not BaseModel:
            try:
                global_properties: Dict[Type[Any], Dict[str, PropSelect[Any, Any] | Discrim[Any, Any]]] = type.__getattribute__(BaseModel, '_properties')
            except AttributeError:
                global_properties = {}
                setattr(BaseModel, '_properties', {})

            if cls not in global_properties:
                properties: Dict[str, PropSelect[Any, Any] | Discrim[Any, Any]] = {}
                global_properties[cls] = properties

                cls_name = cls.__name__
                type_hints = get_type_hints(cls, include_extras=True)
                for name, _type in type_hints.items():
                    origin = get_origin(_type)
                    type_params = get_args(_type)
                    if isclass(origin) and issubclass(origin, PropSelect):
                        assert len(type_params) > 1, f'Selector {name} on model {cls_name} is missing one or more of the three required type paramaters: {_type}'
                        assert len(type_params) == 2, f'Selector {name} on model {cls_name} has more than three type paramaters: {_type}'
                        assert issubclass(cls, type_params[0]), f'Selector {name} on model {cls_name} selects from {type_params[0]} instead of {cls_name}: {_type}'
                        target = type_params[1]
                        if hasattr(cls, name):
                            given_selector: Any = getattr(cls, name)
                            if given_selector is not None:
                                if isinstance(given_selector, SelectProxy):
                                    if given_selector.name is not None and given_selector.name != name:
                                        if given_selector.name in type_hints:
                                            attr_typ = type_hints[given_selector.name]
                                            if not isclass(attr_typ) and issubclass(attr_typ, target):
                                                raise ValueError(f'Attribute {given_selector.name} with type {attr_typ.__name__} does not correspond to property {name} with type {target}')
                                    property = _selector_from_select_proxy(name, origin, cls, target, given_selector)
                                elif isinstance(given_selector, PropSelect):
                                    property = given_selector
                                else:
                                    raise ValueError(f'Invalid selector assigned to {name}: {given_selector}')
                            else:
                                raise ValueError(f'To configure a selector on {cls_name} use select(), select_opt(), select_arr(), or select_arr()')
                        else:
                            property = _selector_from_select_proxy(name, origin, cls, target, SelectProxy(None, {}))
                        setattr(cls, name, property)
                        properties[property.label] = property
                    elif isclass(origin) and issubclass(origin, Discrim):
                        assert len(type_params) > 1, f'Discriminator {name} on model {cls_name} is missing one or more of the three required type paramaters: {_type}'
                        assert len(type_params) == 2, f'Discriminator {name} on model {cls_name} has more than three type paramaters: {_type}'
                        assert issubclass(cls, type_params[0]), f'Selector {name} on model {cls_name} selects from {type_params[0]} instead of {cls_name}: {_type}'
                        super_class = type_params[0]
                        target = type_params[1]
                        if hasattr(cls, name):
                            given_selector = getattr(cls, name)
                            if given_selector is not None:
                                if isinstance(given_selector, SelectProxy):
                                    prop = _selector_from_select_proxy(name, Prop, cls, str, given_selector)
                                    discrim = Discrim(super_class, target, prop, target.__name__)
                                elif isinstance(given_selector, Discrim):
                                    discrim = given_selector
                                else:
                                    raise ValueError(f'Invalid selector assigned to {name}: {given_selector}')
                            else:
                                raise ValueError(f'To configure a selector on {cls_name} use select(), select_opt(), select_arr(), or select_arr()')
                        else:
                            prop = _selector_from_select_proxy(name, Prop, cls, str, SelectProxy(None, {}))
                            discrim = Discrim(super_class, target, prop, target.__name__)
                        setattr(cls, name, discrim)
                        properties[discrim.property.label] = discrim

        return type.__getattribute__(cls, name_to_get)

def _fully_validate(target: Type[M], value: Any, validators: Dict[Type[Any], Validator]) -> M:
    if isinstance(value, target):
        return value
    elif isinstance(value, PartialModel):
        if not issubclass(value.model, target):
            raise ValueError(f'received partial model of {value.model} instead of expected model {target}')
        return target(**value.as_dict(), _allow_extra_args=True, _validators=validators)
    elif isinstance(value, dict):
        return target(**value, _validators=validators)
    else:
        print(f'{target}, {target.__name__}, {value}')
        raise ValueError(f'expected type {target.__name__} (or dict) but received: {type(value).__name__}.')

class BaseModel(ModelLike, metaclass=BaseModelMeta):
    """
    Base type for a Pydoptic model.

    A Pydoptic model consists of `PropSelect` class attributes (`Prop`, `PropOpt`, `PropArr`, and `PropOptArr`) which
    (1) determine which instance attributes are supported, and (2) provide a mechanism for accessing and manipulating data
    both within instances and other, potentially incomplete data sources (e.g., `PartialModel` or `dict`)

    Instances are fully validated.

    Can include class attribute `validators` to specify how certain types should be validated.
    """
    _properties: Dict[Type[Any], Dict[str, PropSelect[Any, Any] | Discrim[Any, Any]]]
    validators: Dict[Type[Any], Validator]
    """
    Table for looking up validation functions by type.
    """

    @classmethod
    def properties(cls) -> Dict[str, PropSelect[Any, Any] | Discrim[Any, Any]]:
        """
        All the selectors for this subclass
        """
        return BaseModel._properties[cls]

    @classmethod
    def partial(cls, **kwargs) -> PartialModel[Self]:
        """
        Create a partial instance of this model with a subset of properties. Required properties can be 
        omitted, but must be otherwise valid. See `PartialModel`.
        """
        return PartialModel(cls, **kwargs)

    @classmethod
    def construct_partial(cls, *values: Param[Self, Any], **kwargs) -> PartialModel[Self]:
        """
        Create a partial instance of this model using selectors to specify fields. Required properties can be 
        omitted, but must be otherwise valid. See `PartialModel`.
        """
        return PartialModel(cls, **{p.label: p.value for p in values}, **kwargs)

    @classmethod
    def construct(cls, *values: Param[Self, Any], **kwargs) -> Self:
        """
        Create an instance of this model using selectors to specify fields instead of keyword arguments. 
        Required properties can be omitted, but must be otherwise valid. See `PartialModel`.
        """
        return cls(**{p.label: p.value for p in values}, **kwargs)

    def as_partial(self) -> PartialModel[Self]:
        """
        Convert to a `PartialModel`
        """
        return PartialModel(self.__class__, **self.as_dict())

    def __init__(self, **kwargs):
        """
        Construct a model instance, providing all required properties as keyword arguments. Two specialized arguments
        can also be included:
          _allow_extra_args: don't fail when unrecognized properties are provided (they will be excluded, however).
          _validators: a dict instance to lookup validators by type. Will merge with (and overwrite) the validators class attribute
        """
        allow_extra_args = kwargs.get('_allow_extra_args', False)
        if '_allow_extra_args' in kwargs:
            del kwargs['_allow_extra_args']
        validators = getattr(self.__class__, 'validators', {})
        if '_validators' in kwargs:
            validators.update(kwargs['_validators'])
            del kwargs['_validators']
        for selector in self.__class__.properties().values():
            if isinstance(selector, Discrim):
                if selector.property.label in kwargs and kwargs[selector.property.label] != selector.value:
                    raise ValueError(f'Discriminator {selector.property.label} set to illegal value: {kwargs[selector.property.label]}. Must be {selector.value} (will be set automatically if omitted).')
                setattr(self, selector.property.label, selector.value)
            else:
                if selector.label not in kwargs and not selector.is_opt:
                    raise ValueError(f'Missing required parameter {selector.label}')
                if selector.label not in kwargs:
                    setattr(self, selector.label, None)
                else:
                    value = kwargs[selector.label]
                    del kwargs[selector.label]
                    if value is None and not selector.is_opt:
                        raise ValueError(f'Received empty value for required parameter {selector.label}')
                    if value is None:
                        setattr(self, selector.label, None)
                    else:
                        if isclass(selector.target) and issubclass(selector.target, BaseModel):
                            if selector.is_arr:
                                if not isinstance(value, list):
                                    raise ValueError(f'Received non-array value for array field {selector.label}')
                                updated_values = []
                                for i, v in enumerate(value):
                                    try:
                                        updated_values.append(_fully_validate(selector.target, v, validators))
                                    except ValueError as ve:
                                        raise ValueError(f'Property {selector.label} contains invalid element at index {i}: {ve}')
                                setattr(self, selector.label, updated_values)
                            else:
                                try:
                                    print(selector.target)
                                    valid_value = _fully_validate(selector.target, value, validators)
                                    setattr(self, selector.label, valid_value)
                                except ValueError as ve:
                                    raise ValueError(f'Invalid property {selector.label}: {ve}')            
                        else:
                            error_message = validate_type(selector.is_opt, selector.is_arr, selector.target, value, validators)
                            if error_message is not None:
                                message = f'Invalid property {selector.label}: {error_message}'
                                raise ValueError(message)
                            setattr(self, selector.label, value)

        if not allow_extra_args:
            for k, v in kwargs.items():
                if k not in self.__class__.properties():
                    raise ValueError(f'Unrecognized parameter {k} provided (value: {v})')

    def __repr__(self):
        return self.__class__.__name__ + '(' + ', '.join(f'{k}={v}' for k, v in self.as_dict().items()) + ')'

    def __setattr__(self, name: str, value):
        if name in self.properties():
            prop = self.properties()[name]
            if isinstance(prop, Discrim) and value != prop.value:
                raise AttributeError(f'Setting discriminator value is forbidden')
        
        super().__setattr__(name, value)

    def as_dict(self) -> Mapping[str, Any]:
        mapping: Dict[str, Any] = {}
        for name in self.__class__.properties().keys():
            try:
                value = getattr(self, name)
                mapping[name] = value
            except AttributeError:
                ...
        return mapping

    def as_dict_full(self) -> Mapping[str, Any]:
        mapping: Dict[str, Any] = {}
        for name in self.__class__.properties().keys():
            try:
                value = getattr(self, name)
                if isinstance(value, ModelLike):
                    mapping[name] = value.as_dict_full()
                else:
                    mapping[name] = value
            except AttributeError:
                print('hi')
                ...
        return mapping

    def select_partial(self, *selectors: Select[Self, Any]) -> PartialModel[Self]:
        """
        Generate a partial version of this instance, selecting the data to retain with one or more `Select` instances.
        """
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

class PartialModel(Generic[M], Selectable[M]):
    """
    An incomplete version of model instances. Validates data without requiring that all required properties are present.
    """
    __slots__ = ['_dict', 'model']
    model: Type[M]
    _dict: Dict[str, Any]

    def as_model(self, **extra_args) -> M:
        """
        Convert to a complete model, providing any missing properties as keyword arguments.
        """
        return self.model(**self._dict, **extra_args)

    def construct_as_model(self, values: Dict[PropSelect[Self, Any], Any], **extra_args) -> M:
        """
        Convert to a complete model, providing any missing properties using `PropSelect` instances as lookups.
        """
        return self.model(**{sel.label: val for sel, val in values.items()}, **self._dict, **extra_args)

    def __init__(self, model: Type[M], **kwargs):
        """
        Construct a partial model from a model class and any desired properties. Validates provided properties without enforcing
        required property types. Allows unrecognized properties (but does not include them).
        """
        object.__setattr__(self, '_dict', {})
        object.__setattr__(self, 'model', model)
        allow_extra_args = kwargs.get('_allow_extra_args', False)
        if '_allow_extra_args' in kwargs:
            del kwargs['_allow_extra_args']
        validators = getattr(model, 'validators', {})
        if '_validators' in kwargs:
            validators.update(kwargs['_validators'])
            del kwargs['_validators']
        for selector in model.properties().values():
            if isinstance(selector, Discrim):
                if selector.property.label in kwargs and kwargs[selector.property.label] != selector.value:
                    raise ValueError(f'Discriminator {selector.property.label} set to illegal value: {kwargs[selector.property.label]}. Must be {selector.value} (will be set automatically if omitted).')
                setattr(self, selector.property.label, selector.value)
            else:
                if selector.label in kwargs:
                    value = kwargs[selector.label]
                    if value is not None:
                        if isclass(selector.target) and issubclass(selector.target, BaseModel):
                            if selector.is_arr:
                                if not isinstance(value, list):
                                    raise ValueError(f'Received non-array value for array field {selector.label}')
                                updated_values = []
                                for i, v in enumerate(value):
                                    try:
                                        updated_values.append(_partly_validate(selector.target, v, validators))
                                    except ValueError as ve:
                                        raise ValueError(f'Property {selector.label} contains invalid element at index {i}: {ve}')
                                self._dict[selector.label] = updated_values
                            else:
                                try:
                                    valid_value = _partly_validate(selector.target, value, validators)
                                    self._dict[selector.label] = valid_value
                                except ValueError as ve:
                                    raise ValueError(f'Invalid property {selector.label}: {ve}')            
                        else:
                            error_message = validate_type(selector.is_opt, selector.is_arr, selector.target, value, validators)
                            if error_message is not None:
                                message = f'Invalid property {selector.label}: {error_message}'
                                raise ValueError(message)
                            self._dict[selector.label] = value

        if not allow_extra_args:
            for k, v in kwargs.items():
                if k not in model.properties():
                    raise ValueError(f'Unrecognized parameter {k} provided (value: {v})')

    def __repr__(self):
        return 'Partial' + self.model.__name__ + '(' + ', '.join(f'{k}={v}' for k, v in self._dict.items()) + ')'

    def __getattr__(self, item):
        try:
            return object.__getattribute__(self, '_dict')[item]
        except KeyError:
            if item == 'model':
                return object.__getattribute__(self, 'model')
            raise AttributeError(item)

    def __setattr__(self, key, value):
        if key in self.model.properties():
            prop = self.model.properties()[key]
            if isinstance(prop, Discrim) and value != prop.value:
                raise AttributeError(f'Setting discriminator value is forbidden')
        
        object.__getattribute__(self, '_dict')[key] = value

    def as_dict(self) -> Mapping[str, Any]:
        return self._dict

    def select_partial(self, *selectors: Select[M, Any]) -> PartialModel[M]:
        """
        Generate another partial instance, selecting the data to retain with one or more `Select` instances.
        """
        data: Dict[str, Any] = {}
        for selector in selectors:
            selector.copy_to_safe(self, data)
        return self.model.partial(**data)
