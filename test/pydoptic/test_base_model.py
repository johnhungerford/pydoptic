import pytest

from pydoptic.base_model import *
from pydoptic.selector import *

class TestModel(BaseModel):
    annotation: Prop['TestModel', str]
    select_val_empty: Prop['TestModel', int] = select()
    select_val_name: Prop['TestModel', int] = select('select_val_renamed')
    select_opt_empty: PropOpt['TestModel', int] = select()
    select_opt_name: PropOpt['TestModel', int] = select('select_opt_renamed')
    select_arr_empty: PropArr['TestModel', int] = select()
    select_arr_name: PropArr['TestModel', int] = select('select_arr_renamed')
    select_opt_arr_empty: PropOptArr['TestModel', int] = select()
    select_opt_arr_name: PropOptArr['TestModel', int] = select('select_opt_arr_renamed')
    other: Prop['TestModel', 'Other']

TestModel.__test__ = False # type: ignore[attr-defined]

class Other(BaseModel):
    value: Prop['Other', bool]
    another: Prop['Other', 'Another']

class Another(BaseModel):
    value: Prop['Another', float]

def test_base_model_should_construct_selectors():
    assert set(TestModel.properties().keys()) == {
        'annotation',
        'select_val_empty',
        'select_val_renamed',
        'select_opt_empty',
        'select_opt_renamed',
        'select_arr_empty',
        'select_arr_renamed',
        'select_opt_arr_empty',
        'select_opt_arr_renamed',
        'other',
    }

    for select in TestModel.properties().values():
        assert isinstance(select, PropSelect)

    assert TestModel.properties()['annotation'] == TestModel.annotation
    assert TestModel.properties()['select_val_empty'] == TestModel.select_val_empty
    assert TestModel.properties()['select_val_renamed'] == TestModel.select_val_name
    assert TestModel.properties()['select_opt_empty'] == TestModel.select_opt_empty
    assert TestModel.properties()['select_opt_renamed'] == TestModel.select_opt_name
    assert TestModel.properties()['select_arr_empty'] == TestModel.select_arr_empty
    assert TestModel.properties()['select_arr_renamed'] == TestModel.select_arr_name
    assert TestModel.properties()['select_opt_arr_empty'] == TestModel.select_opt_arr_empty
    assert TestModel.properties()['select_opt_arr_renamed'] == TestModel.select_opt_arr_name
    assert TestModel.properties()['other'] == TestModel.other

def test_base_model_should_construct_selector_from_annotation_only():
    assert TestModel.annotation == PropSelect.val('annotation', TestModel, str, {})

def test_base_model_should_construct_selector_from_select():
    assert TestModel.select_val_empty == PropSelect.val('select_val_empty', TestModel, int, {})
    assert TestModel.select_val_name == PropSelect.val('select_val_renamed', TestModel, int, {})

def test_base_model_should_construct_selector_from_select_opt():
    assert TestModel.select_opt_empty == PropSelect.opt('select_opt_empty', TestModel, int, {})
    assert TestModel.select_opt_name == PropSelect.opt('select_opt_renamed', TestModel, int, {})

def test_base_model_should_construct_selector_from_select_arr():
    assert TestModel.select_arr_empty == PropSelect.arr('select_arr_empty', TestModel, int, {})
    assert TestModel.select_arr_name == PropSelect.arr('select_arr_renamed', TestModel, int, {})

def test_base_model_should_construct_selector_from_select_opt_arr():
    assert TestModel.select_opt_arr_empty == PropSelect.opt_arr('select_opt_arr_empty', TestModel, int, {})
    assert TestModel.select_opt_arr_name == PropSelect.opt_arr('select_opt_arr_renamed', TestModel, int, {})

