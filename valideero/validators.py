# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import collections
import datetime
import inspect
import numbers
import re

from .base import Validator, ValidationError, ValidationContext, UNDEFINED, TypeNames
from .compat import string_types, izip, imap, iteritems, text_type, unicode_safe, compatible_repr

__all__ = [
    "AnyOf", "AllOf", "ChainOf", "Nullable", "NoneValue",
    "Enum", "Condition", "AdaptBy", "AdaptTo",
    "Type", "Boolean", "Integer", "Number", "Range",
    "String", "Pattern", "Date", "Datetime", "Time",
    "HomogeneousSequence", "HeterogeneousSequence", "Mapping", "Object",
    "ObjectFactory", "make_default_validation_context", "Optional", "REMOVE",
]


class Composite(Validator):
    def __init__(self, *schemas):
        super(Composite, self).__init__()
        self._schemas = schemas
        self._validators = []

    def parse(self):
        if hasattr(self, '_schemas'):
            self._validators = list(imap(self.val_context.parse, self._schemas))
            del self._schemas

    def validate(self, value):
        raise NotImplementedError()


class AnyOf(Composite):
    """A composite validator that accepts values accepted by any of its component
    validators.

    In case of adaptation, the first validator to successfully adapt the value
    is used.
    """

    def validate(self, value):
        messages = []
        for validator in self._validators:
            try:
                return validator.validate(value)
            except ValidationError as ex:
                messages.append(ex.msg)
        raise ValidationError(self.val_context, " or ".join(messages), value)

    @property
    def humanized_name(self):
        return " or ".join(v.humanized_name for v in self._validators)


class AllOf(Composite):
    """A composite validator that accepts values accepted by all of its component
    validators.

    In case of adaptation, the adapted value from the last validator is returned.
    """

    def validate(self, value):
        result = value
        for validator in self._validators:
            result = validator.validate(value)
        return result

    @property
    def humanized_name(self):
        return " and ".join(v.humanized_name for v in self._validators)


class ChainOf(Composite):
    """A composite validator that passes a value through a sequence of validators.

    value -> validator1 -> value2 -> validator2 -> ... -> validatorN -> final_value
    """

    def validate(self, value):
        for validator in self._validators:
            value = validator.validate(value)
        return value

    @property
    def humanized_name(self):
        return " chained to ".join(v.humanized_name for v in self._validators)


class NoneValue(Validator):
    """A validator that accepts only ``None``.

    ``None`` is adapted to ``default``. ``default`` can also be a zero-argument
    callable, in which case ``None`` is adapted to ``default()``.
    """

    def __init__(self, default=None):
        self._default = default
        super(NoneValue, self).__init__()

    def validate(self, value):
        if value is not None:
            self.error(value)
        return self._default if not callable(self._default) else self._default()

    @property
    def humanized_name(self):
        return self.val_context.type_names.get_type_name(type(None))


class Nullable(Validator):
    """A validator that also accepts ``None``.

    ``None`` is adapted to ``default``. ``default`` can also be a zero-argument
    callable, in which case ``None`` is adapted to ``default()``.
    """

    def __init__(self, schema, default=None):
        super(Nullable, self).__init__()
        self._schema = schema
        self._default = default
        self._validator = None

    def parse(self):
        if hasattr(self, '_schema'):
            validator = self.val_context.parse(self._schema)
            none_validator = self.val_context.parse(NoneValue(self._default))
            if isinstance(validator, AnyOf):
                validator._validators.append(none_validator)
                self._validator = validator
            else:
                self._validator = self.val_context.parse(AnyOf(validator, none_validator))
            del self._schema

    def validate(self, value):
        return self._validator.validate(value)

    @property
    def humanized_name(self):
        return self._validator.humanized_name


class Enum(Validator):
    """A validator that accepts only a finite set of values.

    Attributes:
        - values: The collection of valid values.
    """

    values = ()

    def __init__(self, *values):
        super(Enum, self).__init__()
        if len(values) == 0:
            values = self.values
        try:
            self.values = set(values)
        except TypeError:  # unhashable
            self.values = list(values)

    def validate(self, value):
        try:
            if value in self.values:
                return value
        except TypeError:  # unhashable
            pass
        self.error(value)

    @property
    def humanized_name(self):
        return "one of {{{}}}".format(", ".join(list(imap(self.val_context.repr, self.values))))


