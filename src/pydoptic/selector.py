from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import Any, Callable, Dict, Generic, List, Mapping, Tuple, Type, TypeVar, cast, Optional

A = TypeVar('A')
B = TypeVar('B')
C = TypeVar('C')

class Selectable:
    def __init__(self):
        self._dict = {}

    @property
    def as_mapping(self) -> Mapping[str, Any]:
        return self._dict
    
    def set_mapping(self, key: str, value: Any):
        self._dict[key] = value
    
    @property
    def as_mapping_full(self) -> Mapping[str, Any]:
        result: Dict[str, Any] = {}
        for k, v in self.as_mapping.items():
            if isinstance(v, Selectable):
                result[k] = v.as_mapping_full
            else:
                result[k] = v
        return result
    
    def __eq__(self, value):
        if isinstance(value, Selectable):
            other_dict = value.as_mapping_full
        elif isinstance(value, dict):
            other_dict = value
        else:
            return False
        return self.as_mapping_full == other_dict

    def __hash__(self):
        match self:
            case AttributeSelect(_label=label, _origin=origin, _target=target, _is_arr=is_arr, _is_opt=is_opt):
                return hash((label, origin, target, is_arr, is_opt))
            case LinkedSelect(select_1=sel_1, select_2=sel_2):
                return hash((sel_1, sel_2))
            case _:
                raise ValueError()

