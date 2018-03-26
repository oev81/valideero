# -*- coding: utf-8 -*-
import sys

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3

if PY2:  # pragma: no cover
    text_type = unicode
    binary_type = str
    string_types = basestring
    int_types = (int, long)
    import itertools

    izip = itertools.izip
    imap = itertools.imap
    long = long
    xrange = xrange

    import repr as reprlib


    def iteritems(d, **kw):
        return iter(d.iteritems(**kw))


    class CompatRepr(reprlib.Repr):
        def repr(self, x):
            return reprlib.Repr.repr(self, x).decode('utf8')

        def repr_unicode(self, x, level):
            s = x.encode('utf8')
            return reprlib.Repr.repr_str(self, s, level)


    import __builtin__ as builtins

else:  # pragma: no cover
    text_type = str
    binary_type = bytes
    string_types = str
    int_types = (int,)
    izip = zip
    imap = map
    long = int


    def iteritems(d, **kw):
        return iter(d.items(**kw))


    xrange = range

    import reprlib


    class CompatRepr(reprlib.Repr):
        def repr_bytes(self, x, level):
            s = x.decode('utf8')
            return reprlib.Repr.repr_str(self, s, level)


    import builtins

compatible_repr = CompatRepr().repr


class JsonReprBase(reprlib.Repr):
    def repr_str(self, x, level):
        s = '"{}"'.format(x)
        if len(s) > self.maxstring:
            i = max(0, (self.maxstring - 3) // 2)
            j = max(0, self.maxstring - 3 - i)
            s = builtins.repr(x[:i] + x[len(x) - j:])
            s = s[:i] + b'...' + s[len(s) - j:]
        return s

    def repr_bool(self, x, level):
        return 'true' if x else 'false'

    def repr_NoneType(self, x, level):
        return 'null'


if PY2:
    class JsonRepr(JsonReprBase):
        def repr(self, x):
            return JsonReprBase.repr(self, x).decode('utf8')

        def repr_unicode(self, x, level):
            x = x.encode('utf8')
            return JsonReprBase.repr_str(self, x, level)
else:
    class JsonRepr(JsonReprBase):
        def repr_bytes(self, x, level):
            x = x.decode('utf8')
            return JsonReprBase.repr_str(self, x, level)

json_repr = JsonRepr().repr


def python_2_unicode_compatible(cls):
    """
    The implementation comes from django.utils.encoding.

    """
    if PY2:
        if '__str__' not in cls.__dict__:
            raise ValueError("@python_2_unicode_compatible cannot be applied "
                             "to %s because it doesn't define __str__()." %
                             cls.__name__)
        cls.__unicode__ = cls.__str__
        cls.__str__ = lambda self: self.__unicode__().encode('utf-8')
    return cls


def unicode_safe(x):
    if isinstance(x, binary_type):
        return x.decode('utf8')
    else:
        return x
