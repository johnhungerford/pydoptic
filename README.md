# Pydoptic

A data modeling library based on reified optics.

A good alternative to Pydantic when one or more of the following is true:
1. You rarely use complete instances of your modeled data
2. You frequently need to retrieve and manipulate deeply nested values
3. You neeed a type-safe way to refer to properties when querying remote data

## Why?

In every programming language, data is modeled as a type of container used to store it in memory. In Python, this generally looks something like the following:

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

While the above class definitions do provide a typed description of the data we expect to deal with, their utility when it comes to *doing* anything with the data is actually fairly limited. At most they can do the following:

1. Validate and then represent a complete instance of each data type, either from parameters or some serialized source (e.g., JSON)
2. Provide access to any property that can be validated with a type checker
3. Generate a valid serialized representation of an instance (e.g. JSON)

While this is certainly useful, consider all the other things we might want to do:

1. Consume and validate an *incomplete* instance of our data (e.g., a `Person`'s `name` and `birth_date`, but nothing else) without making the *complete* data model less precise (e.g., by making `Person.address` optional)
2. Access potentially missing values of an incomplete model
3. Query just the `name` and `birth_date` from a database. Nothing in the data model allows us to *specify the field itself* -- only the *value* of the field. This is an important distinction.
4. Update the `is_active` flag of every member of every organization a given person is a member of without having to check if `Person.organizations` or `Organization.members` are `None`.

Achieving these things with ordinary data models is inconvenient at best. Dealing with incomplete data requires defining new types for each use case or abandoning type safety altogether. While data models can read and write (complete) records to a datastore, they provide no mechanism for helping us specify the parts of the data model that are of interest to us, like when we want to specify which fields to retrieve or define a query setting some constraint on a particular field. In general we have to specify field names as strings, losing any pre-runtime validation. Finally, traditional data models provide no abstractions for manipulating nested data, nor do they provide any mechanism that could be used to create such abstractions.

Pydoptic provides an alternative way to model data in Python -- and indeed in any language -- that allows you to accomplish all these and things much more easily and safely.

## How?

Whereas traditional data models represent data as *containers* of properties, Pydoptic models data as collections of *references* to properties. In a traditional data type, a "property" is a value contained by an in-memory record of the type in question. In Pydoptic, a "property" is a *description* of a value belonging to a type. This description can be used to store a value in an object and retrieve just as in a traditional model, but it can *also* be used to store it in or retrieve it from a data backend, or query it, or update it, or... pretty much anything else you can think of that might need to be done with it!

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

The type signatures of the properties require some more boilerplate, to be sure. Most notably, they all contain references to the model class that they belong to. This may seem redundant, but it's a crucial feature that makes them as powerful as the are: because they contain references back to the classes they belong to, they can be used entirely independently of those classes. Each property -- which is only a *class* attribute -- is initialized with a value containing references to both its "origin" type (the model class) and its "target" type (the second type parameter on the right) as well as the attribute name and flags indicated whether it's optional (for `PropOpt` properties), array (`PropArr`), or both (`PropOptArr`).

By constructing our properties as comprehensive metadata *about* values and their relationship with the model they belong to, rather than simply the values themselves, we provide ourselves with a much more flexible and powerful tool. Let's see what we can do with them.

### Basics

Let's start with the basics. These "props" would not be much use to us if we could not actually construct model instances. It turns out we can do this in the usual way:

```python3
person = Person(name="John", address=Address(...), birth_date=..., phone_number=..., is_active=True)

print(person.name)
# John
```

On initialization, the mode class constructs the `Prop` class attributes based on the type hints and keeps track of them internally. It then uses the known properties to validate keyword arguments that are provided when constructing a class instance. The above succeeds even though `organizations` is missing because organizations is a `PropOptArr`, which is optional. If we left out `name`, however, it would raise a `ValueError`.

Note that your type checker will complain that `person.name` is a `Prop` instead of a `str`. While Pydoptic does assign properties as model attributes (the `Prop` types should be defined only on the class), your type checker will not know this. The "Pydoptic" way to retrieve properties is not to access the attribute directly, but use the property itself!

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

As your type checker should indicate, `select_related_status` is a `Select[Person, bool]` which is composed from the `Prop`s `Person.organizations`, `Organization.members`, and `Person.is_active`. This particular chain of props can compose because each prop's *target* type is the same as the *origin* type of the prop chained to it. When this is not the case (meaning the chaining is *invalid*), the type checker will complain. The resulting `Select` can then be used to retrieve and update all `Person.is_active` properties (the final `Prop` in the chain) nested within the original `person` via the path `organizations` -> `members` -> `is_active`. Since `Person.organizations` and `Organization.members` are optional properties, ordinarily retrieving and updating these values would require checking for `None` multiple times. Here is how you would do the same update in the ordinary way:

```python3
if person.organizations is not None:
    for organization in organizations:
        if organization.members is not None:
            for member in members:
                member.is_active = !member.is_active
```

The compositional properties of our `Prop` fields allow us to collapse all that conditional logic into a single method `.update(lambda status: !status)`. All of the logic needed for getting from and setting to those nested values is taken care of for you.

### Incomplete data

By separating our property types from the actual container, handling incomplete data becomes simpler without losing type precision. The same `Prop`s we use to set and retrieve data a model like `Person` can be used to do the same in incomplete models as well.

```python3
partial_person: PartialModel[Person] = Person.partial(name="John", birth_date=...)

print(Person.name.get_val_unsafe(partial_person))
# John

person_dict = {'name': 'John'}
print(Person.name.get_val_unsafe(person_dict))
# John
```

As you can see in the example above, there are two ways to represent incomplete data. `PartialModel` is a model type that can have missing properties and extraneous properties, but any property whose name corresponds to a property on the full model must be valid. Hence `Person.partial(name=23)` would fail because `23` is not a string. This is useful when you are consuming partial data from a data source but still want to validate it. If you don't want to validate the data at all, you can also use a `dict`. If you know your data source is producing valid data, it often makes sense to just keep your data in an untyped `Dict[str, Any]`.

All of the data manipulation methods used on full models have versions that can be used on `PartialModel`s and `dict`s. Methods with the suffix `_unsafe` will work exactly like the regular method, but will raise a `ValueError` when required data is missing (or invalid in certain ways); methods with the suffix `_safe` will return `None` when data is invalid or (for mutating methods) fail silently.

### Data integration

Since `Prop`s contain all the information about the properties they reference, they can easily be used for interacting with *remote* instances of the same data. This repository includes an example Elasticsearch integration as a reference. Here is what it looks like to use the pydoptic-based Elasticsearch API:

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

elastic_service = ElasticService(Elasticsearch('http://localhost:9200'))

elastic_service.create_index(Person)

original_person = Person(name='John', ...)

elastic_service.index(original_person)

query: Query[Person] = Query.match(Person.name, Person.get_val(original_person))

found_people: List[PartialModel[Person]] = elastic_service.search_partial(query, source=[Person.name, Person.birth_date])

for found_person in found_people:
    print(Person.name.get_val_unsafe(person))
    # John
```

The above data model is built using the `ElasticModel` base class, which is a specialized subtype of `BaseModel` that captures property metadata specifically for Elasticsearch (e.g., the index name and field mappings). `Prop`s can be customized with `elastic_prop` to include field-level metadata like `mapping` (the `Prop` type has a metadata field for storing arbitrary key-value data for use cases like this).

`Query` is a representation of queries based on Pydoptic types. For instance, the match query is constructed by using a `Prop` value to specify the field to match with and providing a value corresponding to that prop's target type. The result, when querying `Person.name` is a `Query[Person]`. `Query[Person]` contains a reference to the `Person` class, which can be used to resolve the appropriate index name.

`ElasticService` provides an API for dealing with indices and documents using the Pydoptic-based `ElasticModel` and `Query` types. We first create our `Person` index by simply passing the class to `elastic_service.create_index`. The index name is generated by default from the class name (`person`) and the field mappings are constructed from the properties. We then index a document by passing it to `elastic_service.index`; since the instance contains a reference to the class, the index name can be resolved properly. Finally, we search for the original person by using our `Query[Person]`, which matches on the original person's name. When searching, however, we use a special variant `elastic_service.search_partial` which allows us to provide a `source` parameter, where we specify only two `Person` properties: `Person.name` and `Person.birth_date`. The result is a list of `PartialModel[Person]` instances containing only those fields.

You'll notice at no point in the above are we forced to pass any index or property names as strings. All the information required to resolve the indices and fields are contained in our model types.

### Reified optics

I hope the above has indicated clearly enough how pydoptic can be used to solve the problems indicated in the first section. At this point its worth saying a few words about the approach used.

Pydoptic is inspired by a concept from functional programming called "optics". In functional programming optics are not just useful but pretty much necessary due to the relative difficulty of updating nested properties in immutable data structures. In imperative languages like Python, this is generally easier to do so they tend not to be used much. There a couple of optics libraries out there for Python, but they try to be functional in the full sense, which is to say they are designed to create immutable copies of dataclasses rather than mutate them.

Pydoptic's approach is the first to my knowledge to take the compositional properties of optic types from functional programming while giving them power to mutate objects. The second way it differs from most functional optics libraries is in "reifying" the optics. In functional programming, optics are functions that retrieve or update data and can be composed in various ways; in Pydoptic, they are, at bottom, *descriptions* of the things that can be accessed or updated. It is this latter feature that gives them much more *general* power than traditional optics.

This concept of "reified optics" comes from the Scala project [ZIO schema](https://zio.dev/zio-schema/), which provides (among other things) a similar mechanism for referencing properties via "accessors". Pydoptic provides a simplified version of this approach appropriate to Python and its more limited (though still quite powerful!) type system. The main innovation of Pydoptic (beyond bringing optics to mutable data) is that it models data "optics-first," unlike ZIO-schema, which (for good reasons connected with Scala and the JVM) *derives* optics *from* traditional data models (i.e., data classes).
