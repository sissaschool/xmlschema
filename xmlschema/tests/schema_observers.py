# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2019, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
Observers for XMLSchema classes.
"""
from functools import wraps

from xmlschema.validators import XMLSchema10, XMLSchema11


class SchemaObserver(object):
    """
    Observer that registers created components. Run the 'clear' method after each usage.
    """
    components = []

    @classmethod
    def observed_builder(cls, builder):
        if isinstance(builder, type):
            class BuilderProxy(builder):
                def __init__(self, *args, **kwargs):
                    super(BuilderProxy, self).__init__(*args, **kwargs)
                    cls.components.append(self)
            BuilderProxy.__name__ = builder.__name__
            return BuilderProxy

        elif callable(builder):
            @wraps(builder)
            def builder_proxy(*args, **kwargs):
                result = builder(*args, **kwargs)
                cls.components.append(result)
                return result
            return builder_proxy

    @classmethod
    def clear(cls):
        del cls.components[:]


class ObservedXMLSchema10(XMLSchema10):
    BUILDERS = {
        k: SchemaObserver.observed_builder(getattr(XMLSchema10.BUILDERS, k))
        for k in getattr(XMLSchema10.BUILDERS, '_fields')
    }


class ObservedXMLSchema11(XMLSchema11):
    BUILDERS = {
        k: SchemaObserver.observed_builder(getattr(XMLSchema11.BUILDERS, k))
        for k in getattr(XMLSchema11.BUILDERS, '_fields')
    }
