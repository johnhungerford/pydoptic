import pytest
from pydoptic.base_model import BaseModel

from pydoptic.selector import PropArr, PropOpt, PropOptArr, Prop

class Model(BaseModel):
    nested: PropOpt['Model', 'Nested']

class Nested(BaseModel):
    nested: PropOpt['Nested', 'NestedNested']

class NestedNested(BaseModel):
    value: PropOpt['NestedNested', int]

def test_selector_should_get_value():
    selector = Model.nested(Nested.nested)(NestedNested.value)

    model_1 = Model(nested=Nested(nested=NestedNested(value=23)))
    assert selector.get(model_1).value == 23

    model_2 = Model(nested=Nested(nested=NestedNested()))
    assert selector.get(model_2).value == None

    model_3 = Model()
    assert selector.get(model_3).value == None

def test_selector_should_set_value():
    selector = Model.nested(Nested.nested)(NestedNested.value)

    model_1 = Model(nested=Nested(nested=NestedNested(value=23)))
    assert selector.get(model_1).value == 23
    selector.set(model_1, 1)
    assert selector.get(model_1).value == 1

    model_2 = Model(nested=Nested(nested=NestedNested()))
    assert selector.get(model_2).value == None
    selector.set(model_2, 1)
    assert selector.get(model_2).value == 1

    model_3 = Model(nested=Nested())
    assert selector.get(model_3).value == None
    selector.set(model_3, 1)
    assert selector.get(model_3).value == None

def test_selector_should_update_value():
    selector = Model.nested(Nested.nested)(NestedNested.value)

    model_1 = Model(nested=Nested(nested=NestedNested(value=23)))
    assert selector.get(model_1).value == 23
    selector.update(model_1, lambda i: i + 1)
    assert selector.get(model_1).value == 24

    model_2 = Model(nested=Nested(nested=NestedNested()))
    assert selector.get(model_2).value == None
    selector.update(model_2, lambda i: i + 1)
    assert selector.get(model_2).value == None

    model_3 = Model(nested=Nested())
    assert selector.get(model_3).value == None
    selector.update(model_3, lambda i: i + 1)
    assert selector.get(model_3).value == None

def test_selector_should_clear_value_as_far_up_the_chain_as_possible():
    selector = Model.nested(Nested.nested)(NestedNested.value)

    model_1 = Model(nested=Nested(nested=NestedNested(value=23)))
    assert selector.get(model_1).value == 23
    selector.clear(model_1)
    assert selector.get(model_1).value is None
    assert model_1.nested.nested is not None # type: ignore

def test_selector_should_set_safe_and_unsafe_from_partial_model():
    sel = M1.a(M2.b)(M3.c)(M4.d)

    value_1 = M1.partial(a=M2.partial(b=M3.partial(c=M4.partial(d=23))))
    assert sel.get_safe(value_1).value == 23
    sel.set_unsafe(value_1, 1)
    assert sel.get_safe(value_1).value == 1
    sel.set_safe(value_1, 2)
    assert sel.get_safe(value_1).value == 2

    value_2 = M1.partial(a=M2.partial(b=M3.partial()))
    assert sel.get_safe(value_2).value is None
    with pytest.raises(ValueError):
        sel.set_unsafe(value_2, 1)
    assert sel.get_safe(value_2).value is None
    sel.set_safe(value_2, 2)
    assert sel.get_safe(value_2).value is None

def test_selector_should_set_safe_and_unsafe_from_dict():
    sel = M1.a(M2.b)(M3.c)(M4.d)

    value_1 = M1.partial(a=M2.partial(b=M3.partial(c=M4.partial(d=23))))
    assert sel.get_safe(value_1).value == 23
    sel.set_unsafe(value_1, 1)
    assert sel.get_safe(value_1).value == 1
    sel.set_safe(value_1, 2)
    assert sel.get_safe(value_1).value == 2

    value_2 = M1.partial(a=M2.partial(b=M3.partial()))
    assert sel.get_safe(value_2).value is None
    with pytest.raises(ValueError):
        sel.set_unsafe(value_2, 1)
    assert sel.get_safe(value_2).value is None
    sel.set_safe(value_2, 2)
    assert sel.get_safe(value_2).value is None