@dataclass(frozen=True)
class SelectValue(Generic[A]):
    value: A | List[A] | None
    is_opt: bool
    is_arr: bool

    @property
    def as_list(self) -> List[A]:
        if self.value is None:
            return []
        if self.is_arr:
            return cast(List[A], self.value)
        return cast(List[A], [self.value])
    
    @property
    def as_opt(self) -> A | None:
        if self.value is None:
            return None
        if self.is_arr and isinstance(self.value, list):
            if len(self.value) < 1:
                return None
            return self.value[0]
        return cast(A, self.value)

    def for_each(self, fn: Callable[[A], None]):
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
        if self.value is None:
            if not self.is_opt:
                raise ValueError()
            return cast(SelectValue[B], self)
        if self.is_arr and isinstance(self.value, list):
            return SelectValue([fn(v) for v in self.value], self.is_opt, self.is_arr)
        return SelectValue(fn(cast(A, self.value)), self.is_opt, self.is_arr)

    def flat_map(self, fn: Callable[[A], 'SelectValue[B]']) -> 'SelectValue[B]':
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
    def then(self, next: 'Select[B, C]') -> 'Select[A, C]':
        match next:
            case AttributeSelect():
                return LinkedSelect(self, next)
            case LinkedSelect(select_1=select_1, select_2=select_2):
                return LinkedSelect(self(select_1), select_2)
            case _:
                raise ValueError()

    def __call__(self, next: 'Select[B, C]') -> 'Select[A, C]':
        return self.then(next)

    @property
    def attributes(self) -> List['AttributeSelect[A, Any]']:
        match self:
            case AttributeSelect():
                return [self]
            case LinkedSelect(select_1=select_1, select_2=select_2):
                return [*(attr for attr in select_1.attributes), select_2]
            case _:
                raise ValueError()

    @property
    def model(self) -> Type[A]:
        raise NotImplementedError()
            
    @property
    def path(self) -> str:
        return '.'.join(attr._label for attr in self.attributes)

    @property
    def target(self) -> Type[B]:
        match self:
            case AttributeSelect(_target=tgt):
                return tgt
            case LinkedSelect(select_2=select_2):
                return select_2.target
            case _:
                raise ValueError()
            
    def get_safe(self, target: Selectable | Dict[str, Any]) -> SelectValue[B]:
        try:
            return self.get_unsafe(target)
        except ValueError:
            return SelectValue(None, True, False)
    
    def get_unsafe(self, target: Selectable | Dict[str, Any]) -> SelectValue[B]:
        match self:
            case AttributeSelect(_label=label, _is_opt=is_opt, _is_arr=is_arr):
                if isinstance(target, Selectable):
                    dict_value = target.as_mapping
                elif isinstance(target, dict):
                    dict_value = target
                else:
                    raise ValueError(f'Value must be model or dict')
                result = dict_value.get(label)
                if result is None and not is_opt:
                    raise ValueError(f'Unexpected empty value for attribute {label}')
                if result is not None and is_arr and not isinstance(result, list):
                    raise ValueError(f'Array selector returned non-array value: {result}')
                return SelectValue(result, is_opt, is_arr)
            case LinkedSelect(select_1=select_1, select_2=select_2):
                result = select_1.get_unsafe(target).flat_map(lambda b: select_2.get_unsafe(b))
                return result
            case _:
                raise ValueError()

    def get(self, target: A) -> SelectValue[B]:
        match self:
            case AttributeSelect(_label=label, _is_opt=is_opt, _is_arr=is_arr):
                if isinstance(target, Selectable):
                    dict_value = target.as_mapping
                elif isinstance(target, dict):
                    dict_value = target
                else:
                    raise ValueError(f'Value must be model or dict')
                result = dict_value.get(label)
                if result is None and not is_opt:
                    raise ValueError(f'Unexpected empty value for attribute {label}')
                if result is not None and is_arr and not isinstance(result, list):
                    raise ValueError(f'Array selector returned non-array value: {result}')
                return SelectValue(result, is_opt, is_arr)
            case LinkedSelect(select_1=select_1, select_2=select_2):
                result = select_1.get(target).flat_map(lambda b: select_2.get(b))
                return result
            case _:
                raise ValueError()

    def set_safe(self, target: Selectable | Dict[str, Any], value: B):
        match self:
            case AttributeSelect(_label=label, _is_arr=is_arr):
                if is_arr:
                    list_value = self.get_safe(target).as_list
                    updated: Any = [value for _ in list_value]
                else:
                    updated = value
                if isinstance(target, Selectable):
                    target.set_mapping(label, updated)
                elif isinstance(target, dict):
                    target[label] = updated
                else:
                    return
            case LinkedSelect(select_1=select_1, select_2=select_2):
                select_1.get_safe(target).for_each(lambda b: select_2.set_safe(b, value))
            case _:
                raise ValueError()

    def set_unsafe(self, target: Selectable | Dict[str, Any], value: B):
        match self:
            case AttributeSelect(_label=label, _is_arr=is_arr):
                if is_arr:
                    list_value = self.get_unsafe(target).as_list
                    updated: Any = [value for _ in list_value]
                else:
                    updated = value
                if isinstance(target, Selectable):
                    target.set_mapping(label, updated)
                elif isinstance(target, dict):
                    target[label] = updated
                else:
                    raise ValueError(f'Value must be model or dict')
            case LinkedSelect(select_1=select_1, select_2=select_2):
                select_1.get_unsafe(target).for_each(lambda b: select_2.set_unsafe(b, value))
            case _:
                raise ValueError()

    def set(self, target: A, value: B):
        match self:
            case AttributeSelect(_label=label, _is_arr=is_arr):
                if is_arr:
                    list_value = self.get(target).as_list
                    updated: Any = [value for _ in list_value]
                else:
                    updated = value
                if isinstance(target, Selectable):
                    target.set_mapping(label, updated)
                else:
                    raise ValueError(f'Value must be model')
            case LinkedSelect(select_1=select_1, select_2=select_2):
                select_1.get(target).for_each(lambda b: select_2.set(b, value))
            case _:
                raise ValueError()

    def update_safe(self, target: Selectable | Dict[str, Any], fn: Callable[[B], B]):
        match self:
            case AttributeSelect(_label=label):
                select_value = self.get_safe(target)
                updated = select_value.map(fn)
                if isinstance(target, Selectable):
                    target.set_mapping(label, updated.value)
                elif isinstance(target, dict):
                    target[label] = updated.value
                else:
                    return
            case LinkedSelect(select_1=select_1, select_2=select_2):
                select_1.get_safe(target).for_each(lambda b: select_2.update_safe(b, fn))
            case _:
                raise ValueError()

    def update_unsafe(self, target: Selectable | Dict[str, Any], fn: Callable[[B], B]):
        match self:
            case AttributeSelect(_label=label):
                select_value = self.get_unsafe(target)
                updated = select_value.map(fn)
                if isinstance(target, Selectable):
                    target.set_mapping(label, updated.value)
                elif isinstance(target, dict):
                    target[label] = updated.value
                else:
                    raise ValueError(f'Value must be model or dict')
            case LinkedSelect(select_1=select_1, select_2=select_2):
                select_1.get_unsafe(target).for_each(lambda b: select_2.update_unsafe(b, fn))
            case _:
                raise ValueError()

    def update(self, target: A, fn: Callable[[B], B]):
        match self:
            case AttributeSelect(_label=label):
                select_value = self.get(target)
                updated = select_value.map(fn)
                if isinstance(target, Selectable):
                    target.set_mapping(label, updated.value)
                else:
                    raise ValueError(f'Value must be model')
            case LinkedSelect(select_1=select_1, select_2=select_2):
                select_1.get(target).for_each(lambda b: select_2.update(b, fn))
            case _:
                raise ValueError()

    def clear_safe(self, target: Selectable | Dict[str, Any]):
        match self:
            case AttributeSelect(_label=label, _is_opt=is_opt, _is_arr=is_arr):
                if isinstance(target, Selectable):
                    target.set_mapping(label, None)
                elif isinstance(target, dict):
                    del target[label]
                else:
                    return
            case LinkedSelect(select_1=select_1, select_2=select_2):
                select_1.get_safe(target).for_each(lambda b: select_2.clear_safe(b))
            case _:
                raise ValueError()

    def clear_safe_strict(self, target: Selectable | Dict[str, Any]):
        match self:
            case AttributeSelect(_label=label, _is_opt=is_opt, _is_arr=is_arr):
                if not is_opt and not is_arr:
                    return
                if isinstance(target, Selectable):
                    if is_opt:
                        target.set_mapping(label, None)
                    else:
                        target.set_mapping(label, [])
                elif isinstance(target, dict):
                    if is_opt:
                        del target[label]
                    else:
                        target[label] = []
                else:
                    return
            case LinkedSelect():
                current_select: Select[A, Any] = self
                while True:
                    match current_select:
                        case AttributeSelect(_is_opt=False, _is_arr=False):
                            return
                        case AttributeSelect():
                            return current_select.clear_safe_strict(target)
                        case LinkedSelect(select_1=select_1, select_2=select_2):
                            if select_2._is_opt or select_2._is_arr:
                                return select_1.get_safe(target).for_each(lambda b: select_2.clear_safe_strict(b))
                            current_select = select_1
            case _:
                raise ValueError()

    def clear_unsafe(self, target: Selectable | Dict[str, Any]):
        match self:
            case AttributeSelect(_label=label, _is_opt=is_opt, _is_arr=is_arr):
                if isinstance(target, Selectable):
                    target.set_mapping(label, None)
                elif isinstance(target, dict):
                    del target[label]
                else:
                    return
            case LinkedSelect(select_1=select_1, select_2=select_2):
                select_1.get_unsafe(target).for_each(lambda b: select_2.clear_unsafe(b))
            case _:
                raise ValueError()

    def clear_unsafe_strict(self, target: Selectable | Dict[str, Any]):
        match self:
            case AttributeSelect(_label=label, _is_opt=is_opt, _is_arr=is_arr):
                if not is_opt and not is_arr:
                    raise ValueError('Selector does not contain required property')
                if isinstance(target, Selectable):
                    if is_opt:
                        target.set_mapping(label, None)
                    else:
                        target.set_mapping(label, [])
                elif isinstance(target, dict):
                    if is_opt:
                        del target[label]
                    else:
                        target[label] = []
                else:
                    raise ValueError(f'Value must be model or dict')
            case LinkedSelect():
                current_select: Select[A, Any] = self
                while True:
                    match current_select:
                        case AttributeSelect(_is_opt=False, _is_arr=False):
                            raise ValueError(
                                f'Unable to clear value: selector path `{self.path}` does not contain clearable element')
                        case AttributeSelect():
                            return current_select.clear(target)
                        case LinkedSelect(select_1=select_1, select_2=select_2):
                            if select_2._is_opt or select_2._is_arr:
                                return select_1.get_unsafe(target).for_each(lambda b: select_2.clear_unsafe(b))
                            current_select = select_1
            case _:
                raise ValueError()

    def clear(self, target: A | Selectable | Dict[str, Any]):
        match self:
            case AttributeSelect(_label=label, _is_opt=is_opt, _is_arr=is_arr):
                if not is_opt and not is_arr:
                    raise ValueError('Selector does not contain required property')
                if isinstance(target, Selectable):
                    if is_opt:
                        target.set_mapping(label, None)
                    else:
                        target.set_mapping(label, [])
                elif isinstance(target, dict):
                    if is_opt:
                        del target[label]
                    else:
                        target[label] = []
                else:
                    raise ValueError(f'Value must be model or dict')
            case LinkedSelect():
                current_select: Select[A, Any] = self
                while True:
                    match current_select:
                        case AttributeSelect(_is_opt=False, _is_arr=False):
                            raise ValueError(f'Unable to clear value: selector path `{self.path}` does not contain clearable element')
                        case AttributeSelect():
                            return current_select.clear(target)
                        case LinkedSelect(select_1=select_1, select_2=select_2):
                            if select_2._is_opt or select_2._is_arr:
                                return select_1.get(target).for_each(lambda b: select_2.clear(b))
                            current_select = select_1
            case _:
                raise ValueError()

    def copy_to_safe(self, source: Selectable | Dict[str, Any], target: Dict[str, Any]):
        match self:
            case AttributeSelect(_label=label):
                value = self.get_safe(source).value
                target[label] = value
            case LinkedSelect(select_1=select_1, select_2=select_2):
                current_target = target
                current_sel_1: Select[Any, Any] = select_1
                current_sel_2: Select[Any, Any] = select_2
                while True:
                    match current_sel_1:
                        case LinkedSelect(select_1=select_1a, select_2=select_2a):
                            current_sel_1 = select_1a
                            current_sel_2 = select_2a(current_sel_2)
                        case AttributeSelect(_label=label):
                            value = current_sel_1.get_safe(source)
                            if label not in current_target or not isinstance(current_target[label], dict):
                                current_target[label] = {}
                            return value.for_each(lambda b: current_sel_2.copy_to_safe(b, current_target[label]))
            case _:
                raise ValueError()

    def copy_to_unsafe(self, source: Selectable | Dict[str, Any], target: Dict[str, Any]):
        match self:
            case AttributeSelect(_label=label):
                value = self.get_unsafe(source).value
                target[label] = value
            case LinkedSelect(select_1=select_1, select_2=select_2):
                current_target = target
                current_sel_1: Select[Any, Any] = select_1
                current_sel_2: Select[Any, Any] = select_2
                while True:
                    match current_sel_1:
                        case LinkedSelect(select_1=select_1a, select_2=select_2a):
                            current_sel_1 = select_1a
                            current_sel_2 = select_2a(current_sel_2)
                        case AttributeSelect(_label=label):
                            value = current_sel_1.get_unsafe(source)
                            if label not in current_target or not isinstance(current_target[label], dict):
                                current_target[label] = {}
                            return value.for_each(lambda b: current_sel_2.copy_to_unsafe(b, current_target[label]))
            case _:
                raise ValueError()

    def copy_to(self, source: A, target: Dict[str, Any]):
        match self:
            case AttributeSelect(_label=label):
                value = self.get(source).value
                target[label] = value
            case LinkedSelect(select_1=select_1, select_2=select_2):
                current_target = target
                current_sel_1: Select[Any, Any] = select_1
                current_sel_2: Select[Any, Any] = select_2
                while True:
                    match current_sel_1:
                        case LinkedSelect(select_1=select_1a, select_2=select_2a):
                            current_sel_1 = select_1a
                            current_sel_2 = select_2a(current_sel_2)
                        case AttributeSelect(_label=label):
                            value = current_sel_1.get(source)
                            if label not in current_target or not isinstance(current_target[label], dict):
                                current_target[label] = {}
                            return value.for_each(lambda b: current_sel_2.copy_to(b, current_target[label]))
            case _:
                raise ValueError()


