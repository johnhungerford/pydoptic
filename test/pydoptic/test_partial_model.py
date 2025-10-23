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

def test_partial_model_constructed_from_full_model():
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
    ).as_partial()

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

def test_partial_model_should_allow_extra_args_and_filter_out():
    model_value = TestModel.partial(
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

def test_partial_model_should_accept_all_valid_values():
    model_value = TestModel.partial(
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

def test_complete_partial_model_should_become_full_model():
    model_value = TestModel.partial(
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
    ).as_model()

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

def test_partial_model_should_accept_valid_missing_arguments():
    model_value = TestModel.partial(
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
    with pytest.raises(AttributeError):
        model_value.select_opt_empty # type: ignore[attr-defined]
    assert model_value.select_opt_renamed == 1 # type: ignore[attr-defined]
    assert model_value.select_arr_empty == [1,2,3] # type: ignore[attr-defined]
    assert model_value.select_arr_renamed == [1,2,3] # type: ignore[attr-defined]
    assert model_value.select_opt_arr_empty == [1,2,3] # type: ignore[attr-defined]
    with pytest.raises(AttributeError):
        model_value.select_opt_arr_renamed # type: ignore[attr-defined]

def test_partial_model_should_accept_partial_model_for_nested_models_if_complete():
    model_value = TestModel.partial(
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

    assert isinstance(model_value.other, PartialModel) # type: ignore[attr-defined]
    assert model_value.other.model is Other # type: ignore[attr-defined]
    assert model_value.other.value == True # type: ignore[attr-defined]
    assert isinstance(model_value.other.another, PartialModel) # type: ignore[attr-defined]
    assert model_value.other.another.model is Another # type: ignore[attr-defined]
    assert model_value.other.another.value == 0.2 # type: ignore[attr-defined]

def test_partial_model_should_accept_dict_for_nested_models_if_complete():
    model_value = TestModel.partial(
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

    assert isinstance(model_value.other, PartialModel) # type: ignore[attr-defined]
    assert model_value.other.model is Other # type: ignore[attr-defined]
    assert model_value.other.value == True # type: ignore[attr-defined]
    assert isinstance(model_value.other.another, PartialModel) # type: ignore[attr-defined]
    assert model_value.other.another.model is Another # type: ignore[attr-defined]
    assert model_value.other.another.value == 0.2 # type: ignore[attr-defined]

def test_partial_model_init_should_succeed_if_required_param_is_missing():
    model_value = TestModel.partial(
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

    with pytest.raises(AttributeError):
        model_value.annotation # type: ignore[attr-defined]
    assert model_value.select_val_empty == 1 # type: ignore[attr-defined]
    assert model_value.select_val_renamed == 1 # type: ignore[attr-defined]
    assert model_value.select_opt_empty == 1 # type: ignore[attr-defined]
    assert model_value.select_opt_renamed == 1 # type: ignore[attr-defined]
    assert model_value.select_arr_empty == [1,2,3] # type: ignore[attr-defined]
    assert model_value.select_arr_renamed == [1,2,3] # type: ignore[attr-defined]
    assert model_value.select_opt_arr_empty == [1,2,3] # type: ignore[attr-defined]
    assert model_value.select_opt_arr_renamed == [1,2,3] # type: ignore[attr-defined]

def test_incomplete_partial_model_should_fail_to_become_full_model_if_missing_params_are_not_provided():
    passed = False
    try:
        TestModel.partial(
            annotation="str",
            select_val_renamed=1,
            select_opt_empty=1,
            select_opt_renamed=1,
            select_arr_renamed=[1,2,3],
            select_opt_arr_empty=[1,2,3],
            select_opt_arr_renamed=[1,2,3],
            other=Other(
                value=True,
                another=Another(
                    value=0.2
                )
            ),
        ).as_model()
    except ValueError as ve:
        assert 'select_val_empty' in str(ve)
        passed = True

    assert passed


def test_incomplete_partial_model_should_become_full_model_if_missing_params_are_provided():
    model_value = TestModel.partial(
        annotation="str",
        select_val_renamed=1,
        select_opt_empty=1,
        select_opt_renamed=1,
        select_arr_renamed=[1,2,3],
        select_opt_arr_empty=[1,2,3],
        select_opt_arr_renamed=[1,2,3],
        other=Other(
            value=True,
            another=Another(
                value=0.2
            )
        ),
    ).as_model(
        select_val_empty=1,
        select_arr_empty=[1,2,3]
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

def test_partial_model_init_should_fail_if_primitive_type_is_wrong():
    passed = True
    try:
        TestModel.partial(
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

def test_partial_model_init_should_fail_if_primitive_array_param_receives_non_array():
    passed = True
    try:
        TestModel.partial(
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

def test_partial_model_init_should_fail_if_primitive_array_param_contains_invalid_element():
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

def test_partial_model_init_should_fail_if_wrong_model_is_passed():
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

def test_partial_model_init_should_fail_if_nested_model_is_invalid_dict():
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

def test_partial_model_init_should_accept_incomplete_nested_partial_model():
    TestModel.partial(
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

class NestedModelExample(BaseModel):
    nested_model: SelectArr['NestedModelExample', Another] = select()

def test_partial_model_init_should_accept_valid_nested_model_array():
    nested_vals = [Another(value=2.0), {'value': 0.2}, Another.partial(value=23.042)]
    result = NestedModelExample.partial(
        nested_model=nested_vals,
    )
    assert [v.value for v in result.nested_model] == [2.0, 0.2, 23.042] # type: ignore[attr-defined]

def test_partial_model_init_should_fail_if_nested_model_array_is_not_array():
    passed = True
    try:
        NestedModelExample.partial(
            nested_model=Another(value=0.2),
        )
        passed = False
    except ValueError as e:
        assert 'array' in str(e)

    assert passed

def test_patial_model_init_should_fail_if_nested_model_array_contains_invald_model():
    passed = True
    try:
        NestedModelExample.partial(
            nested_model=[Another(value=2.0), {'value': 'str'}, Another(value=23.042)],
        )
        passed = False
    except ValueError as e:
        assert '1' in str(e)
        assert 'nested_model' in str(e)
        assert 'value' in str(e)
        assert 'str' in str(e)

    assert passed

def test_partial_model_as_mapping_full_should_be_reversable():
    model_value = TestModel.partial(
        annotation="str",
        select_val_empty=1,
        select_opt_renamed=1,
        select_arr_renamed=[1,2,3],
        select_opt_arr_empty=[1,2,3],
        other=Other.partial(
            value=True,
            another=Another.partial(
            )
        ),
    )

    dict_value = model_value.as_mapping_full()

    model_value_2 = TestModel.partial(**dict_value)

    assert model_value == model_value_2

def test_base_model_select_parts_should_generate_partial_model_from_selectors():
    model_value = TestModel.partial(
        annotation="str",
        select_val_renamed=1,
        select_opt_empty=1,
        select_opt_renamed=1,
        select_arr_empty=[1,2,3],
        select_opt_arr_empty=[1,2,3],
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
