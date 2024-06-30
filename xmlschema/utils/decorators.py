#
# Copyright (c), 2016-2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import warnings
from functools import wraps
from typing import Callable, cast, Any, TypeVar

from xmlschema.exceptions import XMLSchemaException, XMLSchemaValueError, \
    XMLSchemaTypeError, XMLSchemaAttributeError, XMLSchemaKeyError, \
    XMLSchemaRuntimeError
from xmlschema.resources.exceptions import XMLResourceError, XMLResourceOSError, \
    XMLResourceValueError, XMLResourceTypeError, XMLResourceAttributeError


FT = TypeVar('FT', bound=Callable[..., Any])
RT = TypeVar('RT')


def catchable_xmlschema_error(func: FT) -> FT:
    """Force a function to raise only an XMLSchemaException or a subclass of it."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except XMLSchemaException:
            raise
        except ValueError as err:
            raise XMLSchemaValueError(err)
        except TypeError as err:
            raise XMLSchemaTypeError(err)
        except AttributeError as err:
            raise XMLSchemaAttributeError(err)
        except KeyError as err:
            raise XMLSchemaKeyError(err)
        except RuntimeError as err:
            raise XMLSchemaRuntimeError(err)

    return cast(FT, wrapper)


def catchable_resource_error(func: FT) -> FT:
    """Force a function to raise only an XMLResourceError or a subclass of it."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except XMLResourceError:
            raise
        except XMLSchemaException as err:
            if not isinstance(err, XMLSchemaValueError):
                raise
            raise XMLResourceValueError(err)
        except ValueError as err:
            raise XMLResourceValueError(err)
        except TypeError as err:
            raise XMLResourceTypeError(err)
        except AttributeError as err:
            raise XMLResourceAttributeError(err)
        except OSError as err:
            raise XMLResourceOSError(err)

    return cast(FT, wrapper)


def deprecated(version: str, stacklevel: int = 1, alt: str = '') \
        -> Callable[[Callable[[Any], RT]],  Callable[[Any], RT]]:

    def decorator(func: Callable[[Any], RT]) -> Callable[[Any], RT]:
        msg = f"{func!r} will be removed in v{version}."
        if alt:
            msg = f"{msg[:-1]}, {alt}."

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> RT:
            warnings.warn(msg, DeprecationWarning, stacklevel=stacklevel + 1)
            return func(*args, **kwargs)
        return wrapper

    return decorator


def will_change(version: str, stacklevel: int = 1, alt: str = '') \
        -> Callable[[Callable[[Any], RT]],  Callable[[Any], RT]]:

    def decorator(func: Callable[[Any], RT]) -> Callable[[Any], RT]:
        msg = f"{func!r} will change from v{version}."
        if alt:
            msg = f"{msg[:-1]}, {alt}."

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> RT:
            warnings.warn(msg, FutureWarning, stacklevel=stacklevel + 1)
            return func(*args, **kwargs)
        return wrapper

    return decorator