class SelectVal(Generic[A, B], Select[A, B]):
    def get_val_safe(self, value: Selectable | Dict[str, Any]) -> B | None:
        return self.get_safe(value).as_opt

    def get_val_unsafe(self, value: Selectable | Dict[str, Any]) -> B:
        result = self.get_unsafe(value).value # type: ignore
        if result is None:
            raise ValueError('Unexpected empty value')
        return cast(B, result)

    def get_val(self, value: A) -> B:
        return self.get(value).value # type: ignore

    def then_val(self, next: SelectVal[B, C]) -> SelectVal[A, C]:
        match next:
            case Prop():
                return LinkedSelectVal(self, next)
            case LinkedSelectVal(select_1=select_1, select_2=select_2):
                return LinkedSelectVal(self(select_1), select_2)
            case _:
                raise ValueError()
    
    def then_opt(self, next: SelectOpt[B, C]) -> SelectOpt[A, C]:
        match next:
            case PropOpt():
                return LinkedSelectOpt(self, next)
            case LinkedSelectOpt(select_1=select_1, select_2=select_2):
                return LinkedSelectOpt(self(select_1), select_2)
            case _:
                raise ValueError()
    
    def then_arr(self, next: SelectArr[B, C]) -> SelectArr[A, C]:
        match next:
            case PropArr():
                return LinkedSelectArr(self, next)
            case LinkedSelectArr(select_1=select_1, select_2=select_2):
                return LinkedSelectArr(self(select_1), select_2)
            case _:
                raise ValueError()
    
    def then_opt_arr(self, next: SelectOptArr[B, C]) -> SelectOptArr[A, C]:
        match next:
            case PropOptArr():
                return LinkedSelectOptArr(self, next)
            case LinkedSelectOptArr(select_1=select_1, select_2=select_2):
                return LinkedSelectOptArr(self(select_1), select_2)
            case _:
                raise ValueError()

