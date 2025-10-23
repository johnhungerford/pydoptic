from typing import List, Iterable, Any, Dict, Type

from elasticsearch import Elasticsearch, NotFoundError

from pydoptic import BaseModel, Select, PartialModel
from pydoptic.selector import Prop
from pydoptic_elastic.elastic_model import M
from pydoptic_elastic.query import Query
from pydoptic.base_model import select

class _IndexResponse(BaseModel):
    id: Prop['_IndexResponse', str] = select('_id')

class _GetResponse(BaseModel):
    id: Prop['_GetResponse', str] = select('_id')
    doc: Prop['_GetResponse', Dict[str, Any]] = select('_source')

class ElasticService:
    def __init__(self, client: Elasticsearch):
        self.__client = client

    def create_index(self, model: Type[M]):
        self.__client.indices.create(index=model._get_index_name(), mappings={'properties': model._get_mappings()})

    def delete_index(self, model: Type[M]):
        self.__client.indices.delete(index=model._get_index_name())

    def refresh_index(self, model: Type[M]):
        self.__client.indices.refresh(index=model._get_index_name())

    def index(self, document: M, **kwargs) -> str:
        response = self.__client.index(index=document.__class__._get_index_name(), document=document.as_mapping_full(), **kwargs)
        return _IndexResponse.id.get_val(response.body)
    
    def get(self, cls: Type[M], id: str, **kwargs) -> M | None:
        try:
            response = self.__client.get(index = cls._get_index_name(), id=id, **kwargs)
            return _GetResponse.doc.get_unsafe(response.body).map(lambda d: cls(**d)).as_opt
        except NotFoundError:
            return None
        
    def get_partial(self, cls: Type[M], id: str, **kwargs) -> PartialModel[M] | None:
        try:
            response = self.__client.get(index = cls._get_index_name(), id=id, **kwargs)
            return _GetResponse.doc.get_unsafe(response.body).map(lambda d: cls.partial(**d)).as_opt
        except NotFoundError:
            return None
        
    def get_raw(self, cls: Type[M], id: str, **kwargs) -> Dict[str, Any] | None:
        try:
            response = self.__client.get(index = cls._get_index_name(), id=id, **kwargs)
            return _GetResponse.doc.get_unsafe(response.body).as_opt
        except NotFoundError:
            return None

    def search(self, query: Query[M], **kwargs) -> Iterable[M]:
        search_results = self.__client.search(index = query.model._get_index_name(), query=query.to_dict(), **kwargs)
        for hit in search_results['hits']['hits']:
            _source = hit['_source']
            yield query.model(**_source)

    def search_partial(self, query: Query[M], source: Iterable[Select[M, Any]] | None = None, **kwargs) -> Iterable[PartialModel[M]]:
        _kwargs = kwargs if source is None else {'source': [sel.path for sel in source], **kwargs}
        search_results = self.__client.search(index=query.model._get_index_name(), query=query.to_dict(), **kwargs)
        for hit in search_results['hits']['hits']:
            _source = hit['_source']
            yield query.model.partial(**_source)

    def search_raw(self, query: Query[M], source: Iterable[Select[M, Any]] | None = None, **kwargs) -> Iterable[Dict[str, Any]]:
        _kwargs = kwargs if source is None else {'source': [sel.path for sel in source], **kwargs}
        search_results = self.__client.search(index=query.model._get_index_name(), query=query.to_dict(), **kwargs)
        for hit in search_results['hits']['hits']:
            yield hit['_source']
