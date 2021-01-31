#
# Copyright (c), 2016-2021, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import os
import re
import sys
import inspect
import logging
from abc import ABC, ABCMeta
from fnmatch import fnmatch
from pathlib import Path
from jinja2 import Environment, ChoiceLoader, FileSystemLoader, \
    TemplateNotFound, TemplateAssertionError

import xmlschema
from xmlschema.validators import XsdType, XsdElement, XsdAttribute
from xmlschema.names import XSD_NAMESPACE


NAME_PATTERN = re.compile(r'^(?:[^\d\W]|:)[\w.\-:]*$')
NCNAME_PATTERN = re.compile(r'^[^\d\W][\w.\-]*$')
QNAME_PATTERN = re.compile(
    r'^(?:(?P<prefix>[^\d\W][\w\-.\xb7\u0387\u06DD\u06DE]*):)?'
    r'(?P<local>[^\d\W][\w\-.\xb7\u0387\u06DD\u06DE]*)$',
)


def is_shell_wildcard(name):
    return '*' in name or '?' in name or '[' in name


def xsd_qname(name):
    return '{%s}%s' % (XSD_NAMESPACE, name)


def filter_method(func):
    """Marks a method for registration as template filter."""
    func.is_filter = True
    return func


def test_method(func):
    """Marks a method for registration as template test."""
    func.is_test = True
    return func


logger = logging.getLogger('xsdtools')
logging_formatter = logging.Formatter('[%(levelname)s] %(message)s')
logging_handler = logging.StreamHandler(sys.stderr)
logging_handler.setFormatter(logging_formatter)
logger.addHandler(logging_handler)


class GeneratorMeta(ABCMeta):
    """Metaclass for creating code generators."""

    def __new__(mcs, name, bases, attrs):
        module = attrs['__module__']
        try:
            module_path = sys.modules[module].__file__
        except AttributeError:
            module_path = os.getcwd()

        formal_language = None
        default_paths = []
        default_filters = {}
        default_tests = {}
        builtin_types = {}
        for base in bases:
            if getattr(base, 'formal_language', None):
                if formal_language is None:
                    formal_language = base.formal_language
                elif formal_language != base.formal_language:
                    msg = "Ambiguous formal_language from {!r} base classes"
                    raise ValueError(msg.format(name))

            if getattr(base, 'default_paths', None):
                default_paths.extend(base.default_paths)
            if hasattr(base, 'default_filters'):
                default_filters.update(base.default_filters)
            if hasattr(base, 'default_tests'):
                default_tests.update(base.default_tests)
            if getattr(base, 'builtin_types', None):
                builtin_types.update(base.builtin_types)

        if 'formal_language' not in attrs:
            attrs['formal_language'] = formal_language
        elif formal_language:
            msg = "formal_language can be defined only once for each generator class hierarchy"
            raise ValueError(msg)

        try:
            for path in attrs['default_paths']:
                if Path(path).is_absolute():
                    dirpath = Path(path)
                else:
                    dirpath = Path(module_path).parent.joinpath(path)

                if not dirpath.is_dir():
                    raise ValueError("Path {!r} is not a directory!".format(str(path)))
                default_paths.append(dirpath)

        except (KeyError, TypeError):
            pass
        else:
            attrs['default_paths'] = default_paths

        for k, v in attrs.items():
            if inspect.isfunction(v):
                if getattr(v, 'is_filter', False):
                    default_filters[k] = v
                elif getattr(v, 'is_test', False):
                    default_tests[k] = v
            elif inspect.isroutine(v):
                # static and class methods
                if getattr(v.__func__, 'is_filter', False):
                    default_filters[k] = v
                elif getattr(v.__func__, 'is_test', False):
                    default_tests[k] = v

        attrs['default_filters'] = default_filters
        attrs['default_tests'] = default_tests

        try:
            for k, v in attrs['builtin_types'].items():
                builtin_types[xsd_qname(k)] = v
        except (KeyError, AttributeError):
            pass
        finally:
            if not builtin_types and not name.startswith('Abstract'):
                raise ValueError("Empty builtin_types for {}".format(name))
            attrs['builtin_types'] = builtin_types

        return type.__new__(mcs, name, bases, attrs)