class Condition(Validator):
    """A validator that accepts a value using a callable ``predicate``.

    A value is accepted if ``predicate(value)`` is true.
    """

    def __init__(self, predicate, traps=Exception):
        super(Condition, self).__init__()
        if not (callable(predicate) and not inspect.isclass(predicate)):
            raise TypeError("Callable expected, {} given".format(unicode_safe(predicate.__class__)))
        self._predicate = predicate
        self._traps = traps

    def validate(self, value):
        if self._traps:
            try:
                is_valid = self._predicate(value)
            except self._traps:
                is_valid = False
        else:
            is_valid = self._predicate(value)

        if not is_valid:
            self.error(value)

        return value

    def error(self, value):
        raise ValidationError(self.val_context,
                              "must satisfy predicate {}".format(self.humanized_name),
                              value)

    @property
    def humanized_name(self):
        return text_type(getattr(self._predicate, "__name__", self._predicate))


def condition_factory(obj):
    """Parse a callable as a Condition validator."""
    if callable(obj) and not inspect.isclass(obj):
        return Condition(obj)


class AdaptBy(Validator):
    """A validator that adapts a value using an ``adaptor`` callable."""

    def __init__(self, adaptor, traps=Exception):
        """Instantiate this validator.

        :param adaptor: The callable ``f(value)`` to adapt values.
        :param traps: An exception or a tuple of exceptions to catch and wrap
            into a :py:exc:`ValidationError`. Any other raised exception is
            left to propagate.
        """
        super(AdaptBy, self).__init__()
        self._adaptor = adaptor
        self._traps = traps

    def validate(self, value):
        if not self._traps:
            return self._adaptor(value)
        try:
            return self._adaptor(value)
        except self._traps as ex:
            raise ValidationError(self.val_context, text_type(ex), value)


class AdaptTo(AdaptBy):
    """A validator that adapts a value to a target class."""

    def __init__(self, target_cls, traps=Exception, exact=False):
        """Instantiate this validator.

        :param target_cls: The target class.
        :param traps: An exception or a tuple of exceptions to catch and wrap
            into a :py:exc:`ValidationError`. Any other raised exception is left
            to propagate.
        :param exact: If False, instances of ``target_cls`` or a subclass are
            returned as is. If True, only instances of ``target_cls`` are
            returned as is.
        """
        if not inspect.isclass(target_cls):
            raise TypeError("Type expected, {} given".format(unicode_safe(target_cls.__name__)))
        self._exact = exact
        super(AdaptTo, self).__init__(target_cls, traps)

    def validate(self, value):
        if isinstance(value, self._adaptor) and (not self._exact or
                                                 value.__class__ == self._adaptor):
            return value
        return super(AdaptTo, self).validate(value)


class Type(Validator):
    """A validator accepting values that are instances of one or more given types.

    Attributes:
        - accept_types: A type or tuple of types that are valid.
        - reject_types: A type or tuple of types that are invalid.
    """

    accept_types = ()
    reject_types = ()

    def __init__(self, accept_types=None, reject_types=None):
        if accept_types is not None:
            self.accept_types = accept_types
        if reject_types is not None:
            self.reject_types = reject_types
        super(Type, self).__init__()

    def validate(self, value):
        if not isinstance(value, self.accept_types) or isinstance(value, self.reject_types):
            self.error(value)
        return value

    @property
    def humanized_name(self):
        return self.name or self.val_context.type_names.format_types(self.accept_types)


def type_factory(obj):
    """Parse a python type (or "old-style" class) as a :py:class:`Type` instance."""
    if inspect.isclass(obj):
        return Type(accept_types=obj)


class Boolean(Type):
    """A validator that accepts bool values."""

    name = "boolean"
    accept_types = bool


class Integer(Type):
    """
    A validator that accepts integers (:py:class:`numbers.Integral` instances)
    but not bool.
    """

    name = "integer"
    accept_types = numbers.Integral
    reject_types = bool


