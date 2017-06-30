# -*- coding: utf-8 -*-
#
# Copyright (c), 2016, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module contains base functions and classes XML Schema components.
"""
import re

from ..core import PY3, etree_tostring
from ..exceptions import XMLSchemaParseError
from ..qnames import *
from ..utils import camel_case_split, FrozenDict
from ..validator import XMLSchemaValidator


#
# Functions for parsing declarations from schema's tree
def check_tag(elem, *tags):
    if elem.tag not in tags:
        tags = (local_name(tag) for tag in tags)
        raise XMLSchemaParseError("({}) expected: {}".format('|'.join(tags), elem))


def get_xsd_annotation(elem):
    """
    Return the annotation of a node child that is
    :param elem: ElementTree's node
    :return: The first child element containing an XSD annotation,
    None if there are no annotation.
    """
    try:
        return elem[0] if elem[0].tag == XSD_ANNOTATION_TAG else None
    except (TypeError, IndexError):
        return None


def get_attributes(obj):
    if isinstance(obj, dict):
        return obj
    elif isinstance(obj, str):
        return {(attr.split('=', maxsplit=1) for attr in obj.split(' '))}
    else:
        return obj.attrib


def get_xsd_component(elem, required=True, strict=True):
    declarations_iterator = iter_xsd_declarations(elem)
    try:
        xsd_declaration = next(declarations_iterator)
    except StopIteration:
        if required:
            raise XMLSchemaParseError("missing declaration", elem)
        return None
    else:
        if not strict:
            return xsd_declaration
        try:
            next(declarations_iterator)
        except StopIteration:
            return xsd_declaration
        else:
            raise XMLSchemaParseError("too many declarations", elem)


def iter_xsd_declarations(elem):
    """
    Get the node's children are XSD declarations, excluding annotations.
    """
    counter = 0
    for child in elem:
        if child.tag == XSD_ANNOTATION_TAG:
            if counter > 0:
                raise XMLSchemaParseError("XSD annotation not allowed here!", elem)
        else:
            yield child
            counter += 1


def get_xsd_attribute(elem, attribute, enumeration=None, **kwargs):
    """
    Get an element's attribute and throws a schema error if the attribute is absent
    and a default is not provided in keyword arguments. The value of the attribute
    can be checked with a list of admitted values.

    :param elem: The Element instance.
    :param attribute: The name of the XML attribute.
    :param enumeration: Container with the admitted values for the attribute.
    :param kwargs: Optional keyword arguments for a default value or for
    an enumeration with admitted values.
    :return: The attribute value in a string or the default value.
    """
    try:
        value = elem.attrib[attribute]
    except (KeyError, AttributeError) as err:
        try:
            return kwargs['default']
        except KeyError:
            raise XMLSchemaParseError("attribute {} expected".format(err), elem)
    else:
        if enumeration and value not in enumeration:
            raise XMLSchemaParseError("wrong value %r for %r attribute" % (value, attribute), elem)
        return value


def get_xsd_bool_attribute(elem, attribute, **kwargs):
    value = get_xsd_attribute(elem, attribute, **kwargs)
    if isinstance(value, bool):
        return value
    elif value in ('true', '1'):
        return True
    elif value in ('false', '0'):
        return False
    else:
        raise XMLSchemaParseError(
            "an XML boolean value is required for attribute %r" % attribute, elem
        )


def get_xsd_int_attribute(elem, attribute, minimum=None, **kwargs):
    """
    Get an element's attribute converting it to an int(). Throws an
    error if the attribute is not found and the default is None.
    Checks the value when a minimum is provided.

    :param elem: The Element's instance.
    :param attribute: The attribute name.
    :param minimum: Optional minimum integer value for the attribute.
    :return: Integer containing the attribute value.
    """
    value = get_xsd_attribute(elem, attribute, **kwargs)
    try:
        value = int(value)
    except (TypeError, ValueError) as err:
        raise XMLSchemaParseError("attribute %r error: %r" % (attribute, str(err)), elem)
    else:
        if minimum is None or value >= minimum:
            return value
        else:
            raise XMLSchemaParseError(
                "attribute %r value must be greater or equal to %r" % (attribute, minimum), elem
            )


def get_xsd_derivation_attribute(elem, attribute, values):
    """
    Get a derivation attribute (maybe 'block', 'blockDefault', 'final' or 'finalDefault')
    checking the items with the values arguments. Returns a string.

    :param elem: The Element's instance.
    :param attribute: The attribute name.
    :param values: Sequence of admitted values when the attribute value is not '#all'.
    :return: A string.
    """
    value = get_xsd_attribute(elem, attribute, default='')
    items = value.split()
    if len(items) == 1 and items[0] == "#all":
        return ' '.join(values)
    elif not all([s in values for s in items]):
        raise XMLSchemaParseError("wrong value %r for attribute %r." % (value, attribute), elem)
    return value


def iterchildren_by_tag(tag):
    """
    Defines a generator that produce all child elements that have a specific tag.
    """
    def iterfind_function(root):
        for elem in root:
            if elem.tag == tag:
                yield elem
    iterfind_function.__name__ = 'iterfind_xsd_%ss' % '_'.join(camel_case_split(local_name(tag))).lower()
    return iterfind_function

iterchildren_xsd_import = iterchildren_by_tag(XSD_IMPORT_TAG)
iterchildren_xsd_include = iterchildren_by_tag(XSD_INCLUDE_TAG)
iterchildren_xsd_redefine = iterchildren_by_tag(XSD_REDEFINE_TAG)


class XsdBase(object):
    """
    Base class for XML Schema Definition classes.

    :param elem: ElementTree's node containing the definition.
    :param schema: The XMLSchema object that owns the definition.
    """
    _DUMMY_DICT = FrozenDict()
    _REGEX_SPACE = re.compile(r'\s')
    _REGEX_SPACES = re.compile(r'\s+')

    def __init__(self, elem, schema=None):
        self.schema = schema
        self.elem = elem

    def __setattr__(self, name, value):
        if name == "elem":
            elem = getattr(self, 'elem', None)
            if False and elem is not None and elem is not value:
                raise XMLSchemaValueError("cannot change the 'elem' of an XSD object.")
            self._attrib = value.attrib if value is not None else self._DUMMY_DICT
        elif name == "schema":
            schema = getattr(self, 'schema', None)
            if schema is not None:
                if value is None:
                    raise XMLSchemaValueError("cannot remove the 'schema' of %r." % self)
                if schema.target_namespace != value.target_namespace:
                    import pdb
                    pdb.set_trace()
                    raise XMLSchemaValueError(
                        "cannot change 'schema' attribute of %r: the actual %r has a different "
                        "target namespace than %r." % (self, schema, value)
                    )
            if value is not None:
                self.target_namespace = value.target_namespace
                self.namespaces = value.namespaces
            else:
                self.target_namespace = ''
                self.namespaces = self._DUMMY_DICT
        super(XsdBase, self).__setattr__(name, value)

    def __repr__(self):
        return u"<%s at %#x>" % (self.__class__.__name__, id(self))

    def __str__(self):
        # noinspection PyCompatibility
        return unicode(self).encode("utf-8")

    def __unicode__(self):
        return self.__repr__()

    if PY3:
        __str__ = __unicode__

    def _get_namespace_attribute(self):
        """
        Get the namespace attribute value for anyAttribute and anyElement declaration,
        checking if the value is conforming to the specification.
        """
        value = get_xsd_attribute(self.elem, 'namespace', default='##any')
        items = value.split()
        if len(items) == 1 and items[0] in ('##any', '##all', '##other', '##local', '##targetNamespace'):
            return value
        elif not all([s not in ('##any', '##other') for s in items]):
            self.schema.errors.append(
                XMLSchemaParseError("wrong value %r for the 'namespace' attribute." % value, self.elem)
            )
        return value

    def _is_namespace_allowed(self, namespace, any_namespace):
        if any_namespace == '##any' or namespace == XSI_NAMESPACE_PATH:
            return True
        elif any_namespace == '##other':
            return namespace != self.target_namespace
        else:
            any_namespaces = any_namespace.split()
            if '##local' in any_namespaces and namespace == '':
                return True
            elif '##targetNamespace' in any_namespaces and namespace == self.target_namespace:
                return True
            else:
                return namespace in any_namespaces

    @property
    def id(self):
        """The ``'id'`` attribute of declaration tag, ``None`` if missing."""
        return self._attrib.get('id')

    def to_string(self, indent='', max_lines=None, spaces_for_tab=4):
        if self.elem is None:
            return str(None)
        else:
            return etree_tostring(self.elem, indent, max_lines, spaces_for_tab)


class XsdAnnotation(XsdBase):
    """
    Class for XSD 'annotation' definitions.
    
    <annotation
      id = ID
      {any attributes with non-schema namespace . . .}>
      Content: (appinfo | documentation)*
    </annotation>
    
    <appinfo
      source = anyURI
      {any attributes with non-schema namespace . . .}>
      Content: ({any})*
    </appinfo>
    
    <documentation
      source = anyURI
      xml:lang = language
      {any attributes with non-schema namespace . . .}>
      Content: ({any})*
    </documentation>
    """
    def __setattr__(self, name, value):
        if name == 'elem':
            check_tag(value, XSD_ANNOTATION_TAG)
            self.appinfo = []
            self.documentation = []
            for child in value:
                if child.tag == XSD_APPINFO_TAG:
                    for key in child.attrib:
                        if key != 'source':
                            self.schema.errors.append(XMLSchemaParseError(
                                "wrong attribute %r for appinfo declaration." % key, self
                            ))
                    self.appinfo.append(child)
                elif child.tag == XSD_DOCUMENTATION_TAG:
                    for key in child.attrib:
                        if key not in ['source', XML_LANG]:
                            self.schema.errors.append(XMLSchemaParseError(
                                "wrong attribute %r for documentation declaration." % key, self
                            ))
                    self.documentation.append(child)
        super(XsdAnnotation, self).__setattr__(name, value)


class XsdComponent(XsdBase, XMLSchemaValidator):
    """
    XML Schema component base class.

    :param elem: ElementTree's node containing the definition.
    :param schema: The XMLSchema object that owns the definition.
    :param is_global: `True` if the component is a global declaration/definition, \
    `False` if it's local.
    :param parent: Parent XSD component. For global components the default parent \
    is the argument `schema`.
    :param name: Name of the component, overwritten by the parse of the `elem` argument.
    :param options: Options containing classes and factories to use for creating new components.
    """
    FACTORY_KWARG = None
    XSD_GLOBAL_TAG = None

    def __init__(self, elem, schema=None, is_global=False, parent=None, name=None, **options):
        self.is_global = is_global
        if is_global:
            self.parent = schema or parent
        else:
            self.parent = parent
        self.name = name
        self.options = options
        self.errors = []  # Component parsing errors
        super(XsdComponent, self).__init__(elem, schema)
        XMLSchemaValidator.__init__(self)

    def __repr__(self):
        return u"<%s %r at %#x>" % (self.__class__.__name__, self.name, id(self))

    def __str__(self):
        # noinspection PyCompatibility
        return unicode(self).encode("utf-8")

    def __unicode__(self):
        if self.name and self.name[0] == '{':
            return self.name
        else:
            return self.__repr__()

    if PY3:
        __str__ = __unicode__

    def __setattr__(self, name, value):
        super(XsdComponent, self).__setattr__(name, value)
        if name == 'elem' and value is not None and self.schema is not None:
            self._parse()

    def _parse(self):
        if self.errors:
            del self.errors[:]
        annotation = get_xsd_annotation(self.elem)
        if annotation is not None:
            self.annotation = XsdAnnotation(annotation, self.schema)
        else:
            self.annotation = None

    def _parse_error(self, msg, elem=None):
        self.errors.append(XMLSchemaParseError(msg, self, elem))

    @property
    def check_token(self):
        return self.schema.maps.check_token

    @property
    def built(self):
        return self.elem is not None or self.name in XSD_SPECIAL_TYPES

    def check(self):
        if self.checked:
            return
        XMLSchemaValidator.check(self)

        if self.name in XSD_SPECIAL_TYPES:
            self._valid = True
        elif self.built is False:
            self._valid = None
        if self.schema is not None:
            if any([err.obj is self.elem for err in self.schema.errors]):
                self._valid = False
            elif self.schema.validation == 'strict':
                self._valid = True
            else:
                self._valid = None
        else:
            self._valid = None

    def iter_components(self, xsd_classes=None):
        if xsd_classes is None or isinstance(self, xsd_classes):
            yield self

    def iter_encode(self, *args, **kwargs):
        raise NotImplementedError

    def iter_decode(self, *args, **kwargs):
        raise NotImplementedError


class ParticleMixin(object):
    """
    Mixin for objects related to XSD Particle Schema Components:

      https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/structures.html#p
      https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/structures.html#t
    """
    def __setattr__(self, name, value):
        super(ParticleMixin, self).__setattr__(name, value)
        if name == 'elem':
            max_occurs = self.max_occurs
            if max_occurs is not None and self.min_occurs > max_occurs:
                schema = getattr(self, 'schema')
                if schema is not None:
                    schema.errors.append(XMLSchemaParseError(
                        "maxOccurs must be 'unbounded' or greater than minOccurs:", self
                    ))

    @property
    def min_occurs(self):
        return get_xsd_int_attribute(getattr(self, 'elem'), 'minOccurs', default=1, minimum=0)

    @property
    def max_occurs(self):
        try:
            return get_xsd_int_attribute(getattr(self, 'elem'), 'maxOccurs', default=1, minimum=0)
        except (TypeError, ValueError):
            if getattr(self, '_attrib')['maxOccurs'] == 'unbounded':
                return None
            raise

    def is_optional(self):
        return getattr(self, 'elem').get('minOccurs', '').strip() == "0"

    def is_emptiable(self):
        return self.min_occurs == 0

    def is_single(self):
        return self.max_occurs == 1
