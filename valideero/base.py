# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import inspect

from .compat import iteritems, python_2_unicode_compatible, compatible_repr, unicode_safe, imap, string_types, xrange

__all__ = ["ValidationError", "SchemaError", "Validator", "ValidationContext", "UNDEFINED", "TypeNames"]


@python_2_unicode_compatible
class SchemaError(Exception):
    """An object cannot be parsed as a validator."""

    def __init__(self, msg):
        self._msg = msg

    def __str__(self):
        return self._msg

    @property
    def message(self):
        return self.__str__()


@python_2_unicode_compatible
class ValidatorTypeError(TypeError):
    def __init__(self, msg):
        self._msg = msg

    def __str__(self):
        return self._msg

    @property
    def message(self):
        return self.__str__()


UNDEFINED = object()


@python_2_unicode_compatible
class ValidationError(ValueError):
    """A value is invalid for a given validator."""

    def __init__(self, val_context, msg, value=UNDEFINED):
        self.val_context = val_context
        self.msg = unicode_safe(msg)
        self.value = value
        self.error_path_items = []
        super(ValidationError, self).__init__()

    def to_text(self):
        if self.value is not UNDEFINED:
            value = self.val_context.repr(self.value)
            type_name = self.val_context.type_names.get_type_name(self.value.__class__)
            message = "Invalid value {} ({}): {}".format(value, type_name, self.msg)
        else:
            message = self.msg
        if len(self.error_path_items) > 0:
            path_items = [item for item in reversed(self.error_path_items)]
            if not isinstance(path_items[0], string_types):
                path_items.insert(0, "value")
            else:
                path_items[0] = unicode_safe(path_items[0])
            for n in xrange(1, len(path_items)):
                path_items[n] = "[{}]".format(self.val_context.repr(path_items[n]))
            message += " (at {})".format("".join(path_items))
        return message

    def __str__(self):
        return self.to_text()

    @property
    def message(self):
        return self.__str__()

    @property
    def args(self):
        return (self.__str__(), )

    def add_error_path_item(self, context):
        self.error_path_items.append(context)
        return self


class TypeNames(object):
    def __init__(self):
        self._type_names = {}

    def set_name_for_types(self, name, *types):
        """
        Associate one or more types with an alternative human-friendly name.
        """
        for _type in types:
            self._type_names[_type] = name

    def get_type_name(self, type):
        return unicode_safe(self._type_names.get(type) or type.__name__)

    def format_types(self, types):
        if inspect.isclass(types):
            types = (types,)
        names = list(imap(self.get_type_name, types))
        s = names[-1]
        if len(names) > 1:
            s = "{} or {}".format(", ".join(names[:-1]), s)
        return s


class ValidationContext(object):
    def __init__(self, type_names, named_validators, validators_factories, repr_method):
        self.type_names = type_names
        self.named_validators = named_validators
        self.validators_factories = validators_factories
        self.repr = repr_method

    def register(self, name, validator):
        if not isinstance(validator, Validator):
            raise ValidatorTypeError("Validator instance expected, {} given".format(unicode_safe(validator.__class__)))
        self.named_validators[name] = validator

    def _get_validator(self, obj):
        validator = None
        try:
            validator = self.named_validators[obj]
        except (KeyError, TypeError):
            for _, factory in iteritems(self.validators_factories):
                validator = factory(obj)
                if validator is not None:
                    break
        else:
            if inspect.isclass(validator) and issubclass(validator, Validator):
                self.named_validators[obj] = validator = validator()
        return validator

    def parse(self, obj):
        """Try to parse the given ``obj`` as a validator instance.

        :param obj: The object to be parsed. If it is a...:

            - :py:class:`Validator` instance, return it.
            - :py:class:`Validator` subclass, instantiate it without arguments and
              return it.
            - :py:attr:`~Validator.name` of a known :py:class:`Validator` subclass,
              instantiate the subclass without arguments and return it.
            - otherwise find the first registered :py:class:`Validator` factory that
              can create it. The search order is the reverse of the factory registration
              order. The caller is responsible for ensuring there are no ambiguous
              values that can be parsed by more than one factory.

        :raises SchemaError: If no appropriate validator could be found.

        .. warning:: Passing ``required_properties`` and/or ``additional_properties``
            with value other than ``None`` may be non intuitive for schemas that
            involve nested validators. Take for example the following schema::

                v = V.parse({
                    "x": "integer",
                    "child": V.Nullable({
                        "y": "integer"
                    })
                }, required_properties=True)

            Here the top-level properties 'x' and 'child' are required but the nested
            'y' property is not. This is because by the time :py:meth:`parse` is called,
            :py:class:`~valideero.validators.Nullable` has already parsed its argument
            with the default value of ``required_properties``. Several other builtin
            validators work similarly to :py:class:`~valideero.validators.Nullable`,
            accepting one or more schemas to parse. In order to parse an arbitrarily
            complex nested validator with the same value for ``required_properties``
            and/or ``additional_properties``, use the :py:func:`parsing` context
            manager instead::

                with V.parsing(required_properties=True):
                    v = V.parse({
                        "x": "integer",
                        "child": V.Nullable({
                            "y": "integer"
                        })
                    })
        """

        if isinstance(obj, Validator):
            validator = obj
        elif inspect.isclass(obj) and issubclass(obj, Validator):
            validator = obj()
        else:
            validator = self._get_validator(obj)

        if not isinstance(validator, Validator):
            raise SchemaError("{} cannot be parsed as a Validator".format(compatible_repr(obj)))

        validator.set_validation_context(self)
        validator.parse()

        return validator


class Validator(object):
    """Abstract base class of all validators.

    Concrete subclasses must implement :py:meth:`validate`. A subclass may optionally
    define a :py:attr:`name` attribute (typically a string) that can be used to specify
    a validator in :py:meth:`parse` instead of instantiating it explicitly.
    """

    name = None

    def __init__(self):
        self.val_context = None  # type: ValidationContext

    def set_validation_context(self, context):
        # set context only once
        # for cases when contexts are mixed
        if self.val_context is None:
            self.val_context = context

    def parse(self):
        pass

    def validate(self, value):
        """Check if ``value`` is valid and if so adapt it.

        :param value:
        :raises ValidationError: If ``value`` is invalid.
        :returns: The validated (and possibly adapted) value.
        """
        raise NotImplementedError

    def is_valid(self, value):
        """Check if the ``value`` is valid.

        :returns: ``True`` if the value is valid, ``False`` if invalid.
        """
        try:
            self.validate(value)
            return True
        except ValidationError:
            return False

    def error(self, value):
        """Helper method that can be called when ``value`` is deemed invalid.

        Can be overriden to provide customized :py:exc:`ValidationError` subclasses.
        """
        raise ValidationError(self.val_context,
                              "must be {}".format(self.humanized_name),
                              value)

    @property
    def humanized_name(self):
        """Return a human-friendly string name for this validator."""
        return unicode_safe(self.name or self.__class__.__name__)