class AbstractGenerator(ABC, metaclass=GeneratorMeta):
    """
    Abstract base class for code generators. A generator works using the
    Jinja2 template engine by an Environment instance.

    :param schema: the XSD schema instance.
    :param searchpath: additional search path for custom templates.
    :param filters: additional custom filter functions.
    :param tests: additional custom tests functions.
    :param types_map: a dictionary with custom mapping for XSD types.
    """
    formal_language = None
    """The formal language associated to the code generator."""

    default_paths = None
    """Default paths for templates."""

    default_filters = None
    """Default filter functions."""

    default_tests = None
    """Default test functions."""

    builtin_types = {
        'anyType': '',
        'anySimpleType': '',
    }
    """Translation map for XSD builtin types."""

    def __init__(self, schema, searchpath=None, filters=None, tests=None, types_map=None):
        if isinstance(schema, xmlschema.XMLSchemaBase):
            self.schema = schema
        else:
            self.schema = xmlschema.XMLSchema(schema)

        self.searchpath = searchpath
        file_loaders = []
        if searchpath is not None:
            file_loaders.append(FileSystemLoader(searchpath))
        if isinstance(self.default_paths, list):
            file_loaders.extend(
                FileSystemLoader(str(path)) for path in reversed(self.default_paths)
            )

        if not file_loaders:
            raise ValueError("At least one search path required for generator instance!")
        loader = ChoiceLoader(file_loaders) if len(file_loaders) > 1 else file_loaders[0]

        self.filters = dict(self.default_filters)
        for name, func in self.default_filters.items():
            if isinstance(func, (staticmethod, classmethod)) or \
                    func.__name__ != func.__qualname__:
                # Replace unbound method with instance bound one
                self.filters[name] = getattr(self, name)
            else:
                self.filters[name] = func
        if filters:
            self.filters.update(filters)

        self.tests = dict(self.default_tests)
        for name, func in self.default_tests.items():
            if isinstance(func, (staticmethod, classmethod)) or \
                    func.__name__ != func.__qualname__:
                # Replace unbound method with instance bound one
                self.tests[name] = getattr(self, name)
            else:
                self.tests[name] = func
        if tests:
            self.tests.update(tests)

        type_mapping_filter = '{}_type'.format(self.formal_language).lower().replace(' ', '_')
        if type_mapping_filter not in self.filters:
            self.filters[type_mapping_filter] = self.map_type

        self.types_map = self.builtin_types.copy()
        if types_map:
            if not self.schema.target_namespace:
                self.types_map.update(types_map)
            else:
                ns_part = '{%s}' % self.schema.target_namespace
                self.types_map.update((ns_part + k, v) for k, v in types_map.items())

        self._env = Environment(loader=loader)
        self._env.filters.update(self.filters)
        self._env.tests.update(self.tests)

    def __repr__(self):
        return '%s(xsd_file=%r, searchpath=%r)' % (
            self.__class__.__name__, self.xsd_file, self.searchpath
        )

    @classmethod
    def register_filter(cls, func):
        """Registers a function as default filter for the code generator."""
        cls.default_filters[func.__name__] = func
        func.is_filter = True
        return func

    @classmethod
    def register_test(cls, func):
        """Registers a function as default test for the code generator."""
        cls.default_tests[func.__name__] = func
        func.is_test = True
        return func

    @property
    def xsd_file(self):
        url = self.schema.url
        return os.path.basename(url) if url else None

    def list_templates(self, extensions=None, filter_func=None):
        return self._env.list_templates(extensions, filter_func)

    def matching_templates(self, name):
        return self._env.list_templates(filter_func=lambda x: fnmatch(x, name))

    def get_template(self, name, parent=None, global_vars=None):
        return self._env.get_template(name, parent, global_vars)

    def select_template(self, names, parent=None, global_vars=None):
        return self._env.select_template(names, parent, global_vars)

    def render(self, names, parent=None, global_vars=None):
        if isinstance(names, str):
            names = [names]
        elif not all(isinstance(x, str) for x in names):
            raise TypeError("'names' argument must contain only strings!")

        results = []
        for name in names:
            try:
                template = self._env.get_template(name, parent, global_vars)
            except TemplateNotFound as err:
                logger.debug("name %r: %s", name, str(err))
            except TemplateAssertionError as err:
                logger.warning("template %r: %s", name, str(err))
            else:
                results.append(template.render(schema=self.schema))
        return results

    def render_to_files(self, names, parent=None, global_vars=None, output_dir='.', force=False):
        if isinstance(names, str):
            names = [names]
        elif not all(isinstance(x, str) for x in names):
            raise TypeError("'names' argument must contain only strings!")

        template_names = []
        for name in names:
            if is_shell_wildcard(name):
                template_names.extend(self.matching_templates(name))
            else:
                template_names.append(name)

        output_dir = Path(output_dir)
        rendered = []

        for name in template_names:
            try:
                template = self._env.get_template(name, parent, global_vars)
            except TemplateNotFound as err:
                logger.debug("name %r: %s", name, str(err))
            except TemplateAssertionError as err:
                logger.warning("template %r: %s", name, str(err))
            else:
                output_file = output_dir.joinpath(Path(name).name).with_suffix('')
                if not force and output_file.exists():
                    continue

                result = template.render(schema=self.schema)
                logger.info("write file %r", str(output_file))
                with open(output_file, 'w') as fp:
                    fp.write(result)
                rendered.append(template.filename)

        return rendered

    def map_type(self, obj):
        """
        Maps an XSD type to a type declaration of the target language.
        This method is registered as filter with a name dependant from
        the language name (eg. c_type).

        :param obj: an XSD type or another type-related declaration as \
        an attribute or an element.
        :return: an empty string for non-XSD objects.
        """
        if isinstance(obj, XsdType):
            xsd_type = obj
        elif isinstance(obj, (XsdAttribute, XsdElement)):
            xsd_type = obj.type
        else:
            return ''

        try:
            return self.types_map[xsd_type.name]
        except KeyError:
            try:
                return self.types_map[xsd_type.base_type.name]
            except (KeyError, AttributeError):
                if xsd_type.is_complex():
                    return self.types_map[xsd_qname('anyType')]
                else:
                    return self.types_map[xsd_qname('anySimpleType')]

    @staticmethod
    @filter_method
    def name(obj, unnamed='none'):
        """
        Get the unqualified name of the provided object. Invalid
        chars for identifiers are replaced by an underscore.

        :param obj: an XSD object or a named object or a string.
        :param unnamed: value for unnamed objects. Defaults to 'none'.
        :return: str
        """
        try:
            name = obj.local_name
        except AttributeError:
            try:
                obj = obj.name
            except AttributeError:
                pass

            if not isinstance(obj, str):
                return unnamed

            try:
                if obj[0] == '{':
                    _, name = obj.split('}')
                elif ':' in obj:
                    prefix, name = obj.split(':')
                    if NCNAME_PATTERN.match(prefix) is None:
                        return ''
                else:
                    name = obj
            except (IndexError, ValueError):
                return ''
        else:
            if not isinstance(name, str):
                return ''

        if NCNAME_PATTERN.match(name) is None:
            return unnamed
        return name.replace('.', '_').replace('-', '_')

    @filter_method
    def qname(self, obj, unnamed='none', sep='__'):
        """
        Get the QName of the provided object. Invalid chars for
        identifiers are replaced by an underscore.

        :param obj: an XSD object or a named object or a string.
        :param unnamed: value for unnamed objects. Defaults to 'none'.
        :param sep: the replacement for colon. Defaults to double underscore.
        :return: str
        """
        try:
            qname = obj.prefixed_name
        except AttributeError:
            try:
                obj = obj.name
            except AttributeError:
                pass

            if not isinstance(obj, str):
                return unnamed

            try:
                if obj[0] == '{':
                    namespace, local_name = obj.split('}')
                    for prefix, uri in self.schema.namespaces.items():
                        if uri == namespace:
                            qname = '%s:%s' % (uri, local_name)
                            break
                    else:
                        qname = local_name
                else:
                    qname = obj
            except (IndexError, ValueError):
                return unnamed

        if not qname or QNAME_PATTERN.match(qname) is None:
            return unnamed
        return qname.replace('.', '_').replace('-', '_').replace(':', sep)

    @staticmethod
    @filter_method
    def namespace(obj):
        try:
            namespace = obj.target_namespace
        except AttributeError:
            try:
                obj = obj.name
            except AttributeError:
                pass

            try:
                if not isinstance(obj, str) or obj[0] != '{':
                    return ''
                namespace, _ = obj.split('}')
            except (IndexError, ValueError):
                return ''
        else:
            if not isinstance(namespace, str):
                return ''
        return namespace

    @staticmethod
    @filter_method
    def type_name(obj, suffix=None, unnamed='none'):
        """
        Get the unqualified name of the XSD type. Invalid
        chars for identifiers are replaced by an underscore.

        :param obj: an instance of (XsdType|XsdAttribute|XsdElement).
        :param suffix: force a suffix. For default removes '_type' or 'Type' suffixes.
        :param unnamed: value for unnamed XSD types. Defaults to 'none'.
        :return: str
        """
        if isinstance(obj, XsdType):
            name = obj.local_name or unnamed
        elif isinstance(obj, (XsdElement, XsdAttribute)):
            name = obj.type.local_name or unnamed
        else:
            name = unnamed

        if not name or NCNAME_PATTERN.match(name) is None:
            name = unnamed

        if name.endswith('Type'):
            name = name[:-4]
        elif name.endswith('_type'):
            name = name[:-5]

        if suffix:
            name = '{}{}'.format(name, suffix)

        return name.replace('.', '_').replace('-', '_')

    @staticmethod
    @filter_method
    def type_qname(obj, suffix=None, unnamed='none', sep='__'):
        """
        Get the unqualified name of the XSD type. Invalid
        chars for identifiers are replaced by an underscore.

        :param obj: an instance of (XsdType|XsdAttribute|XsdElement).
        :param suffix: force a suffix. For default removes '_type' or 'Type' suffixes.
        :param unnamed: value for unnamed XSD types. Defaults to 'none'.
        :param sep: the replacement for colon. Defaults to double underscore.
        :return: str
        """
        if isinstance(obj, XsdType):
            qname = obj.prefixed_name or unnamed
        elif isinstance(obj, (XsdElement, XsdAttribute)):
            qname = obj.type.prefixed_name or unnamed
        else:
            qname = unnamed

        if not qname or QNAME_PATTERN.match(qname) is None:
            qname = unnamed

        if qname.endswith('Type'):
            qname = qname[:-4]
        elif qname.endswith('_type'):
            qname = qname[:-5]

        if suffix:
            qname = '{}{}'.format(qname, suffix)

        return qname.replace('.', '_').replace('-', '_').replace(':', sep)

    @staticmethod
    @filter_method
    def sort_types(xsd_types, accept_circularity=False):
        """
        Returns a sorted sequence of XSD types. Sorted types can be used to build code declarations.

        :param xsd_types: a sequence with XSD types.
        :param accept_circularity: if set to `True` circularities are accepted. Defaults to `False`.
        :return: a list with ordered types.
        """
        if not isinstance(xsd_types, (list, tuple)):
            try:
                xsd_types = list(xsd_types.values())
            except AttributeError:
                pass

        assert all(isinstance(x, XsdType) for x in xsd_types)
        ordered_types = [x for x in xsd_types if x.is_simple()]
        ordered_types.extend(x for x in xsd_types if x.is_complex() and x.has_simple_content())
        unordered = {x: [] for x in xsd_types if x.is_complex() and not x.has_simple_content()}

        for xsd_type in unordered:
            for e in xsd_type.content_type.iter_elements():
                if e.type in unordered:
                    unordered[xsd_type].append(e.type)

        while unordered:
            deleted = 0
            for xsd_type in xsd_types:
                if xsd_type in unordered:
                    if not unordered[xsd_type]:
                        del unordered[xsd_type]
                        ordered_types.append(xsd_type)
                        deleted += 1

            for xsd_type in unordered:
                unordered[xsd_type] = [x for x in unordered[xsd_type] if x in unordered]

            if not deleted:
                if not accept_circularity:
                    raise ValueError("Circularity found between {!r}".format(list(unordered)))
                ordered_types.extend(list(unordered))
                break

        assert len(xsd_types) == len(ordered_types)
        return ordered_types

    def is_derived(self, xsd_type, *names, derivation=None):
        for type_name in names:
            if not isinstance(type_name, str) or not type_name:
                continue
            elif type_name[0] == '{':
                if xsd_type.is_derived(self.schema.maps.types[type_name], derivation):
                    return True
            elif ':' in type_name:
                try:
                    other = self.schema.resolve_qname(type_name)
                except xmlschema.XMLSchemaException:
                    continue
                else:
                    if xsd_type.is_derived(other, derivation):
                        return True
            else:
                if xsd_type.is_derived(self.schema.types[type_name], derivation):
                    return True

        return False

    @test_method
    def derivation(self, xsd_type, *names):
        return self.is_derived(xsd_type, *names)

    @test_method
    def extension(self, xsd_type, *names):
        return self.is_derived(xsd_type, *names, derivation='extension')

    @test_method
    def restriction(self, xsd_type, *names):
        return self.is_derived(xsd_type, *names, derivation='restriction')

    @staticmethod
    @test_method
    def multi_sequence(xsd_type):
        if xsd_type.has_simple_content():
            return False
        return any(e.is_multiple() for e in xsd_type.content_type.iter_elements())


class PythonGenerator(AbstractGenerator):
    """
    Python code generic generator for XSD schemas.
    """
    formal_language = 'Python'

    default_paths = ['templates/python/']

    builtin_types = {
        'string': 'str',
        'boolean': 'bool',
        'float': 'float',
        'double': 'float',
        'integer': 'int',
        'unsignedByte': 'int',
        'nonNegativeInteger': 'int',
        'positiveInteger': 'int',
    }