class SelectOpt(Generic[A, B], Select[A, B]):
    def get_val_safe(self, value: Selectable | Dict[str, Any]) -> B | None:
        return self.get_safe(value).as_opt

    def get_val_unsafe(self, value: Selectable | Dict[str, Any]) -> B | None:
        return self.get_unsafe(value).value # type: ignore

    def get_val(self, value: A | Dict[str, Any]) -> B | None:
        return self.get(value).value # type: ignore

    def then_val(self, next: SelectVal[B, C]) -> SelectOpt[A, C]:
        match next:
            case Prop():
                return LinkedSelectOpt(self, next)
            case LinkedSelectVal(select_1=select_1, select_2=select_2):
                return LinkedSelectOpt(self(select_1), select_2)
            case _:
                raise ValueError()
    
    def then_opt(self, next: SelectOpt[B, C]) -> SelectOpt[A, C]:
        match next:
            case PropOpt():
                return LinkedSelectOpt(self, next)
            case LinkedSelectOpt(select_1=select_1, select_2=select_2):
                return LinkedSelectOpt(self(select_1), select_2)
            case _:
                raise ValueError()
    
    def then_arr(self, next: SelectArr[B, C]) -> SelectOptArr[A, C]:
        match next:
            case PropArr():
                return LinkedSelectOptArr(self, next)
            case LinkedSelectArr(select_1=select_1, select_2=select_2):
                return LinkedSelectOptArr(self(select_1), select_2)
            case _:
                raise ValueError()
    
    def then_opt_arr(self, next: SelectOptArr[B, C]) -> SelectOptArr[A, C]:
        match next:
            case PropOptArr():
                return LinkedSelectOptArr(self, next)
            case LinkedSelectOptArr(select_1=select_1, select_2=select_2):
                return LinkedSelectOptArr(self(select_1), select_2)
            case _:
                raise ValueError()