def test_selector_should_update_safe_and_unsafe_from_partial_model():
    sel = M1.a(M2.b)(M3.c)(M4.d)

    value_1 = {'a': {'b': {'c': {'d': 23}}}}
    assert sel.get_safe(value_1).value == 23
    sel.update_unsafe(value_1, lambda i: i + 1)
    assert sel.get_safe(value_1).value == 24
    sel.update_safe(value_1, lambda i: i + 1)
    assert sel.get_safe(value_1).value == 25

    value_2: dict = {'a': {'b': {}}}
    assert sel.get_safe(value_2).value is None
    with pytest.raises(ValueError):
        sel.update_unsafe(value_2, lambda i: i + 1)
    assert sel.get_safe(value_2).value is None
    sel.update_safe(value_1, lambda i: i + 1)
    assert sel.get_safe(value_2).value is None

def test_selector_should_update_safe_and_unsafe_from_dict():
    sel = M1.a(M2.b)(M3.c)(M4.d)

    value_1 = {'a': {'b': {'c': {'d': 23}}}}
    assert sel.get_safe(value_1).value == 23
    sel.update_unsafe(value_1, lambda i: i + 1)
    assert sel.get_safe(value_1).value == 24
    sel.update_safe(value_1, lambda i: i + 1)
    assert sel.get_safe(value_1).value == 25

    value_2: dict = {'a': {'b': {}}}
    assert sel.get_safe(value_2).value is None
    with pytest.raises(ValueError):
        sel.update_unsafe(value_2, lambda i: i + 1)
    assert sel.get_safe(value_2).value is None
    sel.update_safe(value_1, lambda i: i + 1)
    assert sel.get_safe(value_2).value is None

class Z(BaseModel):
    d: Prop['Z', int]

class Y(BaseModel):
    c: PropOpt['Y', Z]

class X(BaseModel):
    b: Prop['X', Y]

class W(BaseModel):
    a: Prop['W', X]

def test_selector_should_clear_safe_on_a_partial_model():
    sel_valid = W.a(X.b)(Y.c)(Z.d)
    sel_invalid = W.a(X.b)

    value_1 = W.partial(a=X.partial(b=Y.partial(c=Z.partial(d=23))))
    assert sel_valid.get_safe(value_1).value == 23
    sel_valid.clear_safe(value_1)
    assert value_1.a.b.c.d is None

    value_2 = W.partial(a=X.partial(b=Y.partial(c=Z.partial(d=23))))
    assert sel_valid.get_safe(value_2).value == 23
    sel_valid.clear_safe_strict(value_2)
    assert value_2.a.b.c is None

    value_3 = W.partial(a=X.partial(b=Y.partial(c=Z.partial(d=23))))
    assert sel_invalid.get_safe(value_3).value is not None
    sel_invalid.clear_safe(value_3)
    assert value_3.a.b is None

    value_4 = W.partial(a=X.partial(b=Y.partial(c=Z.partial(d=23))))
    assert sel_invalid.get_safe(value_4).value is not None
    sel_invalid.clear_safe_strict(value_4) # shouldn't throw
    assert value_4.a.b is not None

def test_selector_should_clear_safe_on_a_dict():
    sel_valid = W.a(X.b)(Y.c)(Z.d)
    sel_invalid = W.a(X.b)

    value_1 = {'a': {'b': {'c': {'d': 23}}}}
    assert sel_valid.get_safe(value_1).value == 23
    sel_valid.clear_safe(value_1)
    assert value_1['a']['b']['c'].get('d') is None

    value_2 = {'a': {'b': {'c': {'d': 23}}}}
    assert sel_valid.get_safe(value_2).value == 23
    sel_valid.clear_safe_strict(value_2)
    assert value_2['a']['b'].get('c') is None

    value_3 = {'a': {'b': {'c': {'d': 23}}}}
    assert sel_invalid.get_safe(value_3).value is not None
    sel_invalid.clear_safe(value_3)
    assert value_3['a'].get('b') is None

    value_4 = {'a': {'b': {'c': {'d': 23}}}}
    assert sel_invalid.get_safe(value_4).value is not None
    sel_invalid.clear_safe_strict(value_4) # shouldn't throw
    assert value_4['a']['b'] is not None