def test_base_model_should_accept_valid_argument_types():
    model_value = TestModel(
        annotation="str",
        select_val_empty=1,
        select_val_renamed=1,
        select_opt_empty=1,
        select_opt_renamed=1,
        select_arr_empty=[1,2,3],
        select_arr_renamed=[1,2,3],
        select_opt_arr_empty=[1,2,3],
        select_opt_arr_renamed=[1,2,3],
        other=Other(
            value=True,
            another=Another(
                value=0.2
            )
        ),
    )

    assert model_value.annotation == "str" # type: ignore[attr-defined]
    assert model_value.select_val_empty == 1 # type: ignore[attr-defined]
    assert model_value.select_val_renamed == 1 # type: ignore[attr-defined]
    assert model_value.select_opt_empty == 1 # type: ignore[attr-defined]
    assert model_value.select_opt_renamed == 1 # type: ignore[attr-defined]
    assert model_value.select_arr_empty == [1,2,3] # type: ignore[attr-defined]
    assert model_value.select_arr_renamed == [1,2,3] # type: ignore[attr-defined]
    assert model_value.select_opt_arr_empty == [1,2,3] # type: ignore[attr-defined]
    assert model_value.select_opt_arr_renamed == [1,2,3] # type: ignore[attr-defined]
    assert model_value.other.value == True # type: ignore[attr-defined]
    assert model_value.other.another.value == 0.2 # type: ignore[attr-defined]


def test_base_model_should_accept_valid_missing_arguments():
    model_value = TestModel(
        annotation="str",
        select_val_empty=1,
        select_val_renamed=1,
        select_opt_renamed=1,
        select_arr_empty=[1,2,3],
        select_arr_renamed=[1,2,3],
        select_opt_arr_empty=[1,2,3],
        other=Other(
            value=True,
            another=Another(
                value=0.2
            )
        ),
    )

    assert model_value.annotation == "str" # type: ignore[attr-defined]
    assert model_value.select_val_empty == 1 # type: ignore[attr-defined]
    assert model_value.select_val_renamed == 1 # type: ignore[attr-defined]
    assert model_value.select_opt_empty is None # type: ignore[attr-defined]
    assert model_value.select_opt_renamed == 1 # type: ignore[attr-defined]
    assert model_value.select_arr_empty == [1,2,3] # type: ignore[attr-defined]
    assert model_value.select_arr_renamed == [1,2,3] # type: ignore[attr-defined]
    assert model_value.select_opt_arr_empty == [1,2,3] # type: ignore[attr-defined]
    assert model_value.select_opt_arr_renamed is None # type: ignore[attr-defined]

def test_base_model_should_accept_partial_model_for_nested_models_if_complete():
    model_value = TestModel(
        annotation="str",
        select_val_empty=1,
        select_val_renamed=1,
        select_arr_empty=[1,2,3],
        select_arr_renamed=[1,2,3],
        other=Other.partial(
            value=True,
            another=Another.partial(
                value=0.2
            )
        ),
    )

    assert isinstance(model_value.other, Other) # type: ignore[attr-defined]
    assert model_value.other.value == True # type: ignore[attr-defined]
    assert isinstance(model_value.other.another, Another) # type: ignore[attr-defined]
    assert model_value.other.another.value == 0.2 # type: ignore[attr-defined]

def test_base_model_should_accept_dict_for_nested_models_if_complete():
    model_value = TestModel(
        annotation="str",
        select_val_empty=1,
        select_val_renamed=1,
        select_arr_empty=[1,2,3],
        select_arr_renamed=[1,2,3],
        other={
            'value': True,
            'another': {
                'value': 0.2
            },
        },
    )

    assert isinstance(model_value.other, Other) # type: ignore[attr-defined]
    assert model_value.other.value == True # type: ignore[attr-defined]
    assert isinstance(model_value.other.another, Another) # type: ignore[attr-defined]
    assert model_value.other.another.value == 0.2 # type: ignore[attr-defined]

def test_base_model_init_should_fail_if_required_param_is_missing():
    passed = True
    try:
        TestModel(
            select_val_empty=1,
            select_val_renamed=1,
            select_opt_empty=1,
            select_opt_renamed=1,
            select_arr_empty=[1,2,3],
            select_arr_renamed=[1,2,3],
            select_opt_arr_empty=[1,2,3],
            select_opt_arr_renamed=[1,2,3],
            other=Other(
                value=True,
                another=Another(
                    value=0.2
                )
            ),
        )
    except ValueError as e:
        assert 'Missing required' in str(e)
        passed = False

    assert passed is False