class Range(Validator):
    """A validator that accepts values within in a certain range."""

    def __init__(self, schema=None, min_value=None, max_value=None):
        """Instantiate a :py:class:`Range` validator.

        :param schema: Optional schema or validator for the value.
        :param min_value: If not None, values less than ``min_value`` are
            invalid.
        :param max_value: If not None, values larger than ``max_value`` are
            invalid.
        """
        super(Range, self).__init__()
        self._schema = schema
        self._validator = None
        self._min_value = min_value
        self._max_value = max_value

    def parse(self):
        if hasattr(self, '_schema') and self._schema is not None:
            self._validator = self.val_context.parse(self._schema)
            del self._schema

    def validate(self, value):
        if self._validator is not None:
            value = self._validator.validate(value)

        if self._min_value is not None and value < self._min_value:
            raise ValidationError(self.val_context,
                                  "must not be less than {}".format(self._min_value),
                                  value)
        if self._max_value is not None and value > self._max_value:
            raise ValidationError(self.val_context,
                                  "must not be larger than {}".format(self._max_value),
                                  value)
        return value


class Number(Type):
    """A validator that accepts any numbers (but not bool)."""

    name = "number"
    accept_types = numbers.Number
    reject_types = bool


class Date(Type):
    """A validator that accepts :py:class:`datetime.date` values."""

    name = "date"
    accept_types = datetime.date


class Datetime(Type):
    """A validator that accepts :py:class:`datetime.datetime` values."""

    name = "datetime"
    accept_types = datetime.datetime


class Time(Type):
    """A validator that accepts :py:class:`datetime.time` values."""

    name = "time"
    accept_types = datetime.time


class String(Type):
    """A validator that accepts string values."""

    name = "string"
    accept_types = string_types

    def __init__(self, min_length=None, max_length=None):
        """Instantiate a String validator.

        :param min_length: If not None, strings shorter than ``min_length`` are
            invalid.
        :param max_length: If not None, strings longer than ``max_length`` are
            invalid.
        """
        self._min_length = min_length
        self._max_length = max_length
        super(String, self).__init__()

    def validate(self, value):
        super(String, self).validate(value)
        if self._min_length is not None and len(value) < self._min_length:
            raise ValidationError(self.val_context,
                                  "must be at least {} characters long".format(self._min_length),
                                  value)
        if self._max_length is not None and len(value) > self._max_length:
            raise ValidationError(self.val_context,
                                  "must be at most {} characters long".format(self._max_length),
                                  value)
        return value


_SRE_Pattern = type(re.compile(""))


class Pattern(Type):
    """A validator that accepts strings that match a given regular expression.

    Attributes:
        - regexp: The regular expression (string or compiled) to be matched.
    """
    accept_types = string_types

    def __init__(self, regexp):
        super(Pattern, self).__init__()
        self.regexp = re.compile(regexp)

    def validate(self, value):
        super(Pattern, self).validate(value)
        if not self.regexp.match(value):
            self.error(value)
        return value

    def error(self, value):
        raise ValidationError(self.val_context,
                              "must match {}".format(self.humanized_name),
                              value)

    @property
    def humanized_name(self):
        return "pattern {}".format(unicode_safe(self.regexp.pattern))


def pattern_factory(obj):
    """Parse a compiled regexp as a :py:class:`Pattern` instance."""
    if isinstance(obj, _SRE_Pattern):
        return Pattern(obj)


class HomogeneousSequence(Type):
    """A validator that accepts homogeneous, non-fixed size sequences."""

    accept_types = collections.Sequence
    reject_types = string_types

    def __init__(self, item_schema=None, min_length=None, max_length=None):
        """Instantiate a :py:class:`HomogeneousSequence` validator.

        :param item_schema: If not None, the schema of the items of the list.
        """
        super(HomogeneousSequence, self).__init__()
        self._item_schema = item_schema
        self._min_length = min_length
        self._max_length = max_length
        self._item_validator = None

    def parse(self):
        if hasattr(self, '_item_schema') and self._item_schema is not None:
            self._item_validator = self.val_context.parse(self._item_schema)
            del self._item_schema

    def validate(self, value):
        super(HomogeneousSequence, self).validate(value)
        if self._min_length is not None and len(value) < self._min_length:
            raise ValidationError(self.val_context,
                                  "must contain at least {} elements".format(self._min_length),
                                  value)
        if self._max_length is not None and len(value) > self._max_length:
            raise ValidationError(self.val_context,
                                  "must contain at most {} elements".format(self._max_length),
                                  value)
        if self._item_validator is None:
            return value
        return value.__class__(self._iter_validated_items(value))

    def _iter_validated_items(self, value):
        validate_item = self._item_validator.validate
        for i, item in enumerate(value):
            try:
                yield validate_item(item)
            except ValidationError as ex:
                raise ex.add_error_path_item(i)


