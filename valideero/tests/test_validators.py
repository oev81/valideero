# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import collections
import re
import unittest
from datetime import date, datetime
from decimal import Decimal
from functools import partial, wraps

import valideero as V
from valideero.compat import long, xrange, string_types, int_types, text_type, binary_type


class Fraction(V.Type):
    name = "fraction"
    accept_types = (float, complex, Decimal)


class Date(V.Type):
    accept_types = (date, datetime)


class Gender(V.Enum):
    name = "gender"
    values = ("male", "female", "it's complicated")


def prepare_val_context():
    val_context = V.make_default_validation_context()
    val_context.register(Fraction.name, Fraction())
    val_context.register(Date.name, Date())
    val_context.register(Gender.name, Gender())
    return val_context


class TestValidator(unittest.TestCase):

    def setUp(self):
        self.val_context = prepare_val_context()

        self.complex_validator = self.val_context.parse({
            "n": "number",
            V.Optional("i", 0): "integer",
            V.Optional("b"): bool,
            V.Optional("e"): V.Enum("r", "g", "b"),
            V.Optional("d"): V.AnyOf("date", "datetime"),
            V.Optional("s"): V.String(min_length=1, max_length=8),
            V.Optional("p"): V.Nullable(re.compile(r"\d{1,4}$")),
            V.Optional("l"): [{"s2": "string"}],
            V.Optional("t"): (text_type, "number"),
            V.Optional("h"): V.Mapping(int, ["string"]),
            V.Optional("o"): {"i2": "integer"},
        })

    def test_none(self):
        for obj in ["boolean", "integer", "number", "string",
                    V.HomogeneousSequence, V.HeterogeneousSequence,
                    V.Mapping, int, float, text_type,
                    Fraction, Fraction(), Gender, Gender(), V.Object, V.Object()]:
            self.assertFalse(self.val_context.parse(obj).is_valid(None))

    def test_boolean(self):
        for obj in "boolean", V.Boolean, V.Boolean():
            self._testValidation(obj,
                                 valid=[True, False],
                                 invalid=[1, 1.1, "foo", u"bar", {}, []])

    def test_integer(self):
        for obj in "integer", V.Integer, V.Integer():
            self._testValidation(obj,
                                 valid=[1],
                                 invalid=[1.1, "foo", u"bar", {}, [], False, True])

    def test_int(self):
        # bools are ints
        self._testValidation(int,
                             valid=[1, True, False],
                             invalid=[1.1, "foo", u"bar", {}, []])

    def test_number(self):
        for obj in "number", V.Number, V.Number():
            self._testValidation(obj,
                                 valid=[1, 1.1],
                                 invalid=["foo", u"bar", {}, [], False, True])

    def test_float(self):
        self._testValidation(float,
                             valid=[1.1],
                             invalid=[1, "foo", u"bar", {}, [], False, True])

    def test_string(self):
        for obj in "string", V.String, V.String():
            self._testValidation(obj,
                                 valid=["foo", u"bar"],
                                 invalid=[1, 1.1, {}, [], False, True])

    def test_string_min_length(self):
        self._testValidation(V.String(min_length=2),
                             valid=["foo", u"fo"],
                             invalid=[u"f", "", False])

    def test_string_max_length(self):
        self._testValidation(V.String(max_length=2),
                             valid=["", "f", u"fo"],
                             invalid=[u"foo", [1, 2, 3]])

    def test_pattern(self):
        self._testValidation(re.compile(r"a*$"),
                             valid=["aaa"],
                             invalid=[u"aba", "baa"])

    def test_range(self):
        self._testValidation(V.Range("integer", 1),
                             valid=[1, 2, 3],
                             invalid=[0, -1])
        self._testValidation(V.Range("integer", max_value=2),
                             valid=[-1, 0, 1, 2],
                             invalid=[3])
        self._testValidation(V.Range("integer", 1, 2),
                             valid=[1, 2],
                             invalid=[-1, 0, 3])
        self._testValidation(V.Range(min_value=1, max_value=2),
                             valid=[1, 2],
                             invalid=[-1, 0, 3])

    def test_homogeneous_sequence(self):
        for obj in V.HomogeneousSequence, V.HomogeneousSequence():
            self._testValidation(obj,
                                 valid=[[], [1], (1, 2), [1, (2, 3), 4]],
                                 invalid=[1, 1.1, "foo", u"bar", {}, False, True])
        self._testValidation(["number"],
                             valid=[[], [1, 2.1, long(3)], (1, long(4), 6)],
                             invalid=[[1, 2.1, long(3), u"x"]])

    def test_heterogeneous_sequence(self):
        for obj in V.HeterogeneousSequence, V.HeterogeneousSequence():
            self._testValidation(obj,
                                 valid=[(), []],
                                 invalid=[1, 1.1, "foo", u"bar", {}, False, True])
        self._testValidation(("string", "number"),
                             valid=[("a", 2), [u"b", 4.1]],
                             invalid=[[], (), (2, "a"), ("a", "b"), (1, 2)])

    def test_sequence_min_length(self):
        self._testValidation(V.HomogeneousSequence(int, min_length=2),
                             valid=[[1, 2, 4], (1, 2)],
                             invalid=[[1], [], (), "123", "", False])

    def test_sequence_max_length(self):
        self._testValidation(V.HomogeneousSequence(int, max_length=2),
                             valid=[[], (), (1,), (1, 2), [1, 2]],
                             invalid=[[1, 2, 3], "123", "f"])

    def test_mapping(self):
        for obj in V.Mapping, V.Mapping():
            self._testValidation(obj,
                                 valid=[{}, {"foo": 3}],
                                 invalid=[1, 1.1, "foo", u"bar", [], False, True])
        self._testValidation(V.Mapping("string", "number"),
                             valid=[{"foo": 3},
                                    {"foo": 3, u"bar": -2.1, "baz": Decimal("12.3")}],
                             invalid=[{"foo": 3, ("bar",): -2.1},
                                      {"foo": 3, "bar": "2.1"}])

    def test_object(self):
        for obj in V.Object, V.Object():
            self._testValidation(obj,
                                 valid=[{}, {"foo": 3}],
                                 invalid=[1, 1.1, "foo", u"bar", [], False, True])
        self._testValidation({"foo": "number", "bar": "string"},
                             valid=[{"foo": 1, "bar": "baz"},
                                    {"foo": 1, "bar": "baz", "quux": 42}],
                             invalid=[{"foo": 1, "bar": []},
                                      {"foo": "baz", "bar": 2.3}])

    def test_required_properties_global(self):
        self._testValidation({"foo": "number", V.Optional("bar"): "boolean", "baz": "string"},
                             valid=[{"foo": -23., "baz": "yo"}],
                             invalid=[{},
                                      {"bar": True},
                                      {"baz": "yo"},
                                      {"foo": 3},
                                      {"bar": False, "baz": "yo"},
                                      {"bar": True, "foo": 3.1}])

    def test_required_properties_parse_parameter(self):
        schema = {
            "foo": "number",
            V.Optional("bar"): "boolean",
            V.Optional("nested"): [{
                "baz": "string"
            }]
        }
        missing_properties = [{}, {"bar": True}, {"foo": 3, "nested": [{}]}]
        for _ in xrange(3):
            self._testValidation(self.val_context.parse(schema), invalid=missing_properties)

    def test_ignore_optional_property_errors_parse_parameter(self):
        schema = {
            "foo": "number",
            V.Optional("bar"): "boolean",
            V.Optional("nested"): [{
                "baz": "string",
                V.Optional("zoo"): "number",
            }]
        }
        invalid_required = [
            {"foo": "2", "bar": True},
        ]
        invalid_optional = [
            {"foo": 3, "bar": "nan"},
            {"foo": 3.1, "nested": [{"baz": "x", "zoo": "12"}]},
            {"foo": 0, "nested": [{"baz": 1, "zoo": 2}]},
        ]
        adapted = [
            {"foo": 3},
            {"foo": 3.1, "nested": [{"baz": "x"}]},
            {"foo": 0},
        ]
        for _ in xrange(3):
            self.val_context.validators_factories['Object'].ignore_optional_property_errors = False
            self._testValidation(self.val_context.parse(schema), invalid=invalid_required + invalid_optional)
            self.val_context.validators_factories['Object'].ignore_optional_property_errors = True
            self._testValidation(self.val_context.parse(schema), invalid=invalid_required,
                                 adapted=zip(invalid_optional, adapted))

    def test_adapt_missing_property(self):
        self._testValidation({"foo": "number", V.Optional("bar", False): "boolean"},
                             adapted=[({"foo": -12}, {"foo": -12, "bar": False})])

    def test_no_additional_properties(self):
        self._testValidation(V.Object({"foo": "number",
                                       V.Optional("bar"): "string"},
                                      additional=False),
                             valid=[{"foo": 23},
                                    {"foo": -23., "bar": "yo"}],
                             invalid=[{"foo": 23, "xyz": 1},
                                      {"foo": -23., "bar": "yo", "xyz": 1}]
                             )

    def test_remove_additional_properties(self):
        self._testValidation(V.Object({"foo": "number",
                                       V.Optional("bar"): "string"},
                                      additional=V.REMOVE),
                             adapted=[({"foo": 23}, {"foo": 23}),
                                      ({"foo": -23., "bar": "yo"}, {"foo": -23., "bar": "yo"}),
                                      ({"foo": 23, "xyz": 1}, {"foo": 23}),
                                      ({"foo": -23., "bar": "yo", "xyz": 1}, {"foo": -23., "bar": "yo"})]
                             )

    def test_additional_properties_schema(self):
        self._testValidation(V.Object({"foo": "number",
                                       V.Optional("bar"): "string"},
                                      additional="boolean"),
                             valid=[{"foo": 23, "bar": "yo", "x1": True, "x2": False}],
                             invalid=[{"foo": 23, "x1": 1},
                                      {"foo": -23., "bar": "yo", "x1": True, "x2": 0}]
                             )

    def test_additional_properties_parse_parameter(self):
        schema = {
            V.Optional("bar"): "boolean",
            V.Optional("nested"): [{
                V.Optional("baz"): "integer"
            }]
        }
        values = [{"x1": "yes"},
                  {"bar": True, "nested": [{"x1": "yes"}]}]
        for _ in xrange(3):
            self.val_context.validators_factories['Object'].additional_properties = True
            self._testValidation(schema,
                                 valid=values)
            self.val_context.validators_factories['Object'].additional_properties = False
            self._testValidation(schema,
                                 invalid=values)
            self.val_context.validators_factories['Object'].additional_properties = V.REMOVE
            self._testValidation(schema,
                                 adapted=[(values[0], {}), (values[1], {"bar": True, "nested": [{}]})])
            self.val_context.validators_factories['Object'].additional_properties = "string"
            self._testValidation(schema,
                                 valid=values, invalid=[{"x1": 42}, {"bar": True, "nested": [{"x1": 42}]}])

    def test_enum(self):
        self._testValidation(V.Enum(1, 2, 3),
                             valid=[1, 2, 3], invalid=[0, 4, "1", [1]])
        self._testValidation(V.Enum(u"foo", u"bar"),
                             valid=["foo", "bar"], invalid=["", "fooabar", ["foo"]])
        self._testValidation(V.Enum(True),
                             valid=[True], invalid=[False, [True]])
        self._testValidation(V.Enum({"foo": u"bar"}),
                             valid=[{u"foo": "bar"}])
        self._testValidation(V.Enum({"foo": u"quux"}),
                             invalid=[{u"foo": u"bar"}])

    def test_enum_class(self):
        for obj in "gender", Gender, Gender():
            self._testValidation(obj,
                                 valid=["male", "female", "it's complicated"],
                                 invalid=["other", ""])

    def test_nullable(self):
        for obj in V.Nullable("integer"), V.Nullable(V.Integer()):
            self._testValidation(obj,
                                 valid=[None, 0],
                                 invalid=[1.1, True, False])
        self._testValidation(V.Nullable([V.Nullable("string")]),
                             valid=[None, [], ["foo"], [None], ["foo", None]],
                             invalid=["", [None, "foo", 1]])

    def test_nullable_with_default(self):
        self._testValidation(V.Nullable("integer", -1),
                             adapted=[(None, -1), (0, 0)],
                             invalid=[1.1, True, False])
        self._testValidation(V.Nullable("integer", lambda: -1),
                             adapted=[(None, -1), (0, 0)],
                             invalid=[1.1, True, False])

    def test_optional_properties_with_default(self):

        regular_nullables = [
            V.Nullable("integer"),
            V.Nullable("integer", None),
            V.Nullable("integer", default=None),
            V.Nullable("integer", lambda: None),
            V.Nullable("integer", default=lambda: None)
        ]
        for obj in regular_nullables:
            self._testValidation({V.Optional("foo"): obj}, adapted=[({}, {})])

        optionals = [
            V.Optional("foo", None),
            V.Optional("foo", default=None),
            V.Optional("foo", lambda: None),
            V.Optional("foo", default=lambda: None)
        ]
        for property in optionals:
            self._testValidation({property: V.Nullable("integer")}, adapted=[({}, {"foo": None})])

    def test_anyof(self):
        self._testValidation(V.AnyOf("integer", {"foo": "integer"}),
                             valid=[1, {"foo": 1}],
                             invalid=[{"foo": 1.1}])

    def test_allof(self):
        self._testValidation(V.AllOf({"id": "integer"}, V.Mapping("string", "number")),
                             valid=[{"id": 3}, {"id": 3, "bar": 4.5}],
                             invalid=[{"id": 1.1, "bar": 4.5},
                                      {"id": 3, "bar": True},
                                      {"id": 3, 12: 4.5}])

        self._testValidation(V.AllOf("number",
                                     lambda x: x > 0,
                                     V.AdaptBy(datetime.utcfromtimestamp)),
                             adapted=[(1373475820, datetime(2013, 7, 10, 17, 3, 40))],
                             invalid=["1373475820", -1373475820])

    def test_chainof(self):
        self._testValidation(V.ChainOf(V.AdaptTo(int),
                                       V.Condition(lambda x: x > 0),
                                       V.AdaptBy(datetime.utcfromtimestamp)),
                             adapted=[(1373475820, datetime(2013, 7, 10, 17, 3, 40)),
                                      ("1373475820", datetime(2013, 7, 10, 17, 3, 40))],
                             invalid=["nan", -1373475820])

    def test_condition(self):
        def is_odd(n):
            return n % 2 == 1

        is_even = lambda n: n % 2 == 0

        class C(object):
            def is_odd_method(self, n):
                return is_odd(n)

            def is_even_method(self, n):
                return is_even(n)

            is_odd_static = staticmethod(is_odd)
            is_even_static = staticmethod(is_even)

        for obj in is_odd, C().is_odd_method, C.is_odd_static:
            self._testValidation(obj,
                                 valid=[1, long(3), -11, 9.0, True],
                                 invalid=[6, 2.1, False, "1", []])

        for obj in is_even, C().is_even_method, C.is_even_static:
            self._testValidation(obj,
                                 valid=[6, long(2), -42, 4.0, 0, 0.0, False],
                                 invalid=[1, 2.1, True, "2", []])

        self._testValidation(text_type.isalnum,
                             valid=["abc", "123", "ab32c"],
                             invalid=["a+b", "a 1", "", True, 2])

        self.assertRaises(TypeError, V.Condition, C)
        self.assertRaises(TypeError, V.Condition(is_even, traps=()).validate, [2, 4])

    def test_condition_partial(self):
        def max_range(sequence, range_limit):
            return max(sequence) - min(sequence) <= range_limit

        f = wraps(max_range)(partial(max_range, range_limit=10))

        for obj in f, V.Condition(f):
            self._testValidation(obj,
                                 valid=[xrange(11), xrange(1000, 1011)],
                                 invalid=[xrange(12), [0, 1, 2, 3, 4, 11]])

    def test_adapt_ordered_dict_object(self):
        self._testValidation(
            {"foo": V.AdaptTo(int), "bar": V.AdaptTo(float)},
            adapted=[(
                collections.OrderedDict([("foo", "1"), ("bar", "2")]),
                collections.OrderedDict([("foo", 1), ("bar", 2.0)])
            )])

    def test_adapt_ordered_dict_mapping(self):
        self._testValidation(
            V.Mapping("string", V.AdaptTo(float)),
            adapted=[(
                collections.OrderedDict([("foo", "1"), ("bar", "2")]),
                collections.OrderedDict([("foo", 1.0), ("bar", 2.0)])
            )])

    def test_adapt_by(self):
        self._testValidation(V.AdaptBy(lambda x: text_type(hex(x)), traps=TypeError),
                             invalid=[1.2, "1"],
                             adapted=[(255, "0xff"), (0, "0x0")])
        self._testValidation(V.AdaptBy(int, traps=(ValueError, TypeError)),
                             invalid=["12b", "1.2", {}, (), []],
                             adapted=[(12, 12), ("12", 12), (1.2, 1)])
        self.assertRaises(TypeError, V.AdaptBy(hex, traps=()).validate, 1.2)

    def test_adapt_to(self):
        self.assertRaises(TypeError, V.AdaptTo, hex)
        for exact in False, True:
            self._testValidation(V.AdaptTo(int, traps=(ValueError, TypeError), exact=exact),
                                 invalid=["12b", "1.2", {}, (), []],
                                 adapted=[(12, 12), ("12", 12), (1.2, 1)])

        class smallint(int):
            pass

        i = smallint(2)
        self.assertIs(V.AdaptTo(int).validate(i), i)
        self.assertIsNot(V.AdaptTo(int, exact=True).validate(i), i)

    def test_fraction(self):
        for obj in "fraction", Fraction, Fraction():
            self._testValidation(obj,
                                 valid=[1.1, 0j, 5 + 3j, Decimal(1) / Decimal(8)],
                                 invalid=[1, "foo", u"bar", {}, [], False, True])

    def test_reject_types(self):
        schema = V.Type(accept_types=Exception, reject_types=Warning)
        exception_validator = self.val_context.parse(schema)
        exception_validator.validate(KeyError())
        self.assertRaises(V.ValidationError, exception_validator.validate, UserWarning())

    def test_schema_errors(self):
        for obj in [
            True,
            1,
            3.2,
            "foo",
            object(),
            ["foo"],
            {"field": "foo"},
        ]:
            self.assertRaises(V.SchemaError, self.val_context.parse, obj)

    def test_not_implemented_validation(self):
        class MyValidator(V.Validator):
            pass

        validator = MyValidator()
        self.assertRaises(NotImplementedError, validator.validate, 1)

    def test_register(self):
        for register in (self.val_context.register,):
            register("to_int", V.AdaptTo(int, traps=(ValueError, TypeError)))
            self._testValidation("to_int",
                                 invalid=["12b", "1.2"],
                                 adapted=[(12, 12), ("12", 12), (1.2, 1)])

            self.assertRaises(TypeError, register, "to_int", int)

    def test_complex_validation(self):

        for valid in [
            {'n': 2},
            {'n': 2.1, 'i': 3},
            {'n': -1, 'b': False},
            {'n': Decimal(3), 'e': "r"},
            {'n': long(2), 'd': datetime.now()},
            {'n': 0, 'd': date.today()},
            {'n': 0, 's': "abc"},
            {'n': 0, 'p': None},
            {'n': 0, 'p': "123"},
            {'n': 0, 'l': []},
            {'n': 0, 'l': [{"s2": "foo"}, {"s2": ""}]},
            {'n': 0, 't': (u"joe", 3.1)},
            {'n': 0, 'h': {5: ["foo", u"bar"], 0: []}},
            {'n': 0, 'o': {"i2": 3}},
        ]:
            self.complex_validator.validate(valid)

        for invalid in [
            None,
            {},
            {'n': None},
            {'n': True},
            {'n': 1, 'e': None},
            {'n': 1, 'e': "a"},
            {'n': 1, 'd': None},
            {'n': 1, 's': None},
            {'n': 1, 's': ''},
            {'n': 1, 's': '123456789'},
            {'n': 1, 'p': '123a'},
            {'n': 1, 'l': None},
            {'n': 1, 'l': [None]},
            {'n': 1, 'l': [{}]},
            {'n': 1, 'l': [{'s2': None}]},
            {'n': 1, 'l': [{'s2': 1}]},
            {'n': 1, 't': ()},
            {'n': 0, 't': (3.1, u"joe")},
            {'n': 0, 't': (u"joe", None)},
            {'n': 1, 'h': {5: ["foo", u"bar"], "0": []}},
            {'n': 1, 'h': {5: ["foo", 2.1], 0: []}},
            {'n': 1, 'o': {}},
            {'n': 1, 'o': {"i2": "2"}},
        ]:
            self.assertRaises(V.ValidationError,
                              self.complex_validator.validate, invalid)

    def test_complex_adaptation(self):
        for value in [
            {'n': 2},
            {'n': 2.1, 'i': 3},
            {'n': -1, 'b': False},
            {'n': Decimal(3), 'e': "r"},
            {'n': long(2), 'd': datetime.now()},
            {'n': 0, 'd': date.today()},
            {'n': 0, 's': "abc"},
            {'n': 0, 'p': None},
            {'n': 0, 'p': "123"},
            {'n': 0, 'l': []},
            {'n': 0, 'l': [{"s2": "foo"}, {"s2": ""}]},
            {'n': 0, 't': (u"joe", 3.1)},
            {'n': 0, 'h': {5: ["foo", u"bar"], 0: []}},
            {'n': 0, 'o': {"i2": 3}},
        ]:
            adapted = self.complex_validator.validate(value)
            self.assertTrue(isinstance(adapted["n"], (int, long, float, Decimal)))
            self.assertTrue(isinstance(adapted["i"], int_types))
            self.assertTrue(adapted.get("b") is None or isinstance(adapted["b"], bool))
            self.assertTrue(adapted.get("d") is None or isinstance(adapted["d"], (date, datetime)))
            self.assertTrue(adapted.get("e") is None or adapted["e"] in "rgb")
            self.assertTrue(adapted.get("s") is None or isinstance(adapted["s"], string_types))
            self.assertTrue(adapted.get("l") is None or isinstance(adapted["l"], list))
            self.assertTrue(adapted.get("t") is None or isinstance(adapted["t"], tuple))
            self.assertTrue(adapted.get("h") is None or isinstance(adapted["h"], dict))
            if adapted.get("l") is not None:
                self.assertTrue(all(isinstance(item["s2"], string_types)
                                    for item in adapted["l"]))
            if adapted.get("t") is not None:
                self.assertEqual(len(adapted["t"]), 2)
                self.assertTrue(isinstance(adapted["t"][0], text_type))
                self.assertTrue(isinstance(adapted["t"][1], float))
            if adapted.get("h") is not None:
                self.assertTrue(all(isinstance(key, int)
                                    for key in adapted["h"].keys()))
                self.assertTrue(all(isinstance(value_item, string_types)
                                    for value in adapted["h"].values()
                                    for value_item in value))
            if adapted.get("o") is not None:
                self.assertTrue(isinstance(adapted["o"]["i2"], int_types))

    def test_humanized_names(self):
        class DummyValidator(V.Validator):
            name = "dummy"

            def validate(self, value):
                return value

        self.val_context.type_names.set_name_for_types("null", type(None))
        validator = self.val_context.parse(DummyValidator())
        self.assertEqual(validator.humanized_name, "dummy")

        validator = self.val_context.parse(V.Nullable(DummyValidator()))
        self.assertEqual(validator.humanized_name, "dummy or null")

        validator = self.val_context.parse(V.AnyOf("boolean", DummyValidator()))
        self.assertEqual(validator.humanized_name, "boolean or dummy")

        validator = self.val_context.parse(V.AllOf("boolean", DummyValidator()))
        self.assertEqual(validator.humanized_name, "boolean and dummy")

        validator = self.val_context.parse(V.ChainOf("boolean", DummyValidator()))
        self.assertEqual(validator.humanized_name, "boolean chained to dummy")

        validator = self.val_context.parse(Date())
        self.assertEqual(validator.humanized_name, "date or datetime")

    def test_error_message(self):
        self._testValidation({"foo": "number", V.Optional("bar"): ["integer"]}, errors=[
            (42,
             "Invalid value 42 (int): must be Mapping"),
            ({},
             "Invalid value {} (dict): missing required properties: ['foo']"),
            ({"foo": b"3"},
             "Invalid value '3' ({}): must be number (at foo)".format(binary_type.__name__)),
            ({"foo": "3"},
             "Invalid value '3' ({}): must be number (at foo)".format(text_type.__name__)),
            ({"foo": 3, "bar": None},
             "Invalid value None (NoneType): must be Sequence (at bar)"),
            ({"foo": 3, "bar": [1, "2", 3]},
             "Invalid value '2' ({}): must be integer (at bar[1])".format(text_type.__name__)),
        ])

    def test_error_properties(self):
        for contexts in [], ['bar'], ['bar', 'baz']:
            ex = V.ValidationError(self.val_context, 'foo')
            for context in contexts:
                ex.add_error_path_item(context)
            self.assertEqual(ex.message, text_type(ex))
            self.assertEqual(ex.args, (text_type(ex),))

    def test_error_message_json_type_names(self):
        self.val_context = V.make_json_validation_context()

        self._testValidation({"foo": "number",
                              V.Optional("bar"): ["integer"],
                              V.Optional("baz"): V.AnyOf("number", ["number"]),
                              V.Optional("opt"): V.Nullable("string")},
                             errors=
                             [(42, "Invalid value 42 (integer): must be object"),
                              ({},
                               'Invalid value {} (object): missing required properties: ["foo"]'),
                              ({"foo": "3"},
                               'Invalid value "3" (string): must be number (at foo)'),
                              ({"foo": None},
                               "Invalid value null (null): must be number (at foo)"),
                              ({"foo": 3, "bar": None},
                               "Invalid value null (null): must be array (at bar)"),
                              ({"foo": 3, "bar": [1, "2", 3]},
                               'Invalid value "2" (string): must be integer (at bar[1])'),
                              ({"foo": 3, "baz": "23"},
                               'Invalid value "23" (string): must be number or must be array (at baz)'),
                              ({"foo": 3, "opt": 12},
                               "Invalid value 12 (integer): must be string or must be null (at opt)")])

    def _testValidation(self, obj, invalid=(), valid=(), adapted=(), errors=()):
        validator = self.val_context.parse(obj)
        for from_value, to_value in [(value, value) for value in valid] + list(adapted):
            self.assertTrue(validator.is_valid(from_value))
            adapted_value = validator.validate(from_value)
            self.assertIs(adapted_value.__class__, to_value.__class__)
            self.assertEqual(adapted_value, to_value)
        for value, error in [(value, None) for value in invalid] + list(errors):
            self.assertFalse(validator.is_valid(value))
            try:
                validator.validate(value)
            except V.ValidationError as ex:
                if error:
                    error_text = ex.to_text()
                    self.assertEqual(error_text, error, "Actual error: {}".format(error_text))


if __name__ == '__main__':
    unittest.main()