def test_selector_should_clear_unsafe_on_a_partial_model():
    sel_valid = W.a(X.b)(Y.c)(Z.d)
    sel_invalid = W.a(X.b)

    value_1 = W.partial(a=X.partial(b=Y.partial(c=Z.partial(d=23))))
    assert sel_valid.get_safe(value_1).value == 23
    sel_valid.clear_unsafe(value_1)
    assert value_1.a.b.c.d is None

    value_2 = W.partial(a=X.partial(b=Y.partial(c=Z.partial(d=23))))
    assert sel_valid.get_safe(value_2).value == 23
    sel_valid.clear_unsafe_strict(value_2)
    assert value_2.a.b.c is None

    value_3 = W.partial(a=X.partial(b=Y.partial(c=Z.partial(d=23))))
    assert sel_invalid.get_safe(value_3).value is not None
    sel_invalid.clear_unsafe(value_3)
    assert value_3.a.b is None

    value_4 = W.partial(a=X.partial(b=Y.partial(c=Z.partial(d=23))))
    assert sel_invalid.get_safe(value_4).value is not None
    with pytest.raises(ValueError):
        sel_invalid.clear_unsafe_strict(value_4)
    assert value_4.a.b is not None

def test_selector_should_clear_unsafe_on_a_dict():
    sel_valid = W.a(X.b)(Y.c)(Z.d)
    sel_invalid = W.a(X.b)

    value_1 = {'a': {'b': {'c': {'d': 23}}}}
    assert sel_valid.get_safe(value_1).value == 23
    sel_valid.clear_unsafe(value_1)
    assert value_1['a']['b']['c'].get('d') is None

    value_2 = {'a': {'b': {'c': {'d': 23}}}}
    assert sel_valid.get_safe(value_2).value == 23
    sel_valid.clear_unsafe_strict(value_2)
    assert value_2['a']['b'].get('c') is None

    value_3 = {'a': {'b': {'c': {'d': 23}}}}
    assert sel_invalid.get_safe(value_3).value is not None
    sel_invalid.clear_unsafe(value_3)
    assert value_3['a'].get('b') is None

    value_4 = {'a': {'b': {'c': {'d': 23}}}}
    assert sel_invalid.get_safe(value_4).value is not None
    with pytest.raises(ValueError):
        sel_invalid.clear_unsafe_strict(value_4)
    assert value_4['a']['b'] is not None

class ValModel(BaseModel):
    nested: Prop['ValModel', 'ValNested']

class ValNested(BaseModel):
    nested: Prop['ValNested', 'ValNestedNested']

class ValNestedNested(BaseModel):
    value: Prop['ValNestedNested', int]

def test_val_selector_should_get_value():
    selector = ValModel.nested.then_val(ValNested.nested).then_val(ValNestedNested.value)

    model = ValModel(nested=ValNested(nested=ValNestedNested(value=23)))
    res = selector.get_val(model)
    assert res == 23

def test_opt_selector_should_get_value():
    selector = Model.nested.then_opt(Nested.nested).then_opt(NestedNested.value)

    model_1 = Model(nested=Nested(nested=NestedNested(value=23)))
    res = selector.get_val(model_1)
    assert res == 23

    model_2 = Model(nested=Nested(nested=NestedNested()))
    res = selector.get_val(model_2)
    assert res is None

    model_3 = Model()
    res = selector.get_val(model_3)
    assert res is None

class ArrModel(BaseModel):
    nested: PropArr['ArrModel', 'ArrNested']

class ArrNested(BaseModel):
    nested: Prop['ArrNested', 'ArrNestedNested']

class ArrNestedNested(BaseModel):
    value: PropArr['ArrNestedNested', int]