def homogeneous_sequence_factory(obj):
    """
    Parse an empty or 1-element ``[schema]`` list as a :py:class:`HomogeneousSequence` validator.
    """
    if isinstance(obj, list) and len(obj) <= 1:
        return HomogeneousSequence(*obj)


class HeterogeneousSequence(Type):
    """A validator that accepts heterogeneous, fixed size sequences."""

    accept_types = collections.Sequence
    reject_types = string_types

    def __init__(self, *item_schemas):
        """Instantiate a :py:class:`HeterogeneousSequence` validator.

        :param item_schemas: The schema of each element of the the tuple.
        """
        super(HeterogeneousSequence, self).__init__()
        self._item_schemas = item_schemas
        self._item_validators = []

    def parse(self):
        if hasattr(self, '_item_schemas'):
            self._item_validators = list(imap(self.val_context.parse, self._item_schemas))
            del self._item_schemas

    def validate(self, value):
        super(HeterogeneousSequence, self).validate(value)
        if len(value) != len(self._item_validators):
            raise ValidationError(self.val_context,
                                  "{} items expected, {} found".format(len(self._item_validators), len(value)),
                                  value)
        return value.__class__(self._iter_validated_items(value))

    def _iter_validated_items(self, value):
        for i, (validator, item) in enumerate(izip(self._item_validators, value)):
            try:
                yield validator.validate(item)
            except ValidationError as ex:
                raise ex.add_error_path_item(i)


def heterogeneous_sequence_factory(obj):
    """
    Parse a  ``(schema1, ..., schemaN)`` tuple as a :py:class:`HeterogeneousSequence`
    validator.
    """
    if isinstance(obj, tuple):
        return HeterogeneousSequence(*obj)


class Mapping(Type):
    """A validator that accepts mappings (:py:class:`collections.Mapping` instances)."""

    accept_types = collections.Mapping

    def __init__(self, key_schema=None, value_schema=None):
        """Instantiate a :py:class:`Mapping` validator.

        :param key_schema: If not None, the schema of the dict keys.
        :param value_schema: If not None, the schema of the dict values.
        """
        super(Mapping, self).__init__()
        self._key_schema = key_schema
        self._value_schema = value_schema
        self._key_validator = None
        self._value_validator = None

    def parse(self):
        if hasattr(self, '_key_schema'):
            if self._key_schema is not None:
                self._key_validator = self.val_context.parse(self._key_schema)
            if self._value_schema is not None:
                self._value_validator = self.val_context.parse(self._value_schema)
            del self._key_schema
            del self._value_schema

    def validate(self, value):
        super(Mapping, self).validate(value)
        return value.__class__(self._iter_validated_items(value))

    def _iter_validated_items(self, value):
        validate_key = validate_value = None
        if self._key_validator is not None:
            validate_key = self._key_validator.validate
        if self._value_validator is not None:
            validate_value = self._value_validator.validate
        for k, v in iteritems(value):
            if validate_value is not None:
                try:
                    v = validate_value(v)
                except ValidationError as ex:
                    raise ex.add_error_path_item(k)
            if validate_key is not None:
                k = validate_key(k)
            yield (k, v)


class Optional(object):
    """
    Marks object property as optional.

    If ``default`` specified, sets the property value to default, when property missing.
    ``default`` can also be a zero-argument callable, in which case property value is set to ``default()``.
    """

    def __init__(self, key, default=UNDEFINED):
        self.key = key
        self.default = default


REMOVE = object()


