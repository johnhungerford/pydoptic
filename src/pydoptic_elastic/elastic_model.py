from datetime import date, datetime
from enum import Enum
from typing import Any, ClassVar, Dict, Optional, TypeVar, TypedDict, Unpack, cast

from pydoptic import BaseModel, select
from pydoptic.selector import PropSelect, LinkedSelect, Select

class ESFieldData(TypedDict):
    mapping: Optional['ESMapping']

TERM_SUFFIX = 'term'

class ESMapping(Enum):
    text_keyword = 'text_keyword'
    text = 'text'
    keyword = 'keyword'
    long = 'long'
    double = 'double'
    boolean = 'boolean'
    date = 'date'

    @classmethod
    def from_select(self, prop: Select[Any, Any]) -> 'ESMapping':
        match prop:
            case PropSelect():
                data = cast(ESFieldData, prop.data)
                mapping = data.get('mapping')
                if mapping is not None:
                    return mapping
                return _mappings_lookup.get(prop.target) or ESMapping.text_keyword
            case LinkedSelect(select_2=prop):
                return self.from_select(prop)
            case _:
                raise ValueError()

    def to_dict(self) -> Dict[str, Any]:
        match self:
            case ESMapping.text_keyword:
                return {'type': 'text', 'fields': {TERM_SUFFIX: {'type': 'keyword'}}}
            case ESMapping.text:
                return {'type': 'text'}
            case ESMapping.keyword:
                return {'type': 'keyword'}
            case ESMapping.long:
                return {'type': 'long'}
            case ESMapping.double:
                return {'type': 'double'}
            case ESMapping.boolean:
                return {'type': 'boolean'}
            case ESMapping.date:
                return {'type': 'date'}

_mappings_lookup = {
    str: ESMapping.text_keyword,
    int: ESMapping.long,
    float: ESMapping.double,
    bool: ESMapping.boolean,
    date: ESMapping.date,
    datetime: ESMapping.date,
}

class ElasticModel(BaseModel):
    index_name: ClassVar[str]

    @classmethod
    def _get_index_name(cls) -> str:
        try:
            return cls.index_name
        except AttributeError:
            return cls.__name__.lower()
    
    @classmethod
    def _get_mappings(cls) -> Dict[str, Any]:
        mappings: Dict[str, Any] = {}
        for prop in cls.selectors().values():
            if issubclass(prop.target, ElasticModel):
                mappings[prop.label] = {'type': 'object', 'properties': prop.target._get_mappings()}
            else:
                mappings[prop.label] = ESMapping.from_select(prop).to_dict()
        return mappings

M = TypeVar('M', bound=ElasticModel)

def elastic_prop(name: str | None = None, **field_data: Unpack[ESFieldData]) -> Any:
    return select(name, **field_data)