def test_partial_model_should_not_allow_extra_args():
    passed = False
    try:
        TestModel(
            annotation="str",
            select_val_empty=1,
            select_val_renamed=1,
            select_opt_empty=1,
            select_opt_renamed=1,
            select_arr_empty=[1,2,3],
            extra_arg_1="hi",
            select_arr_renamed=[1,2,3],
            select_opt_arr_empty=[1,2,3],
            select_opt_arr_renamed=[1,2,3],
            other=Other(
                value=True,
                another=Another(
                    value=0.2
                )
            ),
            extra_arg_2=True,
        )
    except ValueError as ve:
        assert 'extra_arg' in str(ve)
        passed = True

    assert passed

def test_partial_model_should_allow_extra_args_and_filter_out_when_configured_to_do_so():
    model_value = TestModel(
        _allow_extra_args=True,
        annotation="str",
        select_val_empty=1,
        select_val_renamed=1,
        select_opt_empty=1,
        select_opt_renamed=1,
        select_arr_empty=[1,2,3],
        extra_arg_1="hi",
        select_arr_renamed=[1,2,3],
        select_opt_arr_empty=[1,2,3],
        select_opt_arr_renamed=[1,2,3],
        other=Other(
            value=True,
            another=Another(
                value=0.2
            )
        ),
        extra_arg_2=True,
    )

    assert model_value.annotation == "str" # type: ignore[attr-defined]
    assert model_value.select_val_empty == 1 # type: ignore[attr-defined]
    assert model_value.select_val_renamed == 1 # type: ignore[attr-defined]
    assert model_value.select_opt_empty == 1 # type: ignore[attr-defined]
    assert model_value.select_opt_renamed == 1 # type: ignore[attr-defined]
    assert model_value.select_arr_empty == [1,2,3] # type: ignore[attr-defined]
    assert model_value.select_arr_renamed == [1,2,3] # type: ignore[attr-defined]
    assert model_value.select_opt_arr_empty == [1,2,3] # type: ignore[attr-defined]
    assert model_value.select_opt_arr_renamed == [1,2,3] # type: ignore[attr-defined]
    assert model_value.other.value == True # type: ignore[attr-defined]
    assert model_value.other.another.value == 0.2 # type: ignore[attr-defined]

    assert not hasattr(model_value, 'extra_arg_1')
    assert not hasattr(model_value, 'extra_arg_2')

def test_base_model_init_should_fail_if_primitive_type_is_wrong():
    passed = True
    try:
        TestModel(
            annotation=5,
            select_val_empty=1,
            select_val_renamed=1,
            select_opt_empty=1,
            select_opt_renamed=1,
            select_arr_empty=[1,2,3],
            select_arr_renamed=[1,2,3],
            select_opt_arr_empty=[1,2,3],
            select_opt_arr_renamed=[1,2,3],
            other=Other(
                value=True,
                another=Another(
                    value=0.2
                )
            ),
        )
    except ValueError as e:
        assert 'str' in str(e)
        passed = False

    assert passed is False

def test_base_model_init_should_fail_if_primitive_array_param_receives_non_array():
    passed = True
    try:
        TestModel(
            annotation="str",
            select_val_empty=1,
            select_val_renamed=1,
            select_opt_empty=1,
            select_opt_renamed=1,
            select_arr_empty=1,
            select_arr_renamed=[1,2,3],
            select_opt_arr_empty=[1,2,3],
            select_opt_arr_renamed=[1,2,3],
            other=Other(
                value=True,
                another=Another(
                    value=0.2
                )
            ),
        )
    except ValueError as e:
        assert 'array' in str(e)
        passed = False

    assert passed is False

def test_base_model_init_should_fail_if_primitive_array_param_contains_invalid_element():
    passed = True
    try:
        TestModel(
            annotation="str",
            select_val_empty=1,
            select_val_renamed=1,
            select_opt_empty=1,
            select_opt_renamed=1,
            select_arr_empty=[1, "two", 3],
            select_arr_renamed=[1,2,3],
            select_opt_arr_empty=[1,2,3],
            select_opt_arr_renamed=[1,2,3],
            other=Other(
                value=True,
                another=Another(
                    value=0.2
                )
            ),
        )
    except ValueError as e:
        assert 'array' in str(e)
        assert '2' in str(e) # should mention position
        passed = False

    assert passed is False

