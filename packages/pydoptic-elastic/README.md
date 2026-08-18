# pydoptic-elastic

An Elasticsearch integration built on [pydoptic](https://pypi.org/project/pydoptic/).

`ElasticModel` captures index and field-mapping metadata directly on the model's `Prop`s, and `Query`
lets you build Elasticsearch queries by referencing those `Prop`s directly -- no field or index names
passed as bare strings.

## Installation

```bash
pip install pydoptic-elastic
```

Includes the `elasticsearch` client as a regular dependency, so no extras are needed.

## Quickstart

```python3
from pydoptic import Prop
from pydoptic_elastic import ElasticModel, ElasticService, Query, elastic_prop, ESMapping
from elasticsearch import Elasticsearch

class Person(ElasticModel):
    name: Prop['Person', str] = elastic_prop(mapping=ESMapping.keyword)
    age: Prop['Person', int]

service = ElasticService(Elasticsearch('http://localhost:9200'))
service.create_index(Person)

service.index(Person(name='John', age=42))

query = Query.match(Person.name, 'John')
for person in service.search(query):
    print(Person.name.get_val(person))
    # John

# Retrieve only specific fields, as a PartialModel:
for person in service.search_partial(query, source=[Person.name]):
    print(Person.name.get_val_unsafe(person))
    # John
```

See the [pydoptic README](https://github.com/johnhungerford/pydoptic/tree/main/packages/pydoptic) for
the underlying `Prop`/`Select` model this is built on.
