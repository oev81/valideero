# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import unittest
from decimal import Decimal
from functools import partial

import valideero as V
import valideero.extras
from valideero.compat import long
from .test_validators import prepare_val_context


class TestValidator(unittest.TestCase):
    def setUp(self):
        self.val_context = prepare_val_context()

    def test_accepts(self):
        @valideero.extras.accepts(self.val_context, a="fraction", b=int, body={"field_ids": ["integer"],
                                                                               V.Optional("is_ok"): bool,
                                                                               V.Optional("sex"): "gender"})
        def f(a, b=1, **body):
            pass

        valid = [
            partial(f, 2.0, field_ids=[]),
            partial(f, Decimal(1), b=5, field_ids=[1], is_ok=True),
            partial(f, a=3j, b=-1, field_ids=[long(1), 2, long(5)], sex="male"),
            partial(f, 5 + 3j, 0, field_ids=[long(-12), 0, long(0)], is_ok=False, sex="female"),
            partial(f, 2.0, field_ids=[], additional="extra param allowed"),
        ]

        invalid = [
            partial(f, 1),  # 'a' is not a fraction
            partial(f, 1.0),  # missing 'field_ids' from body
            partial(f, 1.0, b=4.1, field_ids=[]),  # 'b' is not int
            partial(f, 1.0, b=2, field_ids=3),  # 'field_ids' is not a list
            partial(f, 1.0, b=1, field_ids=[3.0]),  # 'field_ids[0]' is not a integer
            partial(f, 1.0, b=1, field_ids=[], is_ok=1),  # 'is_ok' is not bool
            partial(f, 1.0, b=1, field_ids=[], sex="m"),  # 'sex' is not a gender
        ]

        for fcall in valid:
            fcall()
        for fcall in invalid:
            self.assertRaises(V.ValidationError, fcall)

    def test_returns(self):
        @valideero.extras.returns(self.val_context, int)
        def f(a):
            return a

        @valideero.extras.returns(self.val_context, V.Type(type(None)))
        def g(a=True):
            if a:
                return a
            else:
                pass

        valid = [
            partial(f, 1),
            partial(g, False),
        ]

        invalid = [
            partial(f, 1.0),
            partial(f, 'x'),
            partial(g, True),
        ]

        for fcall in valid:
            fcall()
        for fcall in invalid:
            self.assertRaises(V.ValidationError, fcall)

    def test_adapts(self):
        @valideero.extras.adapts(self.val_context, body={
            "field_ids": ["integer"],
            V.Optional("scores"): V.Mapping("string", float),
            V.Optional("users"): [{
                "name": ("string", "string"),
                V.Optional("sex"): "gender",
                V.Optional("active", True): V.Nullable("boolean", True),
            }]})
        def f(body):
            return body

        adapted = f({
            "field_ids": [1, 5],
            "scores": {"foo": 23.1, "bar": 2.0},
            "users": [
                {"name": ("Nick", "C"), "sex": "male"},
                {"name": ("Kim", "B"), "active": False},
                {"name": ("Joe", "M"), "active": None},
            ]})

        self.assertEqual(adapted["field_ids"], [1, 5])
        self.assertEqual(adapted["scores"]["foo"], 23.1)
        self.assertEqual(adapted["scores"]["bar"], 2.0)

        self.assertEqual(adapted["users"][0]["name"], ("Nick", "C"))
        self.assertEqual(adapted["users"][0]["sex"], "male")
        self.assertEqual(adapted["users"][0]["active"], True)

        self.assertEqual(adapted["users"][1]["name"], ("Kim", "B"))
        self.assertEqual(adapted["users"][1].get("sex"), None)
        self.assertEqual(adapted["users"][1]["active"], False)

        self.assertEqual(adapted["users"][2]["name"], ("Joe", "M"))
        self.assertEqual(adapted["users"][2].get("sex"), None)
        self.assertEqual(adapted["users"][2].get("active"), True)

        invalid = [
            # missing 'field_ids' from body
            partial(f, {}),
            # score value is not float
            partial(f, {"field_ids": [], "scores": {"a": "2.3"}}),
            # 'name' is not a length-2 tuple
            partial(f, {"field_ids": [], "users": [{"name": ("Bob", "R", "Junior")}]}),
            # name[1] is not a string
            partial(f, {"field_ids": [], "users": [{"name": ("Bob", 12)}]}),
            # name[1] is required
            partial(f, {"field_ids": [], "users": [{"name": ("Bob", None)}]}),
        ]
        for fcall in invalid:
            self.assertRaises(V.ValidationError, fcall)

    def test_adapts_varargs(self):
        @valideero.extras.adapts(self.val_context, a="integer",
                                 b="number",
                                 nums=["number"])
        def f(a, b=1, *nums, **params):
            return a * b + sum(nums)

        self.assertEqual(f(2), 2)
        self.assertEqual(f(2, b=2), 4)
        self.assertEqual(f(2, 2.5, 3), 8)
        self.assertEqual(f(2, 2.5, 3, -2.5), 5.5)

    def test_adapts_kwargs(self):
        @valideero.extras.adapts(self.val_context, a="integer",
                                 b="number",
                                 params={V.Optional("foo"): int, V.Optional("bar"): float})
        def f(a, b=1, **params):
            return a * b + params.get("foo", 1) * params.get("bar", 0.0)

        self.assertEqual(f(1), 1)
        self.assertEqual(f(1, 2), 2)
        self.assertEqual(f(1, b=2.5, foo=3), 2.5)
        self.assertEqual(f(1, b=2.5, bar=3.5), 6.0)
        self.assertEqual(f(1, foo=2, bar=3.5), 8.0)
        self.assertEqual(f(1, b=2.5, foo=2, bar=3.5), 9.5)

    def test_adapts_varargs_kwargs(self):
        @valideero.extras.adapts(self.val_context, a="integer",
                                 b="number",
                                 nums=["number"],
                                 params={V.Optional("foo"): int, V.Optional("bar"): float})
        def f(a, b=1, *nums, **params):
            return a * b + sum(nums) + params.get("foo", 1) * params.get("bar", 0.0)

        self.assertEqual(f(2), 2)
        self.assertEqual(f(2, b=2), 4)
        self.assertEqual(f(2, 2.5, 3), 8)
        self.assertEqual(f(2, 2.5, 3, -2.5), 5.5)
        self.assertEqual(f(1, b=2.5, foo=3), 2.5)
        self.assertEqual(f(1, b=2.5, bar=3.5), 6.0)
        self.assertEqual(f(1, foo=2, bar=3.5), 8.0)
        self.assertEqual(f(1, b=2.5, foo=2, bar=3.5), 9.5)
        self.assertEqual(f(2, 2.5, 3, foo=2), 8.0)
        self.assertEqual(f(2, 2.5, 3, bar=3.5), 11.5)
        self.assertEqual(f(2, 2.5, 3, foo=2, bar=3.5), 15.0)
