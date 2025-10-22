from typing import TypeVar, Generic, Dict, Any, Type, List

from pydoptic import Select
from pydoptic_elastic.elastic_model import M, TERM_SUFFIX, ESMapping

A = TypeVar('A')

class Query(Generic[M]):
    def to_dict(self) -> Dict[str, Any]:
        raise NotImplementedError()

    @property
    def model(self) -> Type[M]:
        raise NotImplementedError()

    @classmethod
    def match(cls, select: Select[M, A], value: A, **kwargs) -> 'MatchQuery[M]':
        return MatchQuery(select, value)

    @classmethod
    def bool(
        cls,
        should: List['Query[M]'] | None = None,
        must: List['Query[M]'] | None = None,
        filter: List['Query[M]'] | None = None,
        must_not: List['Query[M]'] | None = None,
        minimum_should_match: int | None = None,
    ) -> 'BoolQuery[M]':
        return BoolQuery(should=should or [], must=must or [], filter=filter or [], must_not=must_not or [], minimum_should_match=minimum_should_match)

    @classmethod
    def term(cls, select: Select[M, str], value: str, **kwargs) -> 'TermQuery[M]':
        return TermQuery(select, value, **kwargs)

    @classmethod
    def exists(cls, select: Select[M, A]) -> 'ExistsQuery[M]':
        return ExistsQuery(select)

    @classmethod
    def manual(cls, model: Type[M], query: Dict[str, Any]) -> 'ManualQuery[M]':
        return ManualQuery(model, query)

class ManualQuery(Generic[M]):
    def __init__(self, mdl: Type[M], query: Dict[str, Any]):
        self.mdl = mdl
        self.query = query

    def to_dict(self) -> Dict[str, Any]:
        return self.query

    def model(self) -> Type[M]:
        return self.mdl

class ExistsQuery(Query[M]):
    def __init__(self, select: Select[M, A]) -> None:
        self.select = select

    def to_dict(self) -> Dict[str, Any]:
        return {'exists': {'field': self.select.path}}

    @property
    def model(self) -> Type[M]:
        return self.select.model

class TermQuery(Query[M]):
    def __init__(self, select: Select[M, str], value: str, **options) -> None:
        self.select = select
        self.value = value
        self.options = options

    def to_dict(self) -> Dict[str, Any]:
        match ESMapping.from_select(self.select):
            case ESMapping.keyword:
                path = self.select.path
            case ESMapping.text_keyword:
                path = self.select.path + '.' + TERM_SUFFIX
            case other:
                raise ValueError(f'Term query unsupported on {self.select.path} (mapping type: {other.value})')
        return {'term': {path: {'value': self.value, **self.options}}}

    @property
    def model(self) -> Type[M]:
        return self.select.model

class BoolQuery(Query[M]):
    def __init__(self, should: List[Query[M]], must: List[Query[M]], filter: List[Query[M]], must_not: List[Query[M]], minimum_should_match: int | None = None) -> None:
        self.should = should
        self.must = must
        self.filter = filter
        self.must_not = must_not
        self.mdl: Type[M] | None = None
        self.minimum_should_match = minimum_should_match

    def to_dict(self) -> Dict[str, Any]:
        bool_obj: Dict[str, Any] = {}
        if len(self.should) > 0:
            bool_obj['should'] = self.should
        if len(self.must) > 0:
            bool_obj['must'] = self.must
        if len(self.filter) > 0:
            bool_obj['filter'] = self.filter
        if len(self.must_not) > 0:
            bool_obj['must_not'] = self.must_not
        if self.minimum_should_match is not None:
            bool_obj['minimum_should_match'] = self.minimum_should_match
        return {'bool': bool_obj}

    @property
    def model(self) -> Type[M]:
        if self.mdl is not None:
            return self.mdl
        else:
            for batch in [self.should, self.must, self.must_not, self.filter]:
                for query in batch:
                    self.mdl = query.model
                    return self.mdl
            raise ValueError(f'Bool query contains no queries and no valid models: {self}')

    def add_should(self, query: Query[M], *queries: Query[M]):
        if self.mdl is None:
            self.mdl = query.model
        self.should.append(query)
        self.should.extend(queries)

    def add_must(self, query: Query[M], *queries: Query[M]):
        if self.mdl is None:
            self.mdl = query.model
        self.must.append(query)
        self.must.extend(queries)

    def add_filter(self, query: Query[M], *queries: Query[M]):
        if self.mdl is None:
            self.mdl = query.model
        self.filter.append(query)
        self.filter.extend(queries)

    def add_must_not(self, query: Query[M], *queries: Query[M]):
        if self.mdl is None:
            self.mdl = query.model
        self.must_not.append(query)
        self.must_not.extend(queries)

class MatchQuery(Query[M]):
    def __init__(self, select: Select[M, A], value: A, **options):
        self.select = select
        self.value = value
        self.options = options

    def to_dict(self) -> Dict[str, Any]:
        return {'match': {self.select.path: {'query': self.value}, **self.options}}

    @property
    def model(self) -> Type[M]:
        return self.select.model
