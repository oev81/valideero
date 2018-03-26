import inspect

from decorator import decorator


def accepts(validation_context, **schemas):
    """Create a decorator for validating function parameters.

    Example::

        @accepts(validation_context, a="number", body={"field_ids": [int], V.Optional("is_ok"): bool})
        def f(a, body):
            print (a, body["field_ids"], body.get("is_ok"))

    :param validation_context:
    :param schemas: The schema for validating a given parameter.
    """
    validate = validation_context.parse(schemas).validate

    @decorator
    def validating(func, *args, **kwargs):
        validate(inspect.getcallargs(func, *args, **kwargs))
        return func(*args, **kwargs)

    return validating


def returns(validation_context, schema):
    """Create a decorator for validating function return value.

    Example::
        @accepts(validation_context, a=int, b=int)
        @returns(validation_context, int)
        def f(a, b):
            return a + b

    :param validation_context:
    :param schema: The schema for adapting a given parameter.
    """
    validate = validation_context.parse(schema).validate

    @decorator
    def validating(func, *args, **kwargs):
        ret = func(*args, **kwargs)
        validate(ret)
        return ret

    return validating


def adapts(validation_context, **schemas):
    """Create a decorator for validating and adapting function parameters.

    Example::

        @adapts(validation_context, a="number", body={"field_ids": [V.AdaptTo(int)], V.Optional("is_ok"): bool})
        def f(a, body):
            print (a, body.field_ids, body.is_ok)

    :param validation_context:
    :param schemas: The schema for adapting a given parameter.
    """
    validate = validation_context.parse(schemas).validate

    @decorator
    def adapting(func, *args, **kwargs):
        adapted = validate(inspect.getcallargs(func, *args, **kwargs))
        argspec = inspect.getargspec(func)

        if argspec.varargs is argspec.keywords is None:
            # optimization for the common no varargs, no keywords case
            return func(**adapted)

        adapted_varargs = adapted.pop(argspec.varargs, ())
        adapted_keywords = adapted.pop(argspec.keywords, {})
        if not adapted_varargs:  # keywords only
            if adapted_keywords:
                adapted.update(adapted_keywords)
            return func(**adapted)

        adapted_posargs = [adapted[arg] for arg in argspec.args]
        adapted_posargs.extend(adapted_varargs)
        return func(*adapted_posargs, **adapted_keywords)

    return adapting