def test_base_model_init_should_fail_if_wrong_model_is_passed():
    passed = True
    try:
        TestModel(
            annotation="str",
            select_val_empty=1,
            select_val_renamed=1,
            select_opt_empty=1,
            select_opt_renamed=1,
            select_arr_empty=[1,2,3],
            select_arr_renamed=[1,2,3],
            select_opt_arr_empty=[1,2,3],
            select_opt_arr_renamed=[1,2,3],
            other=Another(
                value=0.2
            ),
        )
    except ValueError as e:
        assert 'expected type Other' in str(e)
        passed = False

    assert passed is False

def test_base_model_init_should_fail_if_nested_model_is_invalid_dict():
    passed = True
    try:
        TestModel(
            annotation="str",
            select_val_empty=1,
            select_val_renamed=1,
            select_opt_empty=1,
            select_opt_renamed=1,
            select_arr_empty=[1,2,3],
            select_arr_renamed=[1,2,3],
            select_opt_arr_empty=[1,2,3],
            select_opt_arr_renamed=[1,2,3],
            other=Other(
                value=True,
                another={
                    'value': 'str', # Invalid
                }
            ),
        )
    except ValueError as e:
        assert 'other' in str(e)
        assert 'str' in str(e)
        passed = False

    assert passed is False

def test_base_model_init_should_fail_if_nested_model_is_incomplete_partial_model():
    passed = True
    try:
        TestModel(
            annotation="str",
            select_val_empty=1,
            select_val_renamed=1,
            select_opt_empty=1,
            select_opt_renamed=1,
            select_arr_empty=[1,2,3],
            select_arr_renamed=[1,2,3],
            select_opt_arr_empty=[1,2,3],
            select_opt_arr_renamed=[1,2,3],
            other=Other.partial(
                value=True,
                another=Another.partial(
                )
            ),
        )
    except ValueError as e:
        assert 'other' in str(e)
        assert 'another' in str(e)
        assert 'value' in str(e)
        passed = False

    assert passed is False


class NestedModelExample(BaseModel):
    nested_model: PropArr['NestedModelExample', Another] = select()

def test_base_model_init_should_accept_valid_nested_model_array():
    nested_vals = [Another(value=2.0), {'value': 0.2}, Another.partial(value=23.042)]
    NestedModelExample.nested_model
    somat = get_type_hints(NestedModelExample)
    result = NestedModelExample(
        nested_model=nested_vals,
    )
    assert [v.value for v in result.nested_model] == [2.0, 0.2, 23.042] # type: ignore[attr-defined]

def test_base_model_init_should_fail_if_nested_model_array_is_not_array():
    passed = True
    try:
        NestedModelExample(
            nested_model=Another(value=0.2),
        )
        passed = False
    except ValueError as e:
        assert 'array' in str(e)

    assert passed

def test_base_model_init_should_fail_if_nested_model_array_contains_invald_model():
    passed = True
    try:
        NestedModelExample(
            nested_model=[Another(value=2.0), {'value': 'str'}, Another(value=23.042)],
        )
        passed = False
    except ValueError as e:
        assert '1' in str(e)
        assert 'nested_model' in str(e)
        assert 'value' in str(e)
        assert 'str' in str(e)

    assert passed

def test_base_model_as_mapping_full_should_be_reversable():
    model_value = TestModel(
        annotation="str",
        select_val_empty=1,
        select_val_renamed=1,
        select_opt_renamed=1,
        select_arr_empty=[1,2,3],
        select_arr_renamed=[1,2,3],
        select_opt_arr_empty=[1,2,3],
        other=Other(
            value=True,
            another=Another(
                value=0.2
            )
        ),
    )

    dict_value = model_value.as_mapping_full()

    model_value_2 = TestModel(**dict_value)

    assert model_value == model_value_2

