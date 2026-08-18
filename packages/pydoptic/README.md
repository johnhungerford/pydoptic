# pydoptic

The core data modeling library based on reified optics. See the
[repository README](https://github.com/johnhungerford/pydoptic) for what reified optics are and why
they're useful -- this document is the in-depth user guide: defining and constructing models, reading
and mutating data, chaining selects, discriminated subtypes, and integrating with external APIs.

## Installation

```bash
pip install pydoptic
```

## User guide

The examples below assume this import, unless a different one is shown:

```python3
from pydoptic import (
    BaseModel, PartialModel, select,
    Discrim, Prop, PropArr, PropOpt, PropOptArr, PropSelect,
    Select, SelectArr, SelectOpt, SelectOptArr, SelectVal, SelectValue,
)
from typing import Any, Dict, List
```

### Defining and constructing models

There are two basic units of data in Pydoptic: `BaseModel` and `PropSelect[A, B]`, where `A` is some subtype of `BaseModel`. Models of type `BaseModel` are defined by their `PropSelect` class attributes, which are class attributes describing what values can be stored in or retrieved from the model:

```python3
class Model1(BaseModel):
    prop_1: Prop['Model1', int]
    prop_2: Prop['Model1', str]
```

It is tempting to think of `prop_1` and `prop_2` as defining the attibutes available on instances of `Model1`. While this is true, it is a limiting perspective. It is better to think of `Model1` and its `Prop`s in more abstract terms: `Model1` describes *anything* -- whether in memory or stored a remote database -- that has the `Prop`s belonging to it.

Moreover, `prop_1` and `prop_2` are not just type definitions -- they are actual values that exist on the class. You can confirm this by running the following:

```python3
print(f'Model1.prop_1 describes a property on {prop_1.origin} with a type {prop_1.target} under the key {prop_1.label}')

# Output:
# Model1.prop_1 describes a property on <class '__main__.Model1'> with a type <class 'int'> under the key prop_1
```

Any subclass of `BaseModel` will automatically construct the appropriate values for every `Prop` you include on the class definition, setting the `label` field with the attribute name, and setting the `origin` and `target` fields with the type parameters you provide. You can also customize the property as follows:

```python3
class Model2(BaseModel):
    prop_1: Prop['Model2', int] = select('prop_one', sql_metadata='PRIMARY KEY')
    prop_2: Prop['Model2', str] = select('prop_two', sql_metadata='FOREIGN KEY')

print(f'{prop_1.label}: {prop_1.origin} -> {prop_1.target})
print(f'Property data: {prop_1.data})
# Output:
# prop_one: <class 'Model2'> -> <class 'int'>
# Property data: {'sql_metadata': 'PRIMARY_KEY'}
```

In the above example, the `select` function is used to customize `prop_1` and `prop_2`, providing different `label`s ("prop_one" and "prop_two") and adding some metadata. As we can see when we log the `data` attribute of the resulting `Prop`, the keyword arguments we provide to the `select` function are captured in the `Prop` in the form of a `dict`. The metadata in the example above could be used to generate a SQL table from `MyModel`, or interpret `join` queries using `prop_2`.

Once you define a model, there are kinds of instances we can construct:

```python3
# Fully validated model
model_1_kw: Model2 = Model2(prop_one=42, prop_two="hello")
model_2_pr: Model2 = Model2.construct(Model1.prop_1.param(42), Model1.prop_2.param("hello"))

# Partial model
model_1_partial_kw: PartialModel[Model2] = Model2.partial(prop_one=42)
model_1_partial_pr: PartialModel[Model2] = Model2.construct_partial(
    Model.prop_2.param("hello"),
)

# Dict
model_1_dict: Dict[str, Any] = {'prop_one': 42}
```

Instances of the model can be constructed the same way as Pydantic, using keyword arguments to pass property values to the constructor. Note that, unlike Pydantic, your IDE or type checker is not going to give you any help with this. Pydantic provides plugins to support this; this would not be possible for Pydoptic since the property names can be manually customized. In `Model2`, for instances, the keywords we have to provide for our constructor arguments ("prop_one" and "prop_two") are different from the names of those properties in the class definition (`prop_1` and `prop_2`).

To help us ensure we're using the correct properties, we have `construct` variants for constructing models and partial models using the `Prop`s themselves instead of strings. These variants accept a vararg list of `Param`s, which you can construct by calling the `param` method on each of your required `Prop`s. While more verbose, it will ensure that the values you provide match the `Prop` types and means you don't have to remember the property names. The only thing it won't ensure is exhaustivity.

Partial models are models that can be missing any or all of the properties declared on the model class. However, the properties it *does* must be otherwise valid. The following would raise an exception:

```python3
partial_model = Model2.partial(prop_one="wrong type!", other_prop="unrecognized property!")
```

Both full models and partial models can be configured to ignore unknown extra arguments by passing `_allow_extra_args=True`. In this case, unrecognized arguments will be silently ignored.

```python3
# No exception:
partial_model = Model2.partial(prop_one=1, other_prop="unrecognized property!")

partial_model.prop_one # 1
partial_model.other_prop # raises AttributeError
```

The last valid model instance is a simple `Dict`. These need not have any reference to the model type in their type signature.

#### Property types

There are four different property types that can be included in a Pydoptic model:
1. `Prop[A, B]`: a required value of type `B`
2. `PropOpt[A, B]`: an optional value of type `B`, equivalent to `B | None`
3. `PropArr[A, B]`: a required array value of type `B`, equivalent to `List[B]`
4. `PropOptArr[A, B]`: an optional array value, equivalent to `List[B] | None`

While it is in principle possible for you to simply use `Prop` for each of these, describing optional values as `Prop[A, B | None]`, array values as `Prop[A, List[B]]`, and optional arrays as `Prop[A, List[B] | None]`, this will limit the composability of your properties, making them substantially less useful. It is therefore very important to use the different `Prop` variants for capturing options and lists.

Moreover, once you have defined your properties using the specific `-Opt` and `-Arr` variants, you can always zoom out using the `.value` method:

```python3
class MyModel(BaseModel):
    required_prop: Prop['MyModel', int]
    optional_prop: PropOpt['MyModel', str]
    array_prop: PropArr['MyModel', float]
    opt_arr_prop: PropOptArr['MyModel', bool]

opt_prop_value: Prop['MyModel', str | None] = MyModel.optional_prop.value
arr_prop_value: Prop['MyModel', List[float]] = MyModel.array_prop.value
opt_arr_prop_value: Prop['MyModel', List[bool] | None] = MyModel.opt_arr_prop.value
# There is also an `option` method on `PropOptArr` to reframe
# the property as an optional list
opt_arr_prop_option: PropOpt['MyModel', List[bool]] = MyModel.opt_arr_prop.option
```

Reframing your array and optional properties in this way can be useful in cases where you want to set or update an array as a whole, for instance, or you want to update optional fields depending on whether or not they are empty ([see below](#reading-and-mutating-data)). But while it's easy to convert an optional or array property to a regular (required) property in this way, due to the Python's type system it's not so easy to convert in the other direction. For this reason you should always start with the more specific property types.

The different property types are also important because they are used in validation. `PropOpt` and `PropOptArr` properties do not need to be provided in constructor arguments to generate a valid models. `PropArr` and `PropOptArr` properties must be lists when provided, and their members will be validated according to the specified type:

```python3
valid_1 = MyModel(
    required_prop=23,
    optional_prop="value",
    array_prop=["hello", "world"],
    opt_arr_prop=[True],
)
valid_2 = MyModel(required_prop=23, array_prop=["hello", "world"]) # optional_prop omitted
invalid = MyModel(
    # Missing required property `required_prop`!
    optional_prop="value",
    array_prop="string instead of array of strings!",
    opt_arr_prop=[True, False, "string instead of bool!"],
)
```

If you used `Prop['MyModel', str | None]` for `optional_prop` instead of `PropOpt`, you would have to explicitly pass `optional_prop=None` to construct a valid model and `valid_2` would turn out to be *invalid*.

#### Validators

Pydoptic has special logic for handling optional and list types, but for all other types, the only validation it is does is simple `isinstance` checks. To customize your model to perform more elaborate validation, you must provide your own validators. In most cases, this should be done on the class as follows:

```python3
def int_validator(value: Any) -> str | None:
    if isinstance(value, int):
        return None 
    if isinstance(value, float):
        if floor(value) == value:
            return None
    return '{value} is not an integer'

class Model(BaseModel):
    validators = {
        int: int_validator
    }

    prop_int: Prop['Model', int]

valid_model_1 = Model(prop_int=23) # Valid because it's an integer
valid_model_2 = Model(prop_int=23.0) # Valid because it's a float with no decimals
invalid_model = Model(prop_int=23.01) # Invalid because float is not integer
```

A "validator" is a function that consumes a value and returns an error message if it's invalid and `None` if it's valid. It can be registered in the model's `validators` class attribute with the associated type as the key. In the above example, `int_validator` provides an error if the value is not an `int` or a `float` that is not equivalent to an integer. Now when we construct a model instance with a float, it only fails if the float has decimal values.

If you are using a model that lacks appropriate validation, you can customize validation on construction. To do this, you can pass custom validators under the special keyword parameter `_validators`. The format should be the same as before:

```python3
class Model(BaseModel):
    prop_int: Prop['Model', int]

valid_model_1 = Model(prop_int=23)
valid_model_2 = Model(prop_int=23.0, _validators={int: int_validator})
invalid_model_1 = Model(prop_int=23.01, _validators={int: int_validator})
invalid_model_2 = Model(prop_int=23.0) # Invalid without custom validator
```

`_validators` can be passed to both complete models and partial models.

#### Serialization

While Pydoptic does not include native serialization and deserialization yet, complete and partial models can be converted to and from `dict` instances easily, from which they can be serialized using any JSON library.

To convert to dict and serialize:

```python3
import json

model: MyModel = MyModel(prop_1='value', prop_2=23, ...)
dict_value: Dict[str, Any] = model.as_dict_full()
str_value: str = json.dumps(dict_value)

partial_model: PartialModel[MyModel] = MyModel.partial(prop_1='value', prop_2=23, ...)
partial_dict: Dict[str, Any] = partial_model.as_dict_full()
partial_str: str = json.dumps(partial_dict)
```

Converting from a dictionary can be accomplished by simply providing a dict to a constructor as keywords:

```python3
import json

str_value: str = ???
dict_value: Dict[str, Any] = json.loads(str_value)
model: MyModel = MyModel(**dict_value)

partial_str: str = ???
partial_dict: Dict[str, Any] = json.loads(partial_str)
partial_model: PartialModel[MyModel] = MyModel.partial(**partial_dict)
```

Note that given how data can be read from and written to objects, there is no necessity that you validate to models or even partial models at all. My own preferred workflow is to use models for ingestion only -- that is, to consume external data and convert them to my domain in the form of Pydoptic models, and then feed these into the data backend. Once valid data is persisted in a backend, it can then retrieved and manipulated in the form of `dict`s, without ever having to generate a full model. This is a matter of preference, however.

#### Typed model attributes

One striking problem with Pydoptic's way of defining models is that it confuses IDEs and type checkers about the attributes on instances of models. Say, for instance, you have the following model and construct a valid instance of it:

```python3
class MyModel(BaseModel):
    int_value: Prop['MyModel', int]
    str_value: Prop['MyModel', str]

model_instance = MyModel(int_value=23, str_value="hello")
```

If you try to access `model_instance.int_value`, your IDE/type checker will think you are accessing the `Prop` class attribute, not the `int` object attribute. This is an annoyance if you want to access those object attributes directly, but remember that Pydoptic's design encourages using the `Prop`s themselves to do access the data. The Pydoptic way to retrieve the value we want is to call `MyModel.int_value.get_val(model_instance)`. The result of this expression will be accurately typed as `int`.

It is understandable, however, given the relative verbosity of the Pydoptic approach, that users may not want to use `Prop`s all the time. If it's important to you to have typed object attributes, you can get around the problem by defining your models as follows:

```python3
class MyModel(BaseModel):
    int_value_prop: Prop['MyModel', int] = property('int_value')
    int_value: int

    str_value_prop: Prop['MyModel', str] = property('str_value')
    str_value: str
```

This approach requires more boilerplate, and you need to take care that your property label overrides match up to the attribute names you use, but it will provide you with the best of both worlds.

### Reading and mutating data

`Prop`, `PropOpt`, `PropArr`, and `PropOptArr` are all subtypes of the base class `Select[A, B]`, which represents some data of type `B` selected within some container of type `A`. This nesting can be both deep and complicated, involving potentially missing values (`PropOpt`), multiple values (`PropArr`), or both (`PropOptArr`). No matter how deeply the data is nested, or how complicated the nesting, the data can always be accessed and manipulated with the same few basic methods. We will begin with these *generic* methods before looking at more methods specific to the non-optional, optional, and array-like variants.

#### `get`, `get_unsafe`, `get_safe`

To retrieve a selected value from a complete model, use the `get` method. This will not return the value directly, however. Instead it will return a `SelectValue[B]` (where `B` is the selected data type). A `SelectValue` contains the selected value in an attribute `value`. The type of `value`, however, is not `B` but `B | List[B] | None`. This is because `get` doesn't know if the `Select` in question is any `-Arr` type, or an `-Opt` type, or both, or neither. This is the challenge of using generic `Select`s.

If you happen to know what kind of properties are selected, you can cast as needed, but if you don't, `SelectValue` provides some other useful methods. First, you can find out what type to expect by looking at the `is_opt` and `is_arr` attributes. These can tell you whether to expect an optional or array type. What may be more useful, however, is to convert the value using `as_arr` or `as_opt`. `as_arr` will keep a list result as a list, but it will turn an empty option into an empty list and a non-empty non-list value into a list of length one. This is useful if don't care whether there are multiple values and just want to use whatever values you get.

Consider, for example, a case where you have a model for an `Organization` and you need to make some kind of remote network request for any point of contact associated with the organization. In this case you can design your logic around a generic selector, without having to know whether it is will return many, one, or no values:

```python3
class Person(BaseModel):
    ...

class Organization(BaseModel):
    ...

def handle_point_of_contacts(org_service: OrgService, poc_select: Select[Organization, Person]):
    organization: Organization = org_service.retrieve_organization()
    pocs: SelectValue[Person] = poc_select.get(organization)
    for poc in pocs.as_list:
        org_service.contact_person(poc)
```

Conversely, if you only wanted to contact one POC (and you don't care whether there are others) you could do the following:

```python3
    poc: Person | None = poc_select.get(organization).as_opt
    if poc is not None:
        org_service.contact_person(poc)
```

In the above case, if there are many `Person`s selected byte `poc_select`, only the first one will be returned. If none are, `poc` will be `None`.

To retrieve values from an incomplete representation of the data, such as a `PartialModel` or a `dict`, there are two variants of `get` that you can use. `get_unsafe` will try to retrieve the selected value and fail with a `ValueError` if it's inaccessible due to invalid data (if its inaccessible due to a valid optional property being missing, it will generate an empty `SelectValue` as expected). `get_safe`, on the other hand, will always fail silently, generating empty `SelectValue` when data is missing.

Note that the type signature of `get_unsafe` and `get_safe` are a bit misleading. They will provide accurate types for non-model values (e.g., primitive properties like `int` or `str`), but they will treat nested models as though they are fully typed. When you retrieve a nested model from a `dict` or `PartialModel`, however, in all likelihood it is going to be another `dict` or `PartialModel`.

```python3
class Inner(BaseModel):
    prop: Prop['Inner', int]

class Outer(BaseModel):
    inner: Prop['Outer', Inner]

# A `Select` that chains two props together (see next section)
prop_select: Select[Outer, int] = Outer.inner(Inner.prop)

full_val = Outer(inner=Inner(prop=23))
# Accurately typed
prop_result_full: SelectValue[int] = prop_select.get(full) 
# Accurately typed
inner_result_full: SelectValue[Inner] = Outer.inner.get(full) 

partial_val = Outer.partial(inner=Inner.partial(prop=23))
# Accurately typed
prop_result_partial: SelectValue[int] = prop_select.get_unsafe(partial_val)
# Inaccurate type! Should be SelectValue[PartialModel[Inner]]
inner_result_partial: SelectValue[Inner] = Outer.inner.get_unsafe(partial_val) 

dict_val = {'inner': {'prop': 23}}
# Accurately typed
prop_result_dict: SelectValue[int] = prop_select.get_unsafe(dict_val)
# Inaccurate type! Should be SelectValue[Dict[str, Any]]
inner_result_dict: SelectValue[Inner] = Outer.inner.get_unsafe(dict_val) 
```

This is an unavoidable result of the fact that selectors are defined in terms of classes. Be sure to cast as appropriate when retrieving incomplete models using `Select`s.

#### `update`, `update_unsafe`, `update_safe`

To mutate nested data, the most powerful method is `update` and its variants. `update` allows you to pass a function that takes a value of the selected type and returns a new value. Any selected value found by the `Select` will be replaced with the new value. This allows you to change values without having to call `get` first to see what data is present.

The behavior of `update` depends on the `Select`. For required, non-array `Select`s, it will simply transform the selected value. For optional, non-array selects, it will transform the selected value *if it is defined*. For array `Select`s, it will transform *all* the selected values.

```python3
class Inner(BaseModel):
    prop: PropArr['Inner', int]

class Outer(BaseModel):
    inner: PropArr['Outer', Inner]

prop_select: Select[Outer, int] = Outer.inner(Inner.prop)

value = Outer(inner=[Inner(prop=[1,2,3]), Inner(prop=[4,5,6])])

print(value)
# Outer(inner=[Inner(prop=[1,2,3]), Inner(prop=[4,5,6])])
print(prop_select.get(value).value)
# [1, 2, 3, 4, 5, 6]

# Add 1 to each prop
prop_select.update(value, lambda i: i + 1)

print(value)
# Outer(inner=[Inner(prop=[2,3,4]), Inner(prop=[5,6,7])])
print(prop_select.get(value).value)
# [2, 3, 4, 5, 6, 7]
```

In the example above, `prop_select` selects an `int` across *two* array properties. When we call `update`, the updater applies to every element, regardless of which "branch" of the nested arrays it's in. Pydoptic takes care of think through all of the nesting for you! In some cases, however, we may not want this. Consider the following example were want to update an optional property based on whether or not it's empty, and we want to add elements to an array property:

```python3
class Inner(BaseModel):
    prop_arr: PropArr['Inner', int]
    prop_opt: PropOpt['Inner', str]

class Outer(BaseModel):
    inner: PropArr['Outer', Inner]

# Call `.value` on properties to expose the full type
prop_arr_select: Select[Outer, List[int]] = Outer.inner(Inner.prop_arr.value)
prop_opt_select: Select[Outer, str | None] = Outer.inner(Inner.prop.value)

value = Outer(inner=[Inner(prop_arr=[1,2,3]), Inner(prop_arr=[4,5], prop_opt="hello")])

# Add the length of each array to the array
prop_arr_select.update(value, lambda arr: [*arr, len(arr)])
# Replace any `None`s with "hello" and replace any non-empty values with `None`
prop_opt_select.update(value, lambda opt: if opt is None then "hello" else None)

print(value)
# Outer(inner=[Inner(prop_arr=[1,2,3,3], prop_opt="hello"), Inner(prop_arr=[4,5,2], prop_opt=None)])
```

By using `Select`s that expose the optional and list types by calling `value` on the props, we can have access to the entire list or the entire option in our updater function. Note that `update` requires a pure function: it will replace the existing value with a new value you provide. This is why we need to reconstruct the entire list using the spread operator rather than just calling `append` (which mutates the list in place, but returns `None`). This is not always ideal for mutating lists; an alternative way to update `prop_arr` is simply to retrieve all of the lists and then mutate them in a for loop.:

```python3
for arr in prop_arr_select.get(value).as_list:
    arr.append(len(arr))
```

To update incomplete data, use `update_unsafe` and `update_safe`. `update_unsafe` will fail with an exception if it's unable to access the data to be updated due to invalid data, whereas `update_safe` will simply ignore (and therefore skip) invalid cases. Like `get`, you need to be careful when updating nested models with the partial variants of `update`. The types will appear to be complete models when they are most likely `PartialModel`s or `dict`s.


#### `set`, `set_unsafe`, `set_safe`

`set` can be used to set selected values. `set` mostly makes sense only for non-array values. To `set` values in an array selector means you will set the same value for every element in every array! To set the array as a whole, use `.value` to expose the `List` type in your array property selector:

```python3
class Inner(BaseModel):
    prop_arr: PropArr['Inner', int]

class Outer(BaseModel):
    inner: PropArr['Outer', Inner]

prop_arr_select: Select[Outer, int] = Outer.inner(Inner.prop_arr)
# Call `.value` on properties to expose the full type
prop_arr_select_list: Select[Outer, List[int]] = Outer.inner(Inner.prop_arr.value)

value = Outer(inner=[Inner(prop_arr=[1,2,3]), Inner(prop_arr=[4,5])])

# Set each element
prop_arr_select.set(value, 4)

print(value)
# Outer(inner=[Inner(prop_arr=[4,4,4]), Inner(prop_arr=[4,4])])

# Set each array
prop_arr_select_list.set(value, [7,8,9])

print(value)
# Outer(inner=[Inner(prop_arr=[7,8,9]), Inner(prop_arr=[7,8,9])])
```

Using the regular `Select`, each element of each `prop_arr` is set to `4`. When we use the `Select` based on `Inner.prop_arr.value` instead of `Inner.prop_arr`, we are able to set each `prop_arr` to `[7,8,9]`.

`set_unsafe` and `set_safe` work the same way as `update_unsafe` and `update_safe`: the `_unsafe` variant raises `ValueError` when it encounters invalid data whereas the `_safe` variant just skips it.

#### `clear`, `clear_unsafe`, `clear_unsafe_strict`, `clear_safe`, `clear_safe_strict`

We have already seen how removing values can be tricky using `Select`. Unless you call `value` to expose optional or array types, you can only *change* values that exist or *insert* new values. For this reason, we have included a set of `clear` methods specifically for removing values.

`clear` is designed to be as flexible as possible to make it easy to remove data in a variety of circumstances without having to think much about what `Select` to use. The result of this, however, is that you have to be careful about how you use it since the behavior will changed depending on your model and how your `Select` is constructed. Make sure you understand its behavior before you use it:
1. `clear` will only remove data on "clearable" properties. Any optional property can be cleared by setting it to `None`, and any array property can be cleared by setting it to an empty array. If a property is an optional array, it is cleared by being set to `None`.
2. `clear` will try to clear the *selected* property, but if it can't, it will try to clear the next property the selected property is chained from. If `model.prop_1.prop_2.prop_3` is a required field, for instance, it will try to clear `model.prop_1.prop_2` (and so on).
3. If none of the properties in the chain are clearable, it will raise a `ValueError`.

```python3
class C(BaseModel):
    req: Prop['C', int]
    opt: PropOpt['C', int]

class B(BaseModel):
    c: PropArr['B', C]

class A(BaseModel):
    b: Prop['A', B]

sel_req = A.b(B.c)(C.req)
sel_opt = A.b(B.c)(C.opt)

value = A(b=B(c=[C(req=1, opt=10), C(req=2, opt=11)]))

sel_opt.clear(value)

print(value)
# A(b=B(c=[C(req=1, opt=None), C(req=2, opt=None)]))

sel_req.clear(value)

print(value)
# A(b=B(c=[]))
```

In the above example, while `sel_opt` is able to clear the `opt` property, `sel_req` cannot clear the selected `req` property so instead it clears the next clearable property, setting `c` to an empty array.

Clearing partial data is even more complicated, since partial data (`PartialModel`s and `dict`s) *can* be cleared even when its required in the model. For this reason, the partial variants of `clear` are distinguished into "strict" and "non-strict" variants. `clear_unsafe_strict` works just like `clear`: it will only clear clearable (optional/array) properties, and will try to clear selected property and work its way backward across the property chain until it finds a clearable property. `clear_unsafe`, on the other hand, will clear the selected property whether or not it's a required field. `clear_safe_strict` and `clear_safe` work the same way, but does not raise exceptions when they encounter invalid data, but simply skip it and move on.

#### Precise `Select`s

As mentioned at the beginning of this section, the four operations described above (`get`, `update`, `set`, `clear`, and their variants) are available on every `Select`, whether a single property or a composite chain. It is possible to construct `Select`s, however, that are more specifically typed. The four property selects  -- `Prop`, `PropOpt`, `PropArr`, and `PropOptArr` -- capture more about what is selected than the generic `Select` type. For these `Select` subtypes, it is possible to retrieve data without the intermediate `SelectValue` result type, since it is known beforehand whether they select options, arrays, or both.

Accordingly, any of these more specific `Select` subtypes include a method `get_val` that will retrieve selected data in the appropriate type:

```python3
class Model(BaseModel):
    req: Prop['Model', int]
    opt: PropOpt['Model', int]
    arr: PropArr['Model', int]
    opt_arr: PropOptArr['Model', int]

value: Model = Model(...)

req_val: int = Model.req.get_val(value)
req_opt: int | None = Model.opt.get_val(value)
req_arr: List[int] = Model.arr.get_val(value)
req_opt_arr: List[int] | None = Model.opt_arr.get_val(value)

# `-OptArr` types also include a `get_arr` method to treat `None` as an empty list
req_o_a_list: List[int] = Model.opt_arr.get_arr(value)
```

On `PropOptArr` there is also a `get_arr` method which returns a `List[B]` instead of `List[B] | None`, converting `None` to an empty list. This will allow you to iterate over results without a null check.

As always, there are `_unsafe` and `safe` variants of `get_val` and `get_arr` methods for retrieving from partial data. Note that `get_val_safe` returns options, since data can be missing.

#### Chaining selects

We have already encountered several examples of chaining `Prop`s to generate a composite select. Any select can just be used as a function that takes another `Select` as a parameter to form a chained `Select`:

```python3
prop_1: Prop[A, B]
prop_2: Prop[B, C]
prop_3: Prop[C, D]
prop_4: Prop[D, E]

a_c: Select[A, C] = prop_1(prop_2)
d_e: Select[D, E] = prop_3(prop_4)

a_d_1: Select[A, E] = a_c(d_e)
a_d_2: Select[A, E] = prop_1(prop_2)(prop_3)(prop_4)
```

Note that you will get type errors if you try to chain a `Select[_, X]` with something other than `Select[X, _]`. The one exception is that you can chain `Select[_, X]` with `Select[Y, _]` if `X` is a *subtype* of `Y` (a property on `Y` must be on `X` if `X` is a subtype of `Y`).

Note also that when we chain in this way we get generic `Select`s. It is also possible to chain `Prop`s so that we retain the option/array information at the type level. You can do this by using `then_` variants to specify explicitly what kind of `Prop` or `Select` you are chaining to:

```python3
prop_1: Prop[A, B]
prop_2: Prop[B, C]
prop_3: PropOpt[C, D]
prop_4: Prop[D, E]
prop_5: PropArr[E, F]
prop_6: Prop[F, G]
prop_7: PropOptArr[G, H]

prop_8a: PropArr[H, I]
prop_8b: PropOpt[H, I]

# Val -> Val : Val
a_c: SelectVal[A, C] = prop_1.then_val(prop_2)
# Val -> Opt : Opt
b_d: SelectOpt[B, D] = prop_2.then_opt(prop_3)
# Opt -> Val : Opt
c_e: SelectOpt[C, E] = prop_3.then_val(prop_4)
# Val -> Arr : Arr
d_f: SelectArr[D, F] = prop_4.then_arr(prop_5)
# Arr -> Val : Arr
e_g: SelectArr[E, G] = prop_5.then_val(prop_6)
# Val -> OptArr : OptArr
f_h: SelectOptArr[F, H] = prop_6.then_opt_arr(prop_6)

# OptArr -> *anything* : OptArr (we can just call `.then`)
g_i_1: SelectOptArr[G, I] = prop_7.then(prop_8a)
g_i_2: SelectOptArr[G, I] = prop_7.then(prop_8b)

f_h_1: 
f_h_2: SelectOptArr[F, H] = (
    prop_1
    .then_val(prop_2)
    .then_opt(prop_3)
    .then_val(prop_4)
    .then_arr(prop_5)
    .then_val(prop_6)
    .then_opt_arr(prop_7)
    .then(prop_8a)
)
```

As we can see from the explicit type annotations, chaining `Prop`s using `then_X` variants results in different `Select-` types: `SelectVal`, `SelectOpt`, `SelectArr`, and `SelectOptArr`. These specific subtypes are the chained analogies to `Prop`, `PropOpt`, `PropArr`, and `PropOptArr` respectively. Like the `Prop`s, these can be used with `get_val` and `get_arr` to extract values directly with the correct types.

#### Discriminating subtypes

All of the `Select` types we have seen thus far involve selecting properties on models. There is one more `Select` type to cover which does something quite different: it selects a *subtype* of a model. Here is what it looks like:

```python3
class Super(BaseModel):
    ...
    prop: Prop['Super', bool]

class Sub1(Super):
    subtype: Discrim[Super, 'Sub1']
    prop_1: Prop['Sub1', int]

class Sub2(Super):
    subtype: Discrim[Super, 'Sub2']
    prop_2: Prop['Sub2', str]

class Root(BaseModel):
    super: PropArr['Root', Super]

value = Root(super=[Sub1(prop_1=23), Sub2(prop_2="hello")])

print(Root.super(Sub1.subtype)(Sub1.prop_1)(value).value)
# [23]

print(Root.super(Sub2.subtype)(Sub2.prop_2)(value).value)
# ["hello"]

Root.super(Sub1.subtype)(Sub1.prop_1).update(value, lambda i: i + 1)

print(value)
# Root(super=[Sub1(prop_1=24), Sub2(prop_2="hello")])
```

The `Discrim[A, B]` type is a `SelectOpt` that selects down from some value of supertype `B` to a subtype `A`, filtering out cases where it is not that subtype. Note that `Discrim` property is treated differently by `BaseModel` than regular properties. It generates a special string attribute `subtype` (or whatever the property name is) that is automatically set to the class name of the subtype when a model is constructed. The `Discrim` `Select` checks whether this string value matches the class name to conclude it is the correct subtype.

You can see the discriminator value if you convert a model to a `dict`:

```python3
value = Root(super=[Sub1(prop_1=23), Sub2(prop_2="hello")])

print(value.as_dict_full())
# {'super': [{'subtype': 'Sub1', 'prop_1': 23}, {'subtype': 'Sub2', 'prop_2': 'hello'}]}
```

### Integrating with external APIs

In order to use Pydoptic models with data APIs, such as a SQL backend, you will need to introspect models and `Select`s to use them to generate requests. Pydoptic provides several public methods to make this easier.

First, to inspect all the properties in a model, you can call `[ClassName].properties()`, which will return a list of all `Prop-` and `Discrim` properties on the model (in order of definition):

```python3
class Model(BaseModel):
    prop_1: Prop['Model', int]
    prop_2: Prop['Model', str]

all_props: List[PropSelect[Any, Any] | Discrim[Any, Any]] = Model.properties()

assert len(all_props) == 2
assert all_props[0] = Model.prop_1
assert all_props[1] = Model.prop_2
```

For each `Prop-` type you can extract the label, origin and target types, and data, using these to generate queries as appropriate.

If you want to use composite `Select`s in your API and not just `Prop-`s, you will probably need to break them down to examine each component `Prop-`. To do this, you can use the `segments` or `properties` attribute. `segments` will return a list of all components including `Discrim`s, whereas `properties` will return only the `Prop-`s.

To see how these data types can be used to integrate with a data backend, see the
[`pydoptic-elastic`](../pydoptic-elastic/) package in this repository, a reference Elasticsearch integration.