def test_arr_selector_should_get_value():
    selector = ArrModel.nested.then_val(ArrNested.nested).then_arr(ArrNestedNested.value)

    model_1 = ArrModel(nested=[ArrNested(nested=ArrNestedNested(value=[1, 2, 3]))])
    res = selector.get_val(model_1)
    assert res == [1, 2, 3]

    model_2 = ArrModel(nested=[ArrNested(nested=ArrNestedNested(value=[1, 2, 3])), ArrNested(nested=ArrNestedNested(value=[4, 5, 6]))])
    res = selector.get_val(model_2)
    assert res == [1, 2, 3, 4, 5, 6]

    model_3 = ArrModel(nested=[])
    res = selector.get_val(model_3)
    assert res == []

def test_arr_selector_should_set_all_values():
    selector = ArrModel.nested.then_val(ArrNested.nested).then_arr(ArrNestedNested.value)

    model_1 = ArrModel(nested=[ArrNested(nested=ArrNestedNested(value=[1, 2, 3]))])
    selector.set(model_1, 4)
    res = selector.get_val(model_1)
    assert res == [4, 4, 4]

    model_2 = ArrModel(nested=[ArrNested(nested=ArrNestedNested(value=[1, 2, 3])), ArrNested(nested=ArrNestedNested(value=[4, 5, 6]))])
    selector.set(model_2, 4)
    res = selector.get_val(model_2)
    assert res == [4, 4, 4, 4, 4, 4]
    assert model_2.nested[0].nested.value == [4, 4, 4] # type: ignore
    assert model_2.nested[1].nested.value == [4, 4, 4] # type: ignore

def test_arr_selector_should_clear_value_as_far_up_the_chain_as_possible():
    selector = ArrModel.nested.then_val(ArrNested.nested).then_arr(ArrNestedNested.value)

    model_1 = ArrModel(nested=[ArrNested(nested=ArrNestedNested(value=[1, 2, 3]))])
    selector.clear(model_1)
    assert selector.get_val(model_1) == []
    assert len(ArrModel.nested.value.get_val(model_1)) == 1
    assert ArrModel.nested.value.get_val(model_1)[0].nested.value == [] # type: ignore

class OptArrModel(BaseModel):
    nested: PropOptArr['OptArrModel', 'OptArrNested']

class OptArrNested(BaseModel):
    nested: Prop['OptArrNested', 'OptArrNested2']

class OptArrNested2(BaseModel):
    nested: PropOpt['OptArrNested2', 'OptArrNested3']

class OptArrNested3(BaseModel):
    value: PropOptArr['OptArrNested3', int]

def test_opt_arr_selector_should_get_value():
    selector_1 = OptArrModel.nested.then(OptArrNested.nested).then(OptArrNested2.nested).then(OptArrNested3.value)
    selector_2 = OptArrModel.nested.then(OptArrNested.nested).then(OptArrNested2.nested).then(OptArrNested3.value)

    model_1 = OptArrModel(nested=[OptArrNested(nested=OptArrNested2(nested=OptArrNested3(value=[1,2,3])))])
    res_1 = selector_1.get_val(model_1)
    res_2 = selector_2.get_val(model_1)
    assert res_1 == res_2 == [1, 2, 3]

    model_2 = OptArrModel(nested=[OptArrNested(nested=OptArrNested2(nested=OptArrNested3()))])
    res_1 = selector_1.get_val(model_2)
    res_2 = selector_2.get_val(model_2)
    assert res_1 == res_2 == []

    model_3 = OptArrModel(nested=[OptArrNested(nested=OptArrNested2())])
    res_1 = selector_1.get_val(model_3)
    res_2 = selector_2.get_val(model_3)
    assert res_1 == res_2 == []

    model_4 = OptArrModel()
    res_1 = selector_1.get_val(model_4)
    res_2 = selector_2.get_val(model_4)
    assert res_1 == res_2 == None

    model_5 = OptArrModel(
        nested=[
            OptArrNested(nested=OptArrNested2(nested=OptArrNested3(value=[1,2,3]))),
            OptArrNested(nested=OptArrNested2()),
            OptArrNested(nested=OptArrNested2(nested=OptArrNested3())),
            OptArrNested(nested=OptArrNested2(nested=OptArrNested3(value=[4,5,6]))),
            OptArrNested(nested=OptArrNested2(nested=OptArrNested3(value=[]))),
        ],
    )
    res_1 = selector_1.get_val(model_5)
    res_2 = selector_2.get_val(model_5)
    assert res_1 == res_2 == [1, 2, 3, 4, 5, 6]