class SelectArr(Generic[A, B], Select[A, B]):
    def get_val_safe(self, value: Selectable | Dict[str, Any]) -> List[B]:
        return self.get_safe(value).as_list

    def get_val_unsafe(self, value: Selectable | Dict[str, Any]) -> List[B]:
        result = self.get_unsafe(value).value # type: ignore
        if result is None:
            raise ValueError('Unexpected empty value')
        if not isinstance(result, list):
            raise ValueError('Retrieved non-list value')
        return result

    def get_val(self, value: A) -> List[B]:
        return self.get(value).value # type: ignore

    def then(self, next: Select[B, C]) -> SelectOptArr[A, C]:
        match next:
            case AttributeSelect():
                return LinkedSelectOptArr(self, next)
            case LinkedSelectArr(select_1=select_1, select_2=select_2):
                return LinkedSelectOptArr(self(select_1), select_2)
            case _:
                raise ValueError()

    def then_val(self, next: SelectVal[B, C]) -> SelectArr[A, C]:
        match next:
            case Prop():
                return LinkedSelectArr(self, next)
            case LinkedSelectVal(select_1=select_1, select_2=select_2):
                return LinkedSelectArr(self(select_1), select_2)
            case _:
                raise ValueError()

    def then_opt(self, next: SelectOpt[B, C]) -> SelectOptArr[A, C]:
        match next:
            case PropOpt():
                return LinkedSelectOptArr(self, next)
            case LinkedSelectOpt(select_1=select_1, select_2=select_2):
                return LinkedSelectOptArr(self(select_1), select_2)
            case _:
                raise ValueError()

    def then_arr(self, next: SelectArr[B, C]) -> SelectArr[A, C]:
        match next:
            case PropArr():
                return LinkedSelectArr(self, next)
            case LinkedSelectArr(select_1=select_1, select_2=select_2):
                return LinkedSelectArr(self(select_1), select_2)
            case _:
                raise ValueError()
    
    def then_opt_arr(self, next: SelectOptArr[B, C]) -> SelectOptArr[A, C]:
        match next:
            case PropOptArr():
                return LinkedSelectOptArr(self, next)
            case LinkedSelectOptArr(select_1=select_1, select_2=select_2):
                return LinkedSelectOptArr(self(select_1), select_2)
            case _:
                raise ValueError()

