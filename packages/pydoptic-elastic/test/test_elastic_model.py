from datetime import date, datetime
from elasticsearch import Elasticsearch

from pydoptic.selector import Prop, PropOptArr
from pydoptic_elastic import ElasticModel, elastic_prop, ESMapping

class Nested(ElasticModel):
    prop_a: Prop['Nested', str] = elastic_prop(mapping=ESMapping.keyword)

class SimpleModel(ElasticModel):
    index_name = 'name_override'

    prop_1: Prop['SimpleModel', str] = elastic_prop(mapping=ESMapping.text)
    prop_2: Prop['SimpleModel', str]
    prop_3: Prop['SimpleModel', int]
    prop_4: Prop['SimpleModel', float]
    prop_5: Prop['SimpleModel', bool]
    prop_6: Prop['SimpleModel', date]
    prop_7: Prop['SimpleModel', datetime]
    prop_8: PropOptArr['SimpleModel', Nested]

def test_elastic_model_mapping_should_reflect_custom_and_default_mappings():
    mappings = SimpleModel._get_mappings()
    assert mappings == {
        'prop_1': {'type': 'text'},
        'prop_2': {'type': 'text', 'fields': {'term': {'type': 'keyword'}}},
        'prop_3': {'type': 'long'},
        'prop_4': {'type': 'double'},
        'prop_5': {'type': 'boolean'},
        'prop_6': {'type': 'date'},
        'prop_7': {'type': 'date'},
        'prop_8': {'type': 'object', 'properties': {'prop_a': {'type': 'keyword'}}},
    }