class RA(BaseModel):
    next: Prop['RA', 'RB']

class RB(BaseModel):
    next: PropOpt['RB', 'RA']
    value: PropOpt['RB', int]

def test_selector_for_recursive_data_model_should_be_possible():
    selector = RA.next.then_opt(RB.next).then_val(RA.next).then_opt(RB.next).then_val(RA.next).then_opt(RB.next).then_val(RA.next).then_opt(RB.value)

    model = RA(next=RB(next=RA(next=RB(next=RA(next=RB(next=RA(next=RB(value=23))))))))

    value = selector.get_val(model)

    assert value == 23

class M4(BaseModel):
    d: Prop['M4', int]

class M3(BaseModel):
    c: Prop['M3', M4]

class M2(BaseModel):
    b: Prop['M2', M3]

class M1(BaseModel):
    a: Prop['M1', M2]

def test_val_selector_should_get_val_from_model():
    sel = M1.a.then_val(M2.b).then_val(M3.c).then_val(M4.d)
    res = sel.get_val(M1(a=M2(b=M3(c=M4(d=23)))))
    assert res == 23

def test_val_selector_should_get_val_safe_and_unsafe_from_partial_model():
    sel = M1.a.then_val(M2.b).then_val(M3.c).then_val(M4.d)

    value_1 = M1.partial(a=M2(b=M3.partial(c=M4(d=23))))
    res_1a = sel.get_val_unsafe(value_1)
    assert res_1a == 23
    res_1b = sel.get_val_safe(value_1)
    assert res_1b == 23

    value_2 = M1.partial(a=M2.partial(b=M3.partial()))
    with pytest.raises(ValueError):
        sel.get_val_unsafe(value_2)
    res_2 = sel.get_val_safe(value_2)
    assert res_2 is None

def test_val_selector_should_get_val_safe_and_unsafe_from_dict():
    sel = M1.a.then_val(M2.b).then_val(M3.c).then_val(M4.d)

    value_1 = {'a': {'b': {'c': {'d': 23}}}}
    res_1a = sel.get_val_unsafe(value_1)
    assert res_1a == 23
    res_1b = sel.get_val_safe(value_1)
    assert res_1b == 23

    value_2: dict = {'a': {'b': {}}}
    with pytest.raises(ValueError):
        sel.get_val_unsafe(value_2)
    res_2 = sel.get_val_safe(value_2)
    assert res_2 is None

class O4(BaseModel):
    d: Prop['O4', int]

class O3(BaseModel):
    c: PropOpt['O3', O4]

class O2(BaseModel):
    b: Prop['O2', O3]

class O1(BaseModel):
    a: PropOpt['O1', O2]

def test_opt_selector_should_get_val_from_model():
    sel = O1.a.then_val(O2.b).then_opt(O3.c).then_val(O4.d)

    # Model with all params
    value_1 = O1(a=O2(b=O3(c=O4(d=23))))
    res_1 = sel.get_val(value_1)
    assert res_1 == 23

    # Model with empty optional param
    value_2 = O1(a=O2(b=O3()))
    res_2 = sel.get_val(value_2)
    assert res_2 is None

def test_opt_selector_should_get_val_safe_and_unsafe_from_partial_model():
    sel = O1.a.then_val(O2.b).then_opt(O3.c).then_val(O4.d)

    value_1 = O1.partial(a=O2(b=O3.partial(c=O4(d=23))))
    res_1a = sel.get_val_unsafe(value_1)
    assert res_1a == 23
    res_1b = sel.get_val_safe(value_1)
    assert res_1b == 23

    # Valid model missing optional value
    value_2 = O1.partial(a=O2.partial(b=O3.partial()))
    res_2a = sel.get_val_unsafe(value_2)
    assert res_2a is None
    res_2b = sel.get_val_safe(value_2)
    assert res_2b is None

    # Invalid model missing required value
    value_3 = O1.partial(a=O2.partial(b=O3.partial(c=O4.partial())))
    with pytest.raises(ValueError):
        sel.get_val_unsafe(value_3)
    res_3 = sel.get_val_safe(value_3)
    assert res_3 is None

