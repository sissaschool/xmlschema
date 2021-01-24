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
This module contains classes for XML Schema attributes and attribute groups.
"""
from decimal import Decimal
from collections.abc import MutableMapping
from elementpath.datatypes import AbstractDateTime, Duration, AbstractBinary
from typing import Union, Dict, Optional

from ..exceptions import XMLSchemaValueError
from ..names import XSI_NAMESPACE, XSD_ANY_SIMPLE_TYPE, XSD_SIMPLE_TYPE, \
    XSD_ATTRIBUTE_GROUP, XSD_COMPLEX_TYPE, XSD_RESTRICTION, XSD_EXTENSION, \
    XSD_SEQUENCE, XSD_ALL, XSD_CHOICE, XSD_ATTRIBUTE, XSD_ANY_ATTRIBUTE, \
    XSD_ASSERT, XSD_NOTATION_TYPE, XSD_ANNOTATION
from ..helpers import get_namespace, get_qname

from .exceptions import XMLSchemaValidationError
from .xsdbase import XsdComponent, ValidationMixin
from .simple_types import XsdSimpleType
from .wildcards import XsdAnyAttribute


class XsdAttribute(XsdComponent, ValidationMixin):
    """
    Class for XSD 1.0 *attribute* declarations.

    :ivar type: the XSD simpleType of the attribute.

    ..  <attribute
          default = string
          fixed = string
          form = (qualified | unqualified)
          id = ID
          name = NCName
          ref = QName
          type = QName
          use = (optional | prohibited | required) : optional
          {any attributes with non-schema namespace ...}>
          Content: (annotation?, simpleType?)
        </attribute>
    """
    _ADMITTED_TAGS = {XSD_ATTRIBUTE}

    type = None
    qualified = False
    default = None
    fixed = None
    form = None
    use = 'optional'
    inheritable = False  # For XSD 1.1 attributes, always False for XSD 1.0 attributes.

    def _parse(self):
        super(XsdAttribute, self)._parse()
        attrib = self.elem.attrib

        if 'use' in attrib and self.parent is not None and \
                attrib['use'] in {'optional', 'prohibited', 'required'}:
            self.use = attrib['use']

        if self._parse_reference():
            try:
                xsd_attribute = self.maps.lookup_attribute(self.name)
            except LookupError:
                self.type = self.any_simple_type
                self.parse_error("unknown attribute {!r}".format(self.name))
            else:
                self.ref = xsd_attribute
                self.type = xsd_attribute.type
                self.qualified = xsd_attribute.qualified
                self.form = xsd_attribute.form

                if xsd_attribute.default is not None and 'default' not in attrib:
                    self.default = xsd_attribute.default

                if xsd_attribute.fixed is not None:
                    if 'fixed' not in attrib:
                        self.fixed = xsd_attribute.fixed
                    elif xsd_attribute.fixed != attrib['fixed']:
                        msg = "referenced attribute has a different fixed value {!r}"
                        self.parse_error(msg.format(xsd_attribute.fixed))

            for attribute in ('form', 'type'):
                if attribute in self.elem.attrib:
                    self.parse_error("attribute {!r} is not allowed when "
                                     "attribute reference is used".format(attribute))
        else:
            if 'form' in attrib:
                self.form = attrib['form']
                if self.parent is not None and self.form == 'qualified':
                    self.qualified = True
            elif self.schema.attribute_form_default == 'qualified':
                self.qualified = True

            try:
                name = attrib['name']
            except KeyError:
                pass
            else:
                if name == 'xmlns':
                    self.parse_error("an attribute name must be different from 'xmlns'")

                if self.parent is None or self.qualified:
                    if self.target_namespace == XSI_NAMESPACE and \
                            name not in {'nil', 'type', 'schemaLocation',
                                         'noNamespaceSchemaLocation'}:
                        self.parse_error("cannot add attributes in %r namespace" % XSI_NAMESPACE)
                    self.name = get_qname(self.target_namespace, name)
                else:
                    self.name = name

            child = self._parse_child_component(self.elem)
            if 'type' in attrib:
                try:
                    type_qname = self.schema.resolve_qname(attrib['type'])
                except (KeyError, ValueError, RuntimeError) as err:
                    self.type = self.any_simple_type
                    self.parse_error(err)
                else:
                    try:
                        self.type = self.maps.lookup_type(type_qname)
                    except LookupError as err:
                        self.type = self.any_simple_type
                        self.parse_error(err)

                    if child is not None and child.tag == XSD_SIMPLE_TYPE:
                        self.parse_error("ambiguous type definition for XSD attribute")

            elif child is not None:
                # No 'type' attribute in declaration, parse for child local simpleType
                self.type = self.schema.BUILDERS.simple_type_factory(child, self.schema, self)
            else:
                # Empty declaration means xsdAnySimpleType
                self.type = self.any_simple_type

            if not isinstance(self.type, XsdSimpleType):
                self.type = self.any_simple_type
                self.parse_error("XSD attribute's type must be a simpleType")

        # Check value constraints
        if 'default' in attrib:
            self.default = attrib['default']
            if 'fixed' in attrib:
                self.parse_error("'default' and 'fixed' attributes are mutually exclusive")

            if self.use != 'optional':
                self.parse_error("the attribute 'use' must be 'optional' "
                                 "if the attribute 'default' is present")

            if not self.type.is_valid(self.default):
                msg = "default value {!r} is not compatible with attribute's type"
                self.parse_error(msg.format(self.default))
            elif self.type.is_key() and self.xsd_version == '1.0':
                self.parse_error("xs:ID key attributes cannot have a default value")

        elif 'fixed' in attrib:
            self.fixed = attrib['fixed']
            if not self.type.is_valid(self.fixed):
                msg = "fixed value {!r} is not compatible with attribute's type"
                self.parse_error(msg.format(self.fixed))
            elif self.type.is_key() and self.xsd_version == '1.0':
                self.parse_error("xs:ID key attributes cannot have a fixed value")

    @property
    def built(self):
        return True

    @property
    def validation_attempted(self):
        return 'full'

    @property
    def scope(self):
        """The scope of the attribute declaration that can be 'global' or 'local'."""
        return 'global' if self.parent is None else 'local'

    @property
    def value_constraint(self):
        """The fixed or the default value if either is defined, `None` otherwise."""
        return self.fixed if self.fixed is not None else self.default

    def is_optional(self):
        return self.use == 'optional'

    def is_required(self):
        return self.use == 'required'

    def is_prohibited(self):
        return self.use == 'prohibited'

    def iter_components(self, xsd_classes=None):
        if xsd_classes is None or isinstance(self, xsd_classes):
            yield self
        if self.ref is None and self.type.parent is not None:
            yield from self.type.iter_components(xsd_classes)

    def data_value(self, text):
        """Returns the decoded data value of the provided text as XPath fn:data()."""
        return self.decode(text, validation='skip')

    def iter_decode(self, text, validation='lax', **kwargs):
        if text is None and self.default is not None:
            text = self.default

        if self.type.is_notation():
            if self.type.name == XSD_NOTATION_TYPE:
                msg = "cannot validate against xs:NOTATION directly, " \
                      "only against a subtype with an enumeration facet"
                yield self.validation_error(validation, msg, text, **kwargs)
            elif not self.type.enumeration:
                msg = "missing enumeration facet in xs:NOTATION subtype"
                yield self.validation_error(validation, msg, text, **kwargs)

        if self.fixed is not None:
            if text is None:
                text = self.fixed
            elif text != self.fixed and \
                    self.type.text_decode(text) != self.type.text_decode(self.fixed):
                msg = "attribute {!r} has a fixed value {!r}".format(self.name, self.fixed)
                yield self.validation_error(validation, msg, text, **kwargs)

        for value in self.type.iter_decode(text, validation, **kwargs):
            if isinstance(value, XMLSchemaValidationError):
                value.reason = 'attribute {}={!r}: {}'.format(
                    self.prefixed_name, text, value.reason
                )
                yield value
                continue
            elif isinstance(value, (int, float, list)) or value is None:
                yield value
            elif isinstance(value, str):
                if value.startswith('{') and self.type.is_qname():
                    yield text
                else:
                    yield value
            elif isinstance(value, Decimal):
                try:
                    yield kwargs['decimal_type'](value)
                except (KeyError, TypeError):
                    yield value
            elif isinstance(value, (AbstractDateTime, Duration)):
                yield value if kwargs.get('datetime_types') else text
            elif isinstance(value, AbstractBinary) and not kwargs.get('binary_types'):
                yield text
            else:
                yield value
            break

    def iter_encode(self, obj, validation='lax', **kwargs):
        for result in self.type.iter_encode(obj, validation):
            yield result
            if not isinstance(result, XMLSchemaValidationError):
                return


class Xsd11Attribute(XsdAttribute):
    """
    Class for XSD 1.1 *attribute* declarations.

    ..  <attribute
          default = string
          fixed = string
          form = (qualified | unqualified)
          id = ID
          name = NCName
          ref = QName
          targetNamespace = anyURI
          type = QName
          use = (optional | prohibited | required) : optional
          inheritable = boolean
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?, simpleType?)
        </attribute>
    """
    _target_namespace = None

    @property
    def target_namespace(self):
        if self._target_namespace is not None:
            return self._target_namespace
        elif self.ref is not None:
            return self.ref.target_namespace
        else:
            return self.schema.target_namespace

    def _parse(self):
        super(Xsd11Attribute, self)._parse()
        if self.use == 'prohibited' and 'fixed' in self.elem.attrib:
            self.parse_error("attribute 'fixed' with use=prohibited is not allowed in XSD 1.1")
        if 'inheritable' in self.elem.attrib:
            if self.elem.attrib['inheritable'].strip() in {'true', '1'}:
                self.inheritable = True
        self._parse_target_namespace()


class XsdAttributeGroup(MutableMapping, XsdComponent, ValidationMixin):
    """
    Class for XSD *attributeGroup* definitions.

    .. <attributeGroup
          id = ID
          name = NCName
          ref = QName
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?, ((attribute | attributeGroup)*, anyAttribute?))
        </attributeGroup>
    """
    _ADMITTED_TAGS = {
        XSD_ATTRIBUTE_GROUP, XSD_COMPLEX_TYPE, XSD_RESTRICTION, XSD_EXTENSION,
        XSD_SEQUENCE, XSD_ALL, XSD_CHOICE, XSD_ATTRIBUTE, XSD_ANY_ATTRIBUTE
    }

    def __init__(self, elem, schema, parent, derivation=None, base_attributes=None):
        self.derivation = derivation
        self._attribute_group: Dict[str, Union[XsdAttribute, XsdAnyAttribute]] = {}
        self.base_attributes = base_attributes
        XsdComponent.__init__(self, elem, schema, parent)

    def __repr__(self):
        if self.ref is not None:
            return '%s(ref=%r)' % (self.__class__.__name__, self.name)
        elif self.name is not None:
            return '%s(name=%r)' % (self.__class__.__name__, self.name)
        elif self:
            names = [a if a.name is None else a.name for a in self.values()]
            return '%s(%r)' % (self.__class__.__name__, names)
        else:
            return '%s()' % self.__class__.__name__

    # Implementation of abstract methods
    def __getitem__(self, key):
        return self._attribute_group[key]

    def __setitem__(self, key, value: Union[XsdAttribute, XsdAnyAttribute]):
        if key is None:
            self._attribute_group[key] = value
        else:
            if key[0] != '{':
                if value.local_name != key:
                    raise XMLSchemaValueError("%r name and key %r mismatch." % (value.name, key))
                if value.target_namespace != self.target_namespace:
                    # Qualify attributes of other namespaces
                    key = value.qualified_name
            elif value.qualified_name != key:
                raise XMLSchemaValueError("%r name and key %r mismatch." % (value.name, key))

            self._attribute_group[key] = value

    def __delitem__(self, key):
        del self._attribute_group[key]

    def __iter__(self):
        if None in self._attribute_group:
            # Put AnyAttribute ('None' key) at the end of iteration
            return iter(sorted(self._attribute_group, key=lambda x: (x is None, x)))
        else:
            return iter(self._attribute_group)

    def __len__(self):
        return len(self._attribute_group)

    def _parse(self):
        super(XsdAttributeGroup, self)._parse()
        any_attribute = None
        attribute_group_refs = []

        if self.elem.tag == XSD_ATTRIBUTE_GROUP:
            if self.parent is not None:
                return  # Skip dummy definitions
            try:
                self.name = get_qname(self.target_namespace, self.elem.attrib['name'])
            except KeyError:
                self.parse_error("an attribute group declaration requires a 'name' attribute.")
                return
            else:
                if self.schema.default_attributes == self.name and self.xsd_version > '1.0':
                    self.schema.default_attributes = self

        attributes: Dict[Optional[str], Union[XsdAttribute, XsdAnyAttribute]] = {}

        for child in self.elem:
            if child.tag == XSD_ANNOTATION or callable(child.tag):
                continue
            elif any_attribute is not None:
                if child.tag == XSD_ANY_ATTRIBUTE:
                    self.parse_error("more anyAttribute declarations in the same attribute group")
                elif child.tag != XSD_ASSERT:
                    self.parse_error("another declaration after anyAttribute")

            elif child.tag == XSD_ANY_ATTRIBUTE:
                any_attribute = self.schema.BUILDERS.any_attribute_class(child, self.schema, self)
                if None in attributes:
                    attributes[None] = attributes[None].copy()
                    attributes[None].intersection(any_attribute)
                else:
                    attributes[None] = any_attribute

            elif child.tag == XSD_ATTRIBUTE:
                try:
                    attribute = self.schema.BUILDERS.attribute_class(child, self.schema, self)
                except TypeError as err:
                    self.parse_error(err, elem=child)
                else:
                    if attribute.name in attributes:
                        self.parse_error("multiple declaration for attribute "
                                         "{!r}".format(attribute.name))
                    elif attribute.use != 'prohibited' or self.elem.tag != XSD_ATTRIBUTE_GROUP:
                        attributes[attribute.name] = attribute

            elif child.tag == XSD_ATTRIBUTE_GROUP:
                try:
                    ref = child.attrib['ref']
                except KeyError:
                    self.parse_error("the attribute 'ref' is required "
                                     "in a local attributeGroup")
                    continue

                try:
                    attribute_group_qname = self.schema.resolve_qname(ref)
                except (KeyError, ValueError, RuntimeError) as err:
                    self.parse_error(err)
                else:
                    if attribute_group_qname in attribute_group_refs:
                        self.parse_error("duplicated attributeGroup %r" % ref)
                    elif self.redefine is not None:
                        if attribute_group_qname == self.name:
                            if attribute_group_refs:
                                self.parse_error("in a redefinition the reference "
                                                 "to itself must be the first")
                            attribute_group_refs.append(attribute_group_qname)
                            attributes.update(self._attribute_group.items())
                            continue
                        elif not attribute_group_refs:
                            # May be an attributeGroup restriction with a ref to another group
                            if not any(e.tag == XSD_ATTRIBUTE_GROUP and ref == e.get('ref')
                                       for e in self.redefine.elem):
                                self.parse_error("attributeGroup ref=%r is not "
                                                 "in the redefined group" % ref)
                    elif attribute_group_qname == self.name and self.xsd_version == '1.0':
                        self.parse_error("Circular attribute groups not allowed in XSD 1.0")
                    attribute_group_refs.append(attribute_group_qname)

                    try:
                        base_attrs = self.maps.lookup_attribute_group(attribute_group_qname)
                    except LookupError:
                        self.parse_error("unknown attribute group %r" % child.attrib['ref'])
                    else:
                        if not isinstance(base_attrs, tuple):
                            for name, attr in base_attrs.items():
                                if name not in attributes:
                                    attributes[name] = attr
                                elif name is not None:
                                    self.parse_error("multiple declaration for attribute "
                                                     "{!r}".format(name))
                                else:
                                    attributes[None] = attributes[None].copy()
                                    attributes[None].intersection(attr)

                        elif self.xsd_version == '1.0':
                            self.parse_error(
                                "Circular reference found between attribute groups "
                                "{!r} and {!r}".format(self.name, attribute_group_qname)
                            )

            elif self.name is not None:
                self.parse_error("(attribute | attributeGroup) expected, found %r." % child)

        # Check and copy base attributes
        if self.base_attributes is not None:
            wildcard = self.base_attributes.get(None)
            for name, attr in attributes.items():
                if name not in self.base_attributes:
                    if self.derivation != 'restriction':
                        continue
                    elif wildcard is None or not wildcard.is_matching(name, self.default_namespace):
                        self.parse_error("Unexpected attribute %r in restriction" % name)
                    continue

                base_attr = self.base_attributes[name]

                if name is None:
                    if self.derivation == 'extension':
                        try:
                            attr.union(base_attr)
                        except ValueError as err:
                            self.parse_error(err)
                    elif not attr.is_restriction(base_attr):
                        self.parse_error("Attribute wildcard is not a restriction "
                                         "of the base wildcard")
                    continue
                if self.derivation == 'restriction' and attr.type.name != XSD_ANY_SIMPLE_TYPE and \
                        not attr.type.is_derived(base_attr.type, 'restriction'):
                    self.parse_error("Attribute type is not a restriction "
                                     "of the base attribute type")
                if base_attr.use != 'optional' and attr.use == 'optional' or \
                        base_attr.use == 'required' and attr.use != 'required':
                    self.parse_error("Attribute %r: unmatched attribute use in restriction" % name)
                if base_attr.fixed is not None and \
                        attr.type.normalize(attr.fixed) != \
                        base_attr.type.normalize(base_attr.fixed):
                    self.parse_error("Attribute %r: derived attribute "
                                     "has a different fixed value" % name)
                if base_attr.inheritable is not attr.inheritable:
                    msg = "Attribute %r: attribute 'inheritable' value change in restriction"
                    self.parse_error(msg % name)

            if self.redefine is not None:
                pass  # In case of redefinition do not copy base attributes
            else:
                self._attribute_group.update(self.base_attributes.items())

        elif self.redefine is not None and not attribute_group_refs:
            for name, attr in self._attribute_group.items():
                if name is None:
                    continue
                elif name not in attributes:
                    if attr.use == 'required':
                        self.parse_error("Missing required attribute %r in "
                                         "redefinition restriction" % name)
                    continue
                if attr.use != 'optional' and attributes[name].use != attr.use:
                    self.parse_error("Attribute %r: unmatched attribute use in redefinition" % name)
                if attr.fixed is not None and attributes[name].fixed is None:
                    self.parse_error("Attribute %r: redefinition remove fixed constraint" % name)

            pos = 0
            keys = list(self._attribute_group.keys())
            for name in attributes:
                try:
                    next_pos = keys.index(name)
                except ValueError:
                    self.parse_error("Redefinition restriction contains "
                                     "additional attribute %r" % name)
                else:
                    if next_pos < pos:
                        self.parse_error("Wrong attribute order in redefinition restriction")
                        break
                    pos = next_pos
            self.clear()

        self._attribute_group.update(attributes)
        if None in self._attribute_group and None not in attributes \
                and self.derivation == 'restriction':
            wildcard = self._attribute_group[None].copy()
            wildcard.namespace = wildcard.not_namespace = wildcard.not_qname = ()
            self._attribute_group[None] = wildcard

        if self.xsd_version == '1.0':
            has_key = False
            for attr in self._attribute_group.values():
                if attr.name and attr.type.is_key():
                    if has_key:
                        self.parse_error("multiple ID attributes not allowed for XSD 1.0")
                        break
                    has_key = True

        elif self.parent is None and self.schema.default_attributes == self.name:
            self.schema.default_attributes = self

    @property
    def built(self):
        return True

    def parse_error(self, error, elem=None, validation=None):
        if self.parent is None:
            super(XsdAttributeGroup, self).parse_error(error, elem, validation)
        else:
            self.parent.parse_error(error, elem, validation)

    def iter_required(self):
        for k, v in self._attribute_group.items():
            if k is not None and v.use == 'required':
                yield k

    def iter_value_constraints(self, use_defaults=True):
        if use_defaults:
            for k, v in self._attribute_group.items():
                if not k:
                    continue
                elif v.fixed is not None:
                    yield k, v.fixed
                elif v.default is not None:
                    yield k, v.default
        else:
            for k, v in self._attribute_group.items():
                if k and v.fixed is not None:
                    yield k, v.fixed

    def iter_components(self, xsd_classes=None):
        if xsd_classes is None or isinstance(self, xsd_classes):
            yield self
        if self.ref is None:
            for attr in self.values():
                if attr.parent is not None:
                    yield from attr.iter_components(xsd_classes)

    def iter_decode(self, attrs, validation='lax', **kwargs):
        if not attrs and not self:
            return

        for name in filter(lambda x: x not in attrs, self.iter_required()):
            reason = "missing required attribute {!r}".format(name)
            yield self.validation_error(validation, reason, attrs, **kwargs)

        kwargs['level'] = kwargs.get('level', 0) + 1
        try:
            use_defaults = kwargs['use_defaults']
        except KeyError:
            use_defaults = True

        additional_attrs = [
            (k, v) for k, v in self.iter_value_constraints(use_defaults) if k not in attrs
        ]
        if additional_attrs:
            attrs = {k: v for k, v in attrs.items()}
            attrs.update(additional_attrs)

        if self.xsd_version == '1.0':
            kwargs['id_list'] = []

        filler = kwargs.get('filler')
        result_list = []
        for name, value in attrs.items():
            try:
                xsd_attribute = self[name]
            except KeyError:
                if get_namespace(name) == XSI_NAMESPACE:
                    try:
                        xsd_attribute = self.maps.lookup_attribute(name)
                    except LookupError:
                        try:
                            xsd_attribute = self[None]  # None key ==> anyAttribute
                            value = (name, value)
                        except KeyError:
                            reason = "%r is not an attribute of the XSI namespace." % name
                            yield self.validation_error(validation, reason, attrs, **kwargs)
                            continue
                else:
                    try:
                        xsd_attribute = self[None]  # None key ==> anyAttribute
                        value = (name, value)
                    except KeyError:
                        reason = "%r attribute not allowed for element." % name
                        yield self.validation_error(validation, reason, attrs, **kwargs)
                        continue
            else:
                if xsd_attribute.use == 'prohibited' and \
                        (None not in self or not self[None].is_matching(name)):
                    reason = "use of attribute %r is prohibited" % name
                    yield self.validation_error(validation, reason, attrs, **kwargs)

            for result in xsd_attribute.iter_decode(value, validation, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    yield result
                elif result is None and filler is not None:
                    result_list.append((name, filler(xsd_attribute)))
                    break
                else:
                    result_list.append((name, result))
                    break

        if kwargs.get('fill_missing'):
            if filler is None:
                result_list.extend((k, None) for k in self._attribute_group
                                   if k is not None and k not in attrs)
            else:
                result_list.extend((k, filler(v)) for k, v in self._attribute_group.items()
                                   if k is not None and k not in attrs)

        yield result_list

    def iter_encode(self, attrs, validation='lax', **kwargs):
        if not attrs and not self:
            return

        for name in filter(lambda x: x not in attrs, self.iter_required()):
            reason = "missing required attribute {!r}".format(name)
            yield self.validation_error(validation, reason, attrs, **kwargs)

        try:
            use_defaults = kwargs['use_defaults']
        except KeyError:
            use_defaults = True

        result_list = []
        for name, value in attrs.items():
            try:
                xsd_attribute = self[name]
            except KeyError:
                namespace = get_namespace(name) or self.target_namespace
                if namespace == XSI_NAMESPACE:
                    try:
                        xsd_attribute = self.maps.lookup_attribute(name)
                    except LookupError:
                        try:
                            xsd_attribute = self[None]  # None key ==> anyAttribute
                            value = (name, value)
                        except KeyError:
                            reason = "%r is not an attribute of the XSI namespace." % name
                            yield self.validation_error(validation, reason, attrs, **kwargs)
                            continue
                else:
                    try:
                        xsd_attribute = self[None]  # None key ==> anyAttribute
                        value = (name, value)
                    except KeyError:
                        reason = "%r attribute not allowed for element." % name
                        yield self.validation_error(validation, reason, attrs, **kwargs)
                        continue

            for result in xsd_attribute.iter_encode(value, validation, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    yield result
                else:
                    if result is not None:
                        result_list.append((name, result))
                    break

        result_list.extend(
            (k, v) for k, v in self.iter_value_constraints(use_defaults) if k not in attrs
        )
        yield result_list
