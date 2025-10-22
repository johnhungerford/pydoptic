from elasticsearch import Elasticsearch

from pydoptic.selector import Prop
from pydoptic_elastic.elastic_model import ElasticModel
from pydoptic_elastic.elastic_service import ElasticService
from pydoptic_elastic.query import Query

class SimpleModel(ElasticModel):
    prop_1: Prop['SimpleModel', int]
    prop_2: Prop['SimpleModel', str]
    prop_3: Prop['SimpleModel', bool]

def test_index_and_retrieve_records():
    client = Elasticsearch('http://localhost:9200')

    service = ElasticService(client)

    try:
        service.create_index(SimpleModel)
    except:
        service.delete_index(SimpleModel)
        service.create_index(SimpleModel)

    try:
        value = SimpleModel(prop_1=23, prop_2="hello", prop_3=True)

        value_id = service.index(value)
        service.refresh_index(SimpleModel)

        value_retrieved = service.get(SimpleModel, value_id)

        assert value_retrieved == value

    finally:
        service.delete_index(SimpleModel)

def test_search_records():
    client = Elasticsearch('http://localhost:9200')

    service = ElasticService(client)

    try:
        service.create_index(SimpleModel)
    except:
        service.delete_index(SimpleModel)
        service.create_index(SimpleModel)

    try:
        value_1 = SimpleModel(prop_1=23, prop_2="hello", prop_3=True)
        value_2 = SimpleModel(prop_1=24, prop_2="world", prop_3=False)

        service.index(value_1)
        service.index(value_2)
        service.refresh_index(SimpleModel)

        query_1 = Query.match(SimpleModel.prop_1, SimpleModel.prop_1.get_val(value_1))
        res_1 = list(service.search(query_1))
        assert res_1 == [value_1]

        query_2 = Query.match(SimpleModel.prop_1, SimpleModel.prop_1.get_val(value_2))
        res_2 = list(service.search(query_2))
        assert res_2 == [value_2]

    finally:
        service.delete_index(SimpleModel)