def test_opt_selector_should_get_val_safe_and_unsafe_from_dict():
    sel = O1.a.then_val(O2.b).then_opt(O3.c).then_val(O4.d)

    value_1: dict = {'a': {'b': {'c': {'d': 23}}}}
    res_1a = sel.get_val_unsafe(value_1)
    assert res_1a == 23
    res_1b = sel.get_val_safe(value_1)
    assert res_1b == 23

    # Valid model missing optional value
    value_2: dict = {'a': {'b': { }}}
    res_2a = sel.get_val_unsafe(value_2)
    assert res_2a is None
    res_2b = sel.get_val_safe(value_2)
    assert res_2b is None

    # Invalid model missing required value
    value_3: dict = {'a': {'b': {'c': {}}}}
    with pytest.raises(ValueError):
        sel.get_val_unsafe(value_3)
    res_3 = sel.get_val_safe(value_3)
    assert res_3 is None

class A4(BaseModel):
    d: Prop['A4', int]

class A3(BaseModel):
    c: PropArr['A3', A4]

class A2(BaseModel):
    b: Prop['A2', A3]

class A1(BaseModel):
    a: PropArr['A1', A2]

def test_arr_selector_should_get_val_from_model():
    sel = A1.a.then_val(A2.b).then_arr(A3.c).then_val(A4.d)

    # Model with all params
    value_1 = A1(a=[A2(b=A3(c=[A4(d=23)]))])
    res_1 = sel.get_val(value_1)
    assert res_1 == [23]

    # Model with empty array param
    value_2 = A1(a=[A2(b=A3(c=[]))])
    res_2 = sel.get_val(value_2)
    assert res_2 == []

def test_arr_selector_should_get_val_safe_and_unsafe_from_partial_model():
    sel = A1.a.then_val(A2.b).then_arr(A3.c).then_val(A4.d)

    value_1 = A1.partial(a=[A2(b=A3.partial(c=[A4(d=23)]))])
    res_1a = sel.get_val_unsafe(value_1)
    assert res_1a == [23]
    res_1b = sel.get_val_safe(value_1)
    assert res_1b == [23]

    # Valid model with empty value
    value_2 = A1.partial(a=[A2.partial(b=A3.partial(c=[]))])
    res_2a = sel.get_val_unsafe(value_2)
    assert res_2a == []
    res_2b = sel.get_val_safe(value_2)
    assert res_2b == []

    # Invalid model missing required value
    value_3 = A1.partial(a=[A2.partial(b=A3.partial(c=[A4.partial()]))])
    with pytest.raises(ValueError):
        sel.get_val_unsafe(value_3)
    res_3 = sel.get_val_safe(value_3)
    assert res_3 == []

def test_arr_selector_should_get_val_safe_and_unsafe_from_dict():
    sel = A1.a.then_val(A2.b).then_arr(A3.c).then_val(A4.d)

    value_1 = {'a': [{'b': {'c': [{'d': 23}]}}]}
    res_1a = sel.get_val_unsafe(value_1)
    assert res_1a == [23]
    res_1b = sel.get_val_safe(value_1)
    assert res_1b == [23]

    # Valid model with empty value
    value_2: dict = {'a': [{'b': {'c': []}}]}
    res_2a = sel.get_val_unsafe(value_2)
    assert res_2a == []
    res_2b = sel.get_val_safe(value_2)
    assert res_2b == []

    # Invalid model missing required value
    value_3: dict = {'a': [{'b': {'c': {}}}]}
    with pytest.raises(ValueError):
        sel.get_val_unsafe(value_3)
    res_3 = sel.get_val_safe(value_3)
    assert res_3 == []

class OA4(BaseModel):
    d: PropArr['OA4', int]