class ModelWithData(BaseModel):
    property: PropOpt['ModelWithData', int] = select(data_1='hello', data_2=2, data_3=False)

def test_select_proxy_should_propagate_data_to_base_model_selectors():
    if isinstance(ModelWithData.property, PropOpt) and ModelWithData.property.target is int:
        assert len(ModelWithData.property.data) == 3
        assert ModelWithData.property.data['data_1'] == 'hello'
        assert ModelWithData.property.data['data_2'] == 2
        assert ModelWithData.property.data['data_3'] == False
    else:
        pytest.fail(f'Did not match expected selector: {ModelWithData.property}')

def test_base_model_select_parts_should_generate_partial_model_from_selectors():
    model_value = TestModel(
        annotation="str",
        select_val_empty=1,
        select_val_renamed=1,
        select_opt_empty=1,
        select_opt_renamed=1,
        select_arr_empty=[1,2,3],
        select_arr_renamed=[1,2,3],
        select_opt_arr_empty=[1,2,3],
        select_opt_arr_renamed=[1,2,3],
        other=Other(
            value=True,
            another=Another(
                value=0.2
            )
        ),
    )

    partial_model = model_value.select_partial(
        TestModel.select_arr_empty,
        TestModel.other(Other.value),
        TestModel.other(Other.another)(Another.value),
    )

    assert partial_model.as_mapping_full() == {
        'select_arr_empty': [1,2,3],
        'other': {
            'value': True,
            'another': {
                'value': 0.2,
            }
        }
    }

class Parent(BaseModel):
    prop_1: Prop['Parent', int]

class Child(Parent):
    prop_2: Prop['Child', int]

def test_base_model_properties_should_be_inherited_from_parent():
    # Parent shouldn't need child props
    Parent(prop_1=1)

    # Child should need parent props
    passed = False
    try:
        Child(prop_2=23)
    except ValueError as ve:
        assert 'prop_1' in str(ve)
        passed = True

    assert passed
    valid_model = Child(prop_1=1, prop_2=2)

    assert Child.prop_1.get_val(valid_model) == 1
    # Parent selector should work on child
    assert Parent.prop_1.get_val(valid_model) == 1
    assert Child.prop_2.get_val(valid_model) == 2


class Base(BaseModel):
    v: Prop['Base', str]

class Sub1(Base):
    d: Discrim[Base, 'Sub1']
    s1v: Prop['Sub1', int]

class Sub2(Base):
    d: Discrim[Base, 'Sub2']
    s2v: Prop['Sub2', bool]

class Root(BaseModel):
    next: Prop['Root', Base]

def test_base_model_should_construct_with_discrim():
    value_1 = Root(next=Sub1(v='1', s1v=23))
    value_2 = Root(next=Sub2(v='2', s2v=True))

    assert value_1.next.d == 'Sub1' # type: ignore
    assert value_2.next.d == 'Sub2' # type: ignore

def test_base_model_should_forbid_constructing_with_invalid_discrim():
    value = Root(next=Sub1(d='Sub1', v='1', s1v=23))
    assert value.next.d == 'Sub1' # type: ignore

    with pytest.raises(ValueError):
        Root(next=Sub2(d='wrong!', v='2', s2v=True))

def test_base_model_should_forbid_setting_invalid_discrim():
    value = Root(next=Sub1(d='Sub1', v='1', s1v=23))
    assert value.next.d == 'Sub1' # type: ignore

    with pytest.raises(AttributeError):
        value.next.d = 'wrong!'  # type: ignore[attr-defined]

class BiModel(BaseModel):
    prop_1_sel: Prop['BiModel', int] = select('prop_1')
    prop_1: int
    prop_2_sel: Prop['BiModel', str] = select('prop_2')
    prop_2: str

def test_base_model_should_allow_type_checked_attributes_using_aliases():    
    value = BiModel(prop_1=23, prop_2="hi")
    assert value.prop_1 == BiModel.prop_1_sel.get_val(value) == 23
    assert value.prop_2 == BiModel.prop_2_sel.get_val(value) == "hi"