class SelectOptArr(Generic[A, B], Select[A, B]):
    def get_val_safe(self, value: Selectable | Dict[str, Any]) -> List[B] | None:
        result = self.get_safe(value).value
        if result is not None and not isinstance(result, list):
            return None
        return result

    def get_val_unsafe(self, value: Selectable | Dict[str, Any]) -> List[B] | None:
        result = self.get_unsafe(value).value
        if result is not None and not isinstance(result, list):
            raise ValueError('Unexpected non-list value')
        return result

    def get_val(self, value: A) -> List[B] | None:
        return self.get(value).value # type: ignore

    def get_arr_safe(self, value: Selectable | Dict[str, Any]) -> List[B]:
        return self.get_safe(value).as_list

    def get_arr_unsafe(self, value: Selectable | Dict[str, Any]) -> List[B]:
        res = self.get_unsafe(value).value
        if res is not None and not isinstance(res, list):
            raise ValueError('Unexpected non-list value')
        return cast(List[B], res)

    def get_arr(self, value: A) -> List[B]:
        return self.get_val(value) or [] # type: ignore

    def then(self, next: Select[B, C]) -> SelectOptArr[A, C]:
        match next:
            case AttributeSelect():
                return LinkedSelectOptArr(self, next)
            case LinkedSelectArr(select_1=select_1, select_2=select_2):
                return LinkedSelectOptArr(self(select_1), select_2)
            case _:
                raise ValueError()

    def then_val(self, next: SelectVal[B, C]) -> SelectOptArr[A, C]:
        match next:
            case Prop():
                return LinkedSelectOptArr(self, next)
            case LinkedSelectVal(select_1=select_1, select_2=select_2):
                return LinkedSelectOptArr(self(select_1), select_2)
            case _:
                raise ValueError()
    
    def then_opt(self, next: SelectOpt[B, C]) -> SelectOptArr[A, C]:
        match next:
            case PropOpt():
                return LinkedSelectOptArr(self, next)
            case LinkedSelectOpt(select_1=select_1, select_2=select_2):
                return LinkedSelectOptArr(self(select_1), select_2)
            case _:
                raise ValueError()
    
    def then_arr(self, next: SelectArr[B, C]) -> SelectOptArr[A, C]:
        match next:
            case PropArr():
                return LinkedSelectOptArr(self, next)
            case LinkedSelectArr(select_1=select_1, select_2=select_2):
                return LinkedSelectOptArr(self(select_1), select_2)
            case _:
                raise ValueError()
    
    def then_opt_arr(self, next: SelectOptArr[B, C]) -> SelectOptArr[A, C]:
        match next:
            case PropOptArr():
                return LinkedSelectOptArr(self, next)
            case LinkedSelectOptArr(select_1=select_1, select_2=select_2):
                return LinkedSelectOptArr(self(select_1), select_2)
            case _:
                raise ValueError()