class OA3(BaseModel):
    c: PropOptArr['OA3', OA4]

class OA2(BaseModel):
    b: PropOpt['OA2', OA3]

class OA1(BaseModel):
    a: Prop['OA1', OA2]

def test_opt_arr_selector_should_get_val_from_model():
    sel = OA1.a.then_opt(OA2.b).then_opt_arr(OA3.c).then(OA4.d)

    # Model with all params
    value_1 = OA1(a=OA2(b=OA3(c=[OA4(d=[23])])))
    res_1 = sel.get_val(value_1)
    assert res_1 == [23]

    # Model with empty array value
    value_2 = OA1(a=OA2(b=OA3(c=[])))
    res_2 = sel.get_val(value_2)
    assert res_2 == []

    # Model with empty optional value
    value_3 = OA1(a=OA2())
    res_3 = sel.get_val(value_3)
    assert res_3 is None

    # Model with empty optional array value
    value_4 = OA1(a=OA2(b=OA3()))
    res_4 = sel.get_val(value_4)
    assert res_4 is None

def test_opt_arr_selector_should_get_val_safe_and_unsafe_from_partial_model():
    sel = OA1.a.then_opt(OA2.b).then_opt_arr(OA3.c).then(OA4.d)

    # Model with all params
    value_1 = OA1.partial(a=OA2(b=OA3.partial(c=[OA4(d=[23])])))
    res_1a = sel.get_val_unsafe(value_1)
    assert res_1a == [23]
    res_1b = sel.get_val_safe(value_1)
    assert res_1b == [23]

    # Model with empty array value
    value_2 = OA1(a=OA2(b=OA3(c=[])))
    res_2a = sel.get_val_unsafe(value_2)
    assert res_2a == []
    res_2b = sel.get_val_safe(value_2)
    assert res_2b == []

    # Model with empty optional value
    value_3 = OA1.partial(a=OA2.partial())
    res_3a = sel.get_val_unsafe(value_3)
    assert res_3a is None
    res_3b = sel.get_val_safe(value_3)
    assert res_3b is None

    # Model with empty optional array value
    value_4 = OA1.partial(a=OA2.partial(b=OA3.partial()))
    res_4a = sel.get_val_unsafe(value_4)
    assert res_4a is None
    res_4b = sel.get_val_safe(value_4)
    assert res_4b is None

    # Model with empty required value
    value_5 = OA1.partial(a=OA2.partial(b=OA3.partial(c=[OA4.partial()])))
    with pytest.raises(ValueError):
        sel.get_val_unsafe(value_5)
    res_5 = sel.get_val_safe(value_5)
    assert res_5 is None

def test_opt_arr_selector_should_get_val_safe_and_unsafe_from_dict():
    sel = OA1.a.then_opt(OA2.b).then_opt_arr(OA3.c).then(OA4.d)

    # Model with all params
    value_1 = {'a': {'b': {'c': [{'d': [23]}]}}}
    res_1a = sel.get_val_unsafe(value_1)
    assert res_1a == [23]
    res_1b = sel.get_val_safe(value_1)
    assert res_1b == [23]

    # Model with empty array value
    value_2: dict = {'a': {'b': {'c': []}}}
    res_2a = sel.get_val_unsafe(value_2)
    assert res_2a == []
    res_2b = sel.get_val_safe(value_2)
    assert res_2b == []

    # Model with empty optional value
    value_3: dict = {'a': {}}
    res_3a = sel.get_val_unsafe(value_3)
    assert res_3a is None
    res_3b = sel.get_val_safe(value_3)
    assert res_3b is None

    # Model with empty optional array value
    value_4: dict = {'a': {'b': {}}}
    res_4a = sel.get_val_unsafe(value_4)
    assert res_4a is None
    res_4b = sel.get_val_safe(value_4)
    assert res_4b is None

    # Model with empty required value
    value_5: dict = {'a': {'b': {'c': [{}]}}}
    with pytest.raises(ValueError):
        sel.get_val_unsafe(value_5)
    res_5 = sel.get_val_safe(value_5)
    assert res_5 is None