class Object(Type):
    """A validator that accepts json-like objects.

    A ``json-like object`` here is meant as a dict with a predefined set of
    "properties", i.e. string keys.
    """

    accept_types = collections.Mapping

    def __init__(self, properties=None, additional=True, ignore_optional_errors=False):
        """Instantiate an Object validator.

        :param properties: ``{name|Optional(name): schema}`` dict
        :param additional: The schema of all properties that are not explicitly
            defined as ``optional`` or ``required``. It can also be:

            - ``True`` to allow any value for additional properties.
            - ``False`` to disallow any additional properties.
            - :py:object:`REMOVE` to remove any additional properties from the
              adapted object.
        :param ignore_optional_errors: Determines if invalid optional properties
            are ignored:

            - ``True`` invalid optional properties are ignored.
            - ``False`` invalid optional properties raise ValidationError.
        """
        super(Object, self).__init__()
        self._all = []
        self._optional_defaults = {}
        self._required_keys = set()
        if properties is None:
            properties = {}
        for p, schema in iteritems(properties):
            if isinstance(p, Optional):
                if p.default is not UNDEFINED:
                    self._optional_defaults[p.key] = p.default
                self._all.append((p.key, schema))
            else:
                self._required_keys.add(p)
                self._all.append((p, schema))
        self._all_keys = [p for p, _ in self._all]
        self._additional = additional
        self._ignore_optional_errors = ignore_optional_errors
        self._named_validators = None

    def parse(self):
        if hasattr(self, '_all'):
            if not isinstance(self._additional, bool) and self._additional is not REMOVE:
                self._additional = self.val_context.parse(self._additional)
            self._named_validators = [
                (name, self.val_context.parse(schema))
                for name, schema in self._all
            ]
            del self._all

    def validate(self, value):
        super(Object, self).validate(value)
        missing_required = self._required_keys.difference(value)
        if missing_required:
            missing_required = list(imap(self.val_context.repr, missing_required))
            raise ValidationError(self.val_context,
                                  "missing required properties: [{}]".format(", ".join(missing_required)),
                                  value)

        result = value.copy()
        for name, validator in self._named_validators:
            if name in value:
                try:
                    adapted = validator.validate(value[name])
                    result[name] = adapted
                except ValidationError as ex:
                    if (not self._ignore_optional_errors
                            or name in self._required_keys):
                        raise ex.add_error_path_item(name)
                    else:
                        del result[name]
            elif name in self._optional_defaults:
                default = self._optional_defaults[name]
                result[name] = default if not callable(default) else default()

        if self._additional is not True:
            all_keys = self._all_keys
            additional_properties = [k for k in value if k not in all_keys]
            if additional_properties:
                if self._additional is False:
                    raise ValidationError(
                        self.val_context,
                        "unexpected properties: {}".format(self.val_context.repr(additional_properties)),
                        value)
                elif self._additional is REMOVE:
                    for name in additional_properties:
                        del result[name]
                else:
                    additional_validate = self._additional.validate
                    for name in additional_properties:
                        try:
                            adapted = additional_validate(value[name])
                            result[name] = adapted
                        except ValidationError as ex:
                            raise ex.add_error_path_item(name)

        return result


class ObjectFactory(object):
    def __init__(self, additional_properties=True, ignore_optional_property_errors=False):
        """
        :param additional_properties: Specifies for this parse call the schema of
            all :py:class:`~valideero.validators.Object` properties that are not
            explicitly defined in schema. It can also be:

            - ``True`` to allow any value for additional properties.
            - ``False`` to disallow any additional properties.
            - :py:object:`REMOVE` to remove any additional
              properties from the adapted object.

        :param ignore_optional_property_errors: Determines if invalid optional
            properties are ignored:

            - ``True`` to ignore invalid optional properties.
            - ``False`` to raise ValidationError for invalid optional properties.
        """
        self.additional_properties = additional_properties
        self.ignore_optional_property_errors = ignore_optional_property_errors

    def __call__(self, obj):
        """
        Parse a python ``{name: schema}`` dict as an :py:class:`Object` instance.
        """
        if isinstance(obj, dict):
            return Object(obj, self.additional_properties, self.ignore_optional_property_errors)


def make_default_validation_context():
    type_names = TypeNames()
    named_validators = {
        'boolean': Boolean,
        'string': String,
        'time': Time,
        'date': Date,
        'integer': Integer,
        'number': Number,
        'datetime': Datetime
    }
    default_validators_factories = {
        'HomogeneousSequence': homogeneous_sequence_factory,
        'Object': ObjectFactory(),
        'HeterogeneousSequence': heterogeneous_sequence_factory,
        'Type': type_factory,
        'Pattern': pattern_factory,
        'Condition': condition_factory,
    }
    return ValidationContext(type_names, named_validators, default_validators_factories, compatible_repr)
