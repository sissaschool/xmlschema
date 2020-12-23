#
# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module contains classes for XML Schema wildcards.
"""
from ..exceptions import XMLSchemaValueError
from ..names import XSI_NAMESPACE, XSD_ANY, XSD_ANY_ATTRIBUTE, \
    XSD_OPEN_CONTENT, XSD_DEFAULT_OPEN_CONTENT, XSI_TYPE
from ..helpers import get_namespace
from ..xpath import XMLSchemaProxy, ElementPathMixin
from .xsdbase import ValidationMixin, XsdComponent
from .particles import ParticleMixin


class XsdWildcard(XsdComponent, ValidationMixin):
    names = ()
    namespace = ('##any',)
    not_namespace = ()
    not_qname = ()
    process_contents = 'strict'

    def __repr__(self):
        if self.not_namespace:
            return '%s(not_namespace=%r, process_contents=%r)' % (
                self.__class__.__name__, self.not_namespace, self.process_contents
            )
        else:
            return '%s(namespace=%r, process_contents=%r)' % (
                self.__class__.__name__, self.namespace, self.process_contents
            )

    def _parse(self):
        super(XsdWildcard, self)._parse()

        # Parse namespace and processContents
        namespace = self.elem.get('namespace', '##any').strip()
        if namespace == '##any':
            pass
        elif not namespace:
            self.namespace = []  # an empty value means no namespace allowed!
        elif namespace == '##other':
            self.namespace = [namespace]
        elif namespace == '##local':
            self.namespace = ['']
        elif namespace == '##targetNamespace':
            self.namespace = [self.target_namespace]
        else:
            self.namespace = []
            for ns in namespace.split():
                if ns == '##local':
                    self.namespace.append('')
                elif ns == '##targetNamespace':
                    self.namespace.append(self.target_namespace)
                elif ns.startswith('##'):
                    self.parse_error("wrong value %r in 'namespace' attribute" % ns)
                else:
                    self.namespace.append(ns)

        process_contents = self.elem.get('processContents', 'strict')
        if process_contents == 'strict':
            pass
        elif process_contents not in ('lax', 'skip'):
            self.parse_error("wrong value %r for 'processContents' "
                             "attribute" % self.process_contents)
        else:
            self.process_contents = process_contents

    def _parse_not_constraints(self):
        if 'notNamespace' not in self.elem.attrib:
            pass
        elif 'namespace' in self.elem.attrib:
            self.parse_error("'namespace' and 'notNamespace' attributes are mutually exclusive")
        else:
            self.namespace = []
            self.not_namespace = []
            for ns in self.elem.attrib['notNamespace'].strip().split():
                if ns == '##local':
                    self.not_namespace.append('')
                elif ns == '##targetNamespace':
                    self.not_namespace.append(self.target_namespace)
                elif ns.startswith('##'):
                    self.parse_error("wrong value %r in 'notNamespace' attribute" % ns)
                else:
                    self.not_namespace.append(ns)

        # Parse notQName attribute
        if 'notQName' not in self.elem.attrib:
            return

        not_qname = self.elem.attrib['notQName'].strip().split()

        if isinstance(self, XsdAnyAttribute) and \
                not all(not s.startswith('##') or s == '##defined'
                        for s in not_qname) or \
                not all(not s.startswith('##') or s in {'##defined', '##definedSibling'}
                        for s in not_qname):
            self.parse_error("wrong value for 'notQName' attribute")
            return

        try:
            names = [x if x.startswith('##') else self.schema.resolve_qname(x, False)
                     for x in not_qname]
        except KeyError as err:
            self.parse_error("unmapped QName in 'notQName' attribute: %s" % str(err))
            return
        except ValueError as err:
            self.parse_error("wrong QName format in 'notQName' attribute: %s" % str(err))
            return

        if self.not_namespace:
            if any(not x.startswith('##') for x in names) and \
                    all(get_namespace(x) in self.not_namespace
                        for x in names if not x.startswith('##')):
                self.parse_error("the namespace of each QName in notQName "
                                 "is allowed by notNamespace")
        elif any(not self.is_namespace_allowed(get_namespace(x))
                 for x in names if not x.startswith('##')):
            self.parse_error("names in notQName must be in namespaces that are allowed")

        self.not_qname = names

    @property
    def built(self):
        return True

    def is_matching(self, name, default_namespace=None, **kwargs):
        if name is None:
            return False
        elif not name or name[0] == '{':
            return self.is_namespace_allowed(get_namespace(name))
        elif not default_namespace:
            return self.is_namespace_allowed('')
        else:
            return self.is_namespace_allowed('') or \
                self.is_namespace_allowed(default_namespace)

    def is_namespace_allowed(self, namespace):
        if self.not_namespace:
            return namespace not in self.not_namespace
        elif '##any' in self.namespace or namespace == XSI_NAMESPACE:
            return True
        elif '##other' in self.namespace:
            return namespace and namespace != self.target_namespace
        else:
            return namespace in self.namespace

    def deny_namespaces(self, namespaces):
        if self.not_namespace:
            return all(x in self.not_namespace for x in namespaces)
        elif '##any' in self.namespace:
            return False
        elif '##other' in self.namespace:
            return all(x == self.target_namespace for x in namespaces)
        else:
            return all(x not in self.namespace for x in namespaces)

    def deny_qnames(self, names):
        if self.not_namespace:
            return all(x in self.not_qname or get_namespace(x) in self.not_namespace
                       for x in names)
        elif '##any' in self.namespace:
            return all(x in self.not_qname for x in names)
        elif '##other' in self.namespace:
            return all(x in self.not_qname or get_namespace(x) == self.target_namespace
                       for x in names)
        else:
            return all(x in self.not_qname or get_namespace(x) not in self.namespace
                       for x in names)

    def is_restriction(self, other, check_occurs=True):
        if check_occurs and isinstance(self, ParticleMixin) \
                and not self.has_occurs_restriction(other):
            return False
        elif not isinstance(other, type(self)):
            return False
        elif other.process_contents == 'strict' and self.process_contents != 'strict':
            return False
        elif other.process_contents == 'lax' and self.process_contents == 'skip':
            return False

        if not self.not_qname and not other.not_qname:
            pass
        elif '##defined' in other.not_qname and '##defined' not in self.not_qname:
            return False
        elif '##definedSibling' in other.not_qname and '##definedSibling' not in self.not_qname:
            return False
        elif other.not_qname:
            if not self.deny_qnames(x for x in other.not_qname if not x.startswith('##')):
                return False
        elif any(not other.is_namespace_allowed(get_namespace(x))
                 for x in self.not_qname if not x.startswith('##')):
            return False

        if self.not_namespace:
            if other.not_namespace:
                return all(ns in self.not_namespace for ns in other.not_namespace)
            elif '##any' in other.namespace:
                return True
            elif '##other' in other.namespace:
                return '' in self.not_namespace and other.target_namespace in self.not_namespace
            else:
                return False
        elif other.not_namespace:
            if '##any' in self.namespace:
                return False
            elif '##other' in self.namespace:
                return set(other.not_namespace).issubset({'', other.target_namespace})
            else:
                return all(ns not in other.not_namespace for ns in self.namespace)

        if self.namespace == other.namespace:
            return True
        elif '##any' in other.namespace:
            return True
        elif '##any' in self.namespace or '##other' in self.namespace:
            return False
        elif '##other' in other.namespace:
            return other.target_namespace not in self.namespace and '' not in self.namespace
        else:
            return all(ns in other.namespace for ns in self.namespace)

    def union(self, other):
        """
        Update an XSD wildcard with the union of itself and another XSD wildcard.
        """
        if not self.not_qname:
            self.not_qname = other.not_qname[:]
        else:
            self.not_qname = [
                x for x in self.not_qname
                if x in other.not_qname or not other.is_namespace_allowed(get_namespace(x))
            ]

        if self.not_namespace:
            if other.not_namespace:
                self.not_namespace = [ns for ns in self.not_namespace if ns in other.not_namespace]
            elif '##any' in other.namespace:
                self.not_namespace = []
                self.namespace = ['##any']
                return
            elif '##other' in other.namespace:
                not_namespace = ('', other.target_namespace)
                self.not_namespace = [ns for ns in self.not_namespace if ns in not_namespace]
            else:
                self.not_namespace = [ns for ns in self.not_namespace if ns not in other.namespace]

            if not self.not_namespace:
                self.namespace = ['##any']
            return

        elif other.not_namespace:
            if '##any' in self.namespace:
                return
            elif '##other' in self.namespace:
                not_namespace = ('', self.target_namespace)
                self.not_namespace = [ns for ns in other.not_namespace if ns in not_namespace]
            else:
                self.not_namespace = [ns for ns in other.not_namespace if ns not in self.namespace]

            self.namespace = ['##any'] if not self.not_namespace else []
            return

        if '##any' in self.namespace or self.namespace == other.namespace:
            return
        elif '##any' in other.namespace:
            self.namespace = ['##any']
            return
        elif '##other' in other.namespace:
            w1, w2 = other, self
        elif '##other' in self.namespace:
            w1, w2 = self, other
        else:
            self.namespace.extend(ns for ns in other.namespace if ns not in self.namespace)
            return

        if w1.target_namespace in w2.namespace and '' in w2.namespace:
            self.namespace = ['##any']
        elif '' not in w2.namespace and w1.target_namespace == w2.target_namespace:
            self.namespace = ['##other']
        elif self.xsd_version == '1.0':
            msg = "not expressible wildcard namespace union: {!r} V {!r}:"
            raise XMLSchemaValueError(msg.format(other.namespace, self.namespace))
        else:
            self.namespace = []
            self.not_namespace = ['', w1.target_namespace] if w1.target_namespace else ['']

    def intersection(self, other):
        """
        Update an XSD wildcard with the intersection of itself and another XSD wildcard.
        """
        if self.not_qname:
            self.not_qname.extend(x for x in other.not_qname if x not in self.not_qname)
        else:
            self.not_qname = [x for x in other.not_qname]

        if self.not_namespace:
            if other.not_namespace:
                self.not_namespace.extend(ns for ns in other.not_namespace
                                          if ns not in self.not_namespace)
            elif '##any' in other.namespace:
                pass
            elif '##other' not in other.namespace:
                self.namespace = [ns for ns in other.namespace if ns not in self.not_namespace]
                self.not_namespace = []
            else:
                if other.target_namespace not in self.not_namespace:
                    self.not_namespace.append(other.target_namespace)
                if '' not in self.not_namespace:
                    self.not_namespace.append('')
            return

        elif other.not_namespace:
            if '##any' in self.namespace:
                self.not_namespace = [ns for ns in other.not_namespace]
                self.namespace = []
            elif '##other' not in self.namespace:
                self.namespace = [ns for ns in self.namespace if ns not in other.not_namespace]
            else:
                self.not_namespace = [ns for ns in other.not_namespace]
                if self.target_namespace not in self.not_namespace:
                    self.not_namespace.append(self.target_namespace)
                if '' not in self.not_namespace:
                    self.not_namespace.append('')
                self.namespace = []
            return

        if self.namespace == other.namespace:
            return
        elif '##any' in other.namespace:
            return
        elif '##any' in self.namespace:
            self.namespace = other.namespace[:]
        elif '##other' in self.namespace:
            self.namespace = [ns for ns in other.namespace if ns not in ('', self.target_namespace)]
        elif '##other' not in other.namespace:
            self.namespace = [ns for ns in self.namespace if ns in other.namespace]
        else:
            if other.target_namespace in self.namespace:
                self.namespace.remove(other.target_namespace)
            if '' in self.namespace:
                self.namespace.remove('')

    def iter_decode(self, source, validation='lax', **kwargs):
        raise NotImplementedError

    def iter_encode(self, obj, validation='lax', **kwargs):
        raise NotImplementedError


class XsdAnyElement(XsdWildcard, ParticleMixin, ElementPathMixin):
    """
    Class for XSD 1.0 *any* wildcards.

    ..  <any
          id = ID
          maxOccurs = (nonNegativeInteger | unbounded) : 1
          minOccurs = nonNegativeInteger : 1
          namespace = ((##any | ##other) | List of (anyURI | (##targetNamespace|##local)) ) : ##any
          processContents = (lax | skip | strict) : strict
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </any>
    """
    _ADMITTED_TAGS = {XSD_ANY}
    precedences = ()

    def __init__(self, elem, schema, parent, maps=None):
        super(XsdAnyElement, self).__init__(elem, schema, parent, maps)
        ElementPathMixin.__init__(self)

    def __repr__(self):
        if self.namespace:
            return '%s(namespace=%r, process_contents=%r, occurs=%r)' % (
                self.__class__.__name__, self.namespace, self.process_contents, self.occurs
            )
        else:
            return '%s(not_namespace=%r, process_contents=%r, occurs=%r)' % (
                self.__class__.__name__, self.not_namespace, self.process_contents, self.occurs
            )

    @property
    def xpath_proxy(self):
        return XMLSchemaProxy(self.schema, self)

    def _parse(self):
        super(XsdAnyElement, self)._parse()
        self._parse_particle(self.elem)

    def match(self, name, default_namespace=None, resolve=False, **kwargs):
        """
        Returns the element wildcard if name is matching the name provided
        as argument, `None` otherwise.

        :param name: a local or fully-qualified name.
        :param default_namespace: used when it's not `None` and not empty for \
        completing local name arguments.
        :param resolve: when `True` it doesn't return the wildcard but try to \
        resolve and return the element matching the name.
        :param kwargs: additional options used by XSD 1.1 xs:any wildcards.
        """
        if not self.is_matching(name, default_namespace, **kwargs):
            return
        elif not resolve:
            return self

        try:
            if name[0] != '{' and default_namespace:
                return self.maps.lookup_element('{%s}%s' % (default_namespace, name))
            else:
                return self.maps.lookup_element(name)
        except LookupError:
            pass

    def __iter__(self):
        return iter(())

    def iter(self, tag=None):
        return iter(())

    def iterchildren(self, tag=None):
        return iter(())

    @staticmethod
    def iter_substitutes():
        return iter(())

    def iter_decode(self, elem, validation='lax', **kwargs):
        if not self.is_matching(elem.tag):
            reason = "{!r} is not allowed here".format(elem)
            yield self.validation_error(validation, reason, elem, **kwargs)

        elif self.process_contents == 'skip':
            return

        elif self.maps.load_namespace(get_namespace(elem.tag)):
            try:
                xsd_element = self.maps.lookup_element(elem.tag)
            except LookupError:
                if XSI_TYPE in elem.attrib:
                    if self.process_contents == 'lax':
                        xsd_element = self.maps.validator.create_element(elem.tag, nillable='true')
                    else:
                        xsd_element = self.maps.validator.create_element(elem.tag)
                    yield from xsd_element.iter_decode(elem, validation, **kwargs)
                elif validation == 'skip' or self.process_contents == 'lax':
                    yield from self.any_type.iter_decode(elem, validation, **kwargs)
                else:
                    reason = "element %r not found." % elem.tag
                    yield self.validation_error(validation, reason, elem, **kwargs)
            else:
                yield from xsd_element.iter_decode(elem, validation, **kwargs)

        elif validation == 'skip':
            yield self.any_type.decode(elem) if len(elem) > 0 else elem.text

        elif self.process_contents == 'strict':
            reason = "unavailable namespace {!r}".format(get_namespace(elem.tag))
            yield self.validation_error(validation, reason, elem, **kwargs)

    def iter_encode(self, obj, validation='lax', **kwargs):
        name, value = obj
        namespace = get_namespace(name)

        if not self.is_namespace_allowed(namespace):
            reason = "element {!r} is not allowed here".format(name)
            yield self.validation_error(validation, reason, value, **kwargs)

        elif self.process_contents == 'skip':
            return

        elif self.maps.load_namespace(namespace):
            try:
                xsd_element = self.maps.lookup_element(name)
            except LookupError:
                if validation == 'skip' or self.process_contents == 'lax':
                    yield from self.any_type.iter_encode(obj, validation, **kwargs)
                elif self.process_contents == 'strict':
                    reason = "element %r not found." % name
                    yield self.validation_error(validation, reason, **kwargs)
            else:
                yield from xsd_element.iter_encode(value, validation, **kwargs)

        elif validation == 'skip':
            yield self.any_type.encode(value)

        elif self.process_contents == 'strict':
            reason = "unavailable namespace {!r}".format(namespace)
            yield self.validation_error(validation, reason, **kwargs)

    def is_overlap(self, other):
        if not isinstance(other, XsdAnyElement):
            return other.is_overlap(self)
        elif self.not_namespace:
            if other.not_namespace:
                return True
            elif '##any' in other.namespace:
                return True
            elif '##other' in other.namespace:
                return True
            else:
                return any(ns not in self.not_namespace for ns in other.namespace)
        elif other.not_namespace:
            if '##any' in self.namespace:
                return True
            elif '##other' in self.namespace:
                return True
            else:
                return any(ns not in other.not_namespace for ns in self.namespace)
        elif self.namespace == other.namespace:
            return True
        elif '##any' in self.namespace or '##any' in other.namespace:
            return True
        elif '##other' in self.namespace:
            return any(ns and ns != self.target_namespace for ns in other.namespace)
        elif '##other' in other.namespace:
            return any(ns and ns != other.target_namespace for ns in self.namespace)
        else:
            return any(ns in self.namespace for ns in other.namespace)

    def is_consistent(self, other):
        return True


class XsdAnyAttribute(XsdWildcard):
    """
    Class for XSD 1.0 *anyAttribute* wildcards.

    ..  <anyAttribute
          id = ID
          namespace = ((##any | ##other) | List of (anyURI | (##targetNamespace | ##local)) )
          processContents = (lax | skip | strict) : strict
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </anyAttribute>
    """
    _ADMITTED_TAGS = {XSD_ANY_ATTRIBUTE}

    def match(self, name, default_namespace=None, resolve=False, **kwargs):
        """
        Returns the attribute wildcard if name is matching the name provided
        as argument, `None` otherwise.

        :param name: a local or fully-qualified name.
        :param default_namespace: used when it's not `None` and not empty for \
        completing local name arguments.
        :param resolve: when `True` it doesn't return the wildcard but try to \
        resolve and return the attribute matching the name.
        :param kwargs: additional options that can be used by certain components.
        """
        if not self.is_matching(name, default_namespace, **kwargs):
            return
        elif not resolve:
            return self

        try:
            if name[0] != '{' and default_namespace:
                return self.maps.lookup_attribute('{%s}%s' % (default_namespace, name))
            else:
                return self.maps.lookup_attribute(name)
        except LookupError:
            pass

    def iter_decode(self, attribute, validation='lax', **kwargs):
        name, value = attribute

        if not self.is_matching(name):
            reason = "attribute %r not allowed." % name
            yield self.validation_error(validation, reason, attribute, **kwargs)

        elif self.process_contents == 'skip':
            return

        elif self.maps.load_namespace(get_namespace(name)):
            try:
                xsd_attribute = self.maps.lookup_attribute(name)
            except LookupError:
                if validation == 'skip':
                    yield value
                elif self.process_contents == 'strict':
                    reason = "attribute %r not found." % name
                    yield self.validation_error(validation, reason, attribute, **kwargs)
            else:
                yield from xsd_attribute.iter_decode(value, validation, **kwargs)

        elif validation == 'skip':
            yield value

        elif self.process_contents == 'strict':
            reason = "unavailable namespace {!r}".format(get_namespace(name))
            yield self.validation_error(validation, reason, **kwargs)

    def iter_encode(self, attribute, validation='lax', **kwargs):
        name, value = attribute
        namespace = get_namespace(name)

        if not self.is_namespace_allowed(namespace):
            reason = "attribute %r not allowed." % name
            yield self.validation_error(validation, reason, attribute, **kwargs)

        elif self.process_contents == 'skip':
            return

        elif self.maps.load_namespace(namespace):
            try:
                xsd_attribute = self.maps.lookup_attribute(name)
            except LookupError:
                if validation == 'skip':
                    yield str(value)
                elif self.process_contents == 'strict':
                    reason = "attribute %r not found." % name
                    yield self.validation_error(validation, reason, attribute, **kwargs)
            else:
                yield from xsd_attribute.iter_encode(value, validation, **kwargs)

        elif validation == 'skip':
            yield str(value)

        elif self.process_contents == 'strict':
            reason = "unavailable namespace {!r}".format(get_namespace(name))
            yield self.validation_error(validation, reason, **kwargs)


class Xsd11AnyElement(XsdAnyElement):
    """
    Class for XSD 1.1 *any* declarations.

    ..  <any
          id = ID
          maxOccurs = (nonNegativeInteger | unbounded)  : 1
          minOccurs = nonNegativeInteger : 1
          namespace = ((##any | ##other) | List of (anyURI | (##targetNamespace | ##local)) )
          notNamespace = List of (anyURI | (##targetNamespace | ##local))
          notQName = List of (QName | (##defined | ##definedSibling))
          processContents = (lax | skip | strict) : strict
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </any>
    """
    def _parse(self):
        super(Xsd11AnyElement, self)._parse()
        self._parse_not_constraints()

    def is_matching(self, name, default_namespace=None, group=None, occurs=None):
        """
        Returns `True` if the component name is matching the name provided as argument,
        `False` otherwise. For XSD elements the matching is extended to substitutes.

        :param name: a local or fully-qualified name.
        :param default_namespace: used if it's not None and not empty for completing \
        the name argument in case it's a local name.
        :param group: used only by XSD 1.1 any element wildcards to verify siblings in \
        case of ##definedSibling value in notQName attribute.
        :param occurs: a Counter instance for verify model occurrences counting.
        """
        if name is None:
            return False
        elif not name or name[0] == '{':
            if not self.is_namespace_allowed(get_namespace(name)):
                return False
        elif not default_namespace:
            if not self.is_namespace_allowed(''):
                return False
        else:
            name = '{%s}%s' % (default_namespace, name)
            if not self.is_namespace_allowed('') \
                    and not self.is_namespace_allowed(default_namespace):
                return False

        if group in self.precedences:
            if occurs is None:
                if any(e.is_matching(name) for e in self.precedences[group]):
                    return False
            elif any(e.is_matching(name) and not e.is_over(occurs[e])
                     for e in self.precedences[group]):
                return False

        if '##defined' in self.not_qname and name in self.maps.elements:
            return False
        if group and '##definedSibling' in self.not_qname:
            if any(e.is_matching(name) for e in group.iter_elements()
                   if not isinstance(e, XsdAnyElement)):
                return False

        return name not in self.not_qname

    def is_consistent(self, other):
        if isinstance(other, XsdAnyElement) or self.process_contents == 'skip':
            return True
        xsd_element = self.match(other.name, other.default_namespace, resolve=True)
        return xsd_element is None or other.is_consistent(xsd_element, strict=False)

    def add_precedence(self, other, group):
        if not self.precedences:
            self.precedences = {}
        try:
            self.precedences[group].append(other)
        except KeyError:
            self.precedences[group] = [other]


class Xsd11AnyAttribute(XsdAnyAttribute):
    """
    Class for XSD 1.1 *anyAttribute* declarations.

    ..  <anyAttribute
          id = ID
          namespace = ((##any | ##other) | List of (anyURI | (##targetNamespace | ##local)) )
          notNamespace = List of (anyURI | (##targetNamespace | ##local))
          notQName = List of (QName | ##defined)
          processContents = (lax | skip | strict) : strict
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </anyAttribute>
    """
    inheritable = False  # Added for reduce checkings on XSD 1.1 attributes

    def _parse(self):
        super(Xsd11AnyAttribute, self)._parse()
        self._parse_not_constraints()

    def is_matching(self, name, default_namespace=None, **kwargs):
        if name is None:
            return False
        elif not name or name[0] == '{':
            namespace = get_namespace(name)
        elif not default_namespace:
            namespace = ''
        else:
            name = '{%s}%s' % (default_namespace, name)
            namespace = default_namespace

        if '##defined' in self.not_qname and name in self.maps.attributes:
            if self.maps.attributes[name].schema is self.schema:
                return False
        return name not in self.not_qname and self.is_namespace_allowed(namespace)


class XsdOpenContent(XsdComponent):
    """
    Class for XSD 1.1 *openContent* model definitions.

    ..  <openContent
          id = ID
          mode = (none | interleave | suffix) : interleave
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?), (any?)
        </openContent>
    """
    _ADMITTED_TAGS = {XSD_OPEN_CONTENT}
    mode = 'interleave'
    any_element = None

    def __init__(self, elem, schema, parent):
        super(XsdOpenContent, self).__init__(elem, schema, parent)

    def __repr__(self):
        return '%s(mode=%r)' % (self.__class__.__name__, self.mode)

    def _parse(self):
        super(XsdOpenContent, self)._parse()
        try:
            self.mode = self.elem.attrib['mode']
        except KeyError:
            pass
        else:
            if self.mode not in {'none', 'interleave', 'suffix'}:
                self.parse_error("wrong value %r for 'mode' attribute." % self.mode)

        child = self._parse_child_component(self.elem)
        if self.mode == 'none':
            if child is not None and child.tag == XSD_ANY:
                self.parse_error("an openContent with mode='none' must not "
                                 "have an <xs:any> child declaration")
        elif child is None or child.tag != XSD_ANY:
            self.parse_error("an <xs:any> child declaration is required")
        else:
            any_element = Xsd11AnyElement(child, self.schema, self)
            any_element.min_occurs = 0
            any_element.max_occurs = None
            self.any_element = any_element

    @property
    def built(self):
        return True

    def is_restriction(self, other):
        if other is None or other.mode == 'none':
            return self.mode == 'none'
        elif self.mode == 'interleave' and other.mode == 'suffix':
            return False
        else:
            return self.any_element.is_restriction(other.any_element)


class XsdDefaultOpenContent(XsdOpenContent):
    """
    Class for XSD 1.1 *defaultOpenContent* model definitions.

    ..  <defaultOpenContent
          appliesToEmpty = boolean : false
          id = ID
          mode = (interleave | suffix) : interleave
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?, any)
        </defaultOpenContent>
    """
    _ADMITTED_TAGS = {XSD_DEFAULT_OPEN_CONTENT}
    applies_to_empty = False

    def __init__(self, elem, schema):
        super(XsdOpenContent, self).__init__(elem, schema)

    def _parse(self):
        super(XsdDefaultOpenContent, self)._parse()
        if self.parent is not None:
            self.parse_error("defaultOpenContent must be a child of the schema")
        if self.mode == 'none':
            self.parse_error("the attribute 'mode' of a defaultOpenContent cannot be 'none'")
        if self._parse_child_component(self.elem) is None:
            self.parse_error("a defaultOpenContent declaration cannot be empty")

        if 'appliesToEmpty' in self.elem.attrib:
            if self.elem.attrib['appliesToEmpty'].strip() in {'true', '1'}:
                self.applies_to_empty = True
