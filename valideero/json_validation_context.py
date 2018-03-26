# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from collections import Sequence, Mapping

from .compat import int_types, binary_type, text_type

from .validators import make_default_validation_context

from .compat import json_repr


__all__ = ["make_json_validation_context"]


def make_json_validation_context():
    val_context = make_default_validation_context()
    val_context.repr = json_repr
    val_context.type_names.set_name_for_types("null", type(None))
    val_context.type_names.set_name_for_types("integer", *int_types)
    val_context.type_names.set_name_for_types("number", float)
    val_context.type_names.set_name_for_types("string", binary_type, text_type)
    val_context.type_names.set_name_for_types("array", list, Sequence)
    val_context.type_names.set_name_for_types("object", dict, Mapping)
    return val_context
