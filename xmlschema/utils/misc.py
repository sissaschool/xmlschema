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
from typing import Callable, Any, TypeVar

RT = TypeVar('RT')


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
