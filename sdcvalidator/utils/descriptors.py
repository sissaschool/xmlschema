#
# Copyright (c), 2016-2025, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from collections.abc import Callable
from threading import Lock
from typing import cast, Generic, Optional, overload, TypeVar, TYPE_CHECKING, Union

from sdcvalidator.exceptions import XMLSchemaAttributeError, XMLSchemaTypeError

if TYPE_CHECKING:
    from sdcvalidator.core.xsdbase import XsdValidator  # noqa


VT = TypeVar('VT', bound='XsdValidator')
RT = TypeVar('RT')


# noinspection PyPep8Naming
class validator_property(Generic[VT, RT]):
    """
    A property that caches the value only if the XSD validator is built.
    TODO: unused, keep it as a temporary substitution for *cached_property* for Python < 3.12
      in case of reported problems with multi-thread contention.
    """

    __slots__ = ('func', 'lock', '_name', '__dict__')

    def __init__(self, func: Callable[[VT], RT]) -> None:
        self.func = func
        self.lock = Lock()
        self.__doc__ = func.__doc__
        if hasattr(func, '__module__'):
            self.__module__ = func.__module__

    def __set_name__(self, owner: type[VT], name: str) -> None:
        if not hasattr(owner, 'built'):
            raise XMLSchemaTypeError("{!r} is not an XSD validator".format(owner))
        if name == 'built':
            raise XMLSchemaAttributeError("can't apply to 'built' property")
        self._name = name

    @overload
    def __get__(self, instance: None, owner: type[VT]) -> 'validator_property[VT, RT]': ...

    @overload
    def __get__(self, instance: VT, owner: type[VT]) -> RT: ...

    def __get__(self, instance: Optional[VT], owner: type[VT]) \
            -> Union['validator_property[VT, RT]', RT]:
        if instance is None:
            return self

        if not instance.built:
            # Can't cache the property if the validator is not built
            if self._name in instance.__dict__:
                instance.__dict__.pop(self._name)
            return self.func(instance)
        elif self._name not in instance.__dict__:
            with self.lock:
                if self._name not in instance.__dict__:
                    instance.__dict__[self._name] = self.func(instance)

        return cast(RT, instance.__dict__[self._name])