@dataclass(frozen=True)
class AttributeSelect(Generic[A, B], Select[A, B]):
    _label: str
    _origin: Type[A]
    _target: Type[B]
    _data: Dict[str, Any]
    _is_opt: bool
    _is_arr: bool

    def __init__(self, l: str, o: Type[A], t: Type[B], d: Dict[str, Any], io: bool, ia: bool):
        raise NotImplementedError('Abstract base class AttributeSelect should not be implemented directly')

    @property
    def model(self) -> Type[A]:
        return self._origin

    @classmethod
    def val(cls, _label: str, _origin: Type[A], _target: Type[B], _data: Dict[str, Any]) -> Prop[A, B]:
        return Prop(_label, _origin, _target, _data, False, False) # type: ignore
    
    @classmethod
    def opt(cls, _label: str, _origin: Type[A], _target: Type[B], _data: Dict[str, Any]) -> PropOpt[A, B]:
        return PropOpt(_label, _origin, _target, _data, True, False) # type: ignore
    
    @classmethod
    def arr(cls, _label: str, _origin: Type[A], _target: Type[B], _data: Dict[str, Any]) -> PropArr[A, B]:
        return PropArr(_label, _origin, _target, _data, False, True) # type: ignore
    
    @classmethod
    def opt_arr(cls, _label: str, _origin: Type[A], _target: Type[B], _data: Dict[str, Any]) -> PropOptArr[A, B]:
        return PropOptArr(_label, _origin, _target, _data, True, True) # type: ignore

@dataclass(frozen=True)
class Prop(Generic[A, B], SelectVal[A, B], AttributeSelect[A, B]):
    _is_opt = False
    _is_arr = False

@dataclass(frozen=True)
class PropOpt(Generic[A, B], AttributeSelect[A, B], SelectOpt[A, B]):
    _is_opt = True
    _is_arr = False

    @property
    def value(self) -> Prop[A, Optional[B]]:
        return Prop(self._label, self._origin, Optional[self._target], self._data, False, False) # type: ignore

@dataclass(frozen=True)
class PropArr(Generic[A, B], AttributeSelect[A, B], SelectArr[A, B]):
    _is_opt = False
    _is_arr = True

    @property
    def value(self) -> Prop[A, List[B]]:
        return Prop(self._label, self._origin, List[self._target], self._data, False, False) # type: ignore

@dataclass(frozen=True)
class PropOptArr(Generic[A, B], AttributeSelect[A, B], SelectOptArr[A, B]):
    _is_opt = True
    _is_arr = True

    @property
    def option(self) -> Prop[A, List[B]]:
        return Prop(self._label, self._origin, List[self._target], self._data, False, False) # type: ignore

    @property
    def value(self) -> Prop[A, List[B] | None]:
        return Prop(self._label, self._origin, Optional[List[self._target]], self._data, False, False) # type: ignore

@dataclass(frozen=True)
class LinkedSelect(Generic[A, B, C], Select[A, C]):
    select_1: Select[A, B]
    select_2: AttributeSelect[B, C]

    @cached_property
    def model(self) -> Type[A]:
        return self.select_1.model

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
