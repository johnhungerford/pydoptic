from pydoptic_elastic import ElasticModel

# Pydoptic

A data modeling framework based on reified optics

## Why?

In every programming language, data is modeled by the type of container used to store it in memory. In Python, this typically looks like the following:

```python3
from pydantic import BaseModel
from datetime import date
from typing import List

class Address(BaseModel):
    number: str
    street: str
    city: str
    postal_code: str
    state: str

class Organization(BaseModel):
    name: str
    address: Address
    phone_number: str
    owner: 'Person'
    members: List['Person'] | None

class Person(BaseModel):
    name: str
    address: Address
    birth_date: date
    phone_number: str
    organizations: List[Organization] | None
    is_active: bool
```

While the above class definitions do provide a reasonably precisely typed description of the data we expect to deal with, their actual utility when it comes to coding is fairly limited. At most they can do the following:

1. Validate and then represent a complete instance of each data type, either from parameters or some serialized source (e.g., JSON)
2. Provide access to any property that can be validated with a type checker
3. Generate a valid serialized representation (e.g. JSON)

While this is certainly useful, consider all the other things we might want to do:

1. Consume and validate an incomplete model of our data (e.g., a `Person`'s `name` and `birth_date`, but nothing else)
2. Access potentially missing values of an incomplete model without sacrificing type precision on the complete model (e.g., `Person.address` should not be `Optional` in the full model, yet in some cases you may not want to include it)
3. Query just the `name` and `birth_date` from our data store. Nothing in the data model allows us to *specify the field itself* -- only the *value* of the field. This is an important distinction.
4. Update the `is_active` flag of every person in every organization a person is a member of without having to check if `Person.organizations` or `Organization.members` are `None`.

Achieving the above with ordinary data models is inconvenient at best. Dealing with incomplete data requires defining new types for each use case or abandoning type safety altogether. While data models can read and write (complete) records to a datastore, they provide no mechanism for helping us specify the parts of the data model that of interest to us, such as when we want to specify which fields to retrieve or define a query setting some constraint on a particular field. In general we have to specify field names as strings, losing any pre-runtime validation. Finally, data models provide no abstractions for manipulating nested data, nor do they provide any mechanism that could be used to create such abstractions.

Pydoptic provides an alternative way to model data in Python -- and indeed in any language -- that allows you to accomplish much more with your data and much more safely.

## How?

Whereas traditional data models represent data as *containers*, Pydoptic represents data as *references*. A "property" on a traditional data type is a value that the type in question will hold. In Pydoptic, a "property" is a *description* of a value. This description can be used to store a value in an object and retrieve just as in a traditional model, but it can *also* be used to store it in a data backend and retrieve it, or query it, or update it, or... anything else that might need to be done with it!

Here is what a Pydoptic version of the data model above looks like:

```python3
from pydoptic import *
from datetime import date

class Address(BaseModel):
    number: Prop['Address', str]
    street: Prop['Address', str]
    city: Prop['Address', str]
    postal_code: Prop['Address', str]
    state: Prop['Address', str]

class Organization(BaseModel):
    name: Prop['Organization', str]
    address: Prop['Organization', Address]
    phone_number: Prop['Organization', str]
    owner: PropOpt['Organization', 'Person']
    members: PropOptArr['Organization', 'Person']

class Person(BaseModel):
    name: Prop['Person', str]
    address: Prop['Person', Address]
    birth_date: Prop['Person', date]
    phone_number: Prop['Person', str]
    organizations: PropOptArr['Person', Organization]
    is_active: Prop['Person', bool]
```

While the type signatures require a bit more boilerplate, the information they provide to the type checkers is extremely powerful. Let's see what it can do for us.

### Basics

Let's start with the basics. We can construct a model instance in the usual way:

```python3
person = Person(name="John", address=Address(...), birth_date=..., phone_number=..., is_active=True)

print(person.name)
# John
```

The above succeeds even though `organizations` is missing because organizations is a `PropOptArr`, which is optional (hence `Opt`). Note that your type checker will complain that `person.name` is a `Prop` instead of a `str`. While Pydoptic does assign properties as model attributes (the `Prop` types should be defined only on the class), your type checker will not know this. The "Pydoptic" way to retrieve properties is not to access the attribute directly, but use the property itself!

```python3
person_name = Person.name.get_val(person)

print(person_name)
#John
```

Your type checker will recognize `person_name` as having a type `str`. While this is a fairly verbose way of getting a simple value, its utility will become clearer when you find yourself frequently accessing nested data. Consider, for instance, if you want 

```python3
select_related_statuses = Person.organizations(Organization.members)(Person.is_active)

statuses = related_status_select.get(person).as_list
print(statuses) 
# [True, False, False, True, ...]

related_status_select.update(lambda status: !status)

statuses = related_status_select.get(person).as_list
print(statuses) 
# [False, True, True, False, ...]
```

As your type checker should indicate, `select_related_status` is a `Selector[Person, bool]`, which we can use to retrieve and update all `is_active` properties nested within the original `person` via the path `organizations` -> `members` -> `is_active`. Since `Person.organizations` and `Organization.members` are optional properties, ordinarily retrieving and updating these values would require checking for `None` multiple times. Here is how you would do the same update in the ordinary way:

```python3
if person.organizations is not None:
    for organization in organizations:
        if organization.members is not None:
            for member in members:
                member.is_active = !member.is_active
```

The compositional properties of our `Prop` fields allow us to collapse all of that conditional logic into a single method `.update(lambda status: !status)`. Each `Prop[A, B]` can be chained with a `Prop[B, C]` to get a `Select[A, C]`. A `Select[A, C]` can be chained with a `Select[C, D]` (which could be a `Prop[C, D]`) to get a new `Select[A, D]`, and so on. All of the logic needed for getting from and setting to those nested fields is taken care of for you.

### Incomplete data

By separating our property types from the actual container, handling incomplete data becomes much simpler. The same `Prop`s we use to set and retrieve data a model like `Person` can be used to do the same in incomplete models as well.

```python3
partial_person: PartialModel[Person] = Person.partial(name="John", birth_date=...)

print(Person.name.get_val_unsafe(partial_person))
# John

person_dict = {'name': 'John'}
print(Person.name.get_val_unsafe(person_dict))
# John
```

As you can see in the example above, there are two ways to represent incomplete data. `PartialModel` is a model type that can have missing properties and extraneous properties, but any property whose name corresponds to a property on the full model must be valid. Hence `Person.partial(name=23)` would fail because `23` is not a string. This is useful when you are consuming partial data from a data source but still want to validate it. If you don't want to validate the data, you can also just use a `dict`. If you know your data source is producing valid data, it often makes sense to just keep your data in an untyped `Dict[str, Any]`.

All of the data manipulation methods used on full models have versions that can be used on `PartialModel`s and `dict`s. Methods with the suffix `_unsafe` will work exactly like the regular method, but will raise a `ValueError` when required data is missing (or invalid in certain ways); methods with the suffix `_safe` will return `None` when data is invalid.

### Data integration

Since `Prop`s contain all the information about the properties they reference, they can easily be used to configure and query data backends. This repository includes an example Elasticsearch integration as a reference. Here is what it looks like to use the pydoptic-based Elasticsearch API:

```python3
from pydoptic import Prop, PropOptArr, PartialModel
from pydoptic_elastic import ElasticModel, Query, ElasticService, elastic_prop, ESMapping
from datetime import date
from elasticsearch import Elasticsearch

class Address(ElasticModel):
    ...

class Organization(ElasticModel):
    ...

class Person(ElasticModel):
    name: Prop['Person', str]
    address: Prop['Person', Address]
    birth_date: Prop['Person', date]
    phone_number: Prop['Person', str] = elastic_prop(mapping=ESMapping.keyword)
    organizations: PropOptArr['Person', Organization]
    is_active: Prop['Person', bool]

query: Query[Person] = Query.match(Person.name, "John")

elastic_service = ElasticService(Elasticsearch('http://localhost:9200'))

person: PartialModel[Person] = elastic_service.search_partial(query, source=[Person.name, Person.birth_date])

print(Person.name.get_val_unsafe(person))
# John
```



