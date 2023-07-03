#
# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from typing import TYPE_CHECKING, Any, Optional, cast, Iterable, Union, Callable
from elementpath.etree import etree_tostring

from ..exceptions import XMLSchemaException, XMLSchemaWarning, XMLSchemaValueError
from ..aliases import ElementType, NamespacesType, SchemaElementType, ModelParticleType
from ..helpers import get_prefixed_qname, etree_getpath, is_etree_element
from ..translation import gettext as _

if TYPE_CHECKING:
    from ..resources import XMLResource
    from .xsdbase import XsdValidator
    from .groups import XsdGroup

ValidatorType = Union['XsdValidator', Callable[[Any], None]]


class XMLSchemaValidatorError(XMLSchemaException):
    """
    Base class for XSD validator errors.

    :param validator: the XSD validator.
    :param message: the error message.
    :param elem: the element that contains the error.
    :param source: the XML resource that contains the error.
    :param namespaces: is an optional mapping from namespace prefix to URI.
    """
    _path: Optional[str]

    def __init__(self, validator: ValidatorType,
                 message: str,
                 elem: Optional[ElementType] = None,
                 source: Optional['XMLResource'] = None,
                 namespaces: Optional[NamespacesType] = None) -> None:
        self._path = None
        self.validator = validator
        self.message = message[:-1] if message[-1] in ('.', ':') else message
        self.namespaces = namespaces
        self.source = source
        self.elem = elem

    def __str__(self) -> str:
        if self.elem is None:
            return self.message

        msg = ['%s:\n' % self.message]
        elem_as_string = cast(str, etree_tostring(self.elem, self.namespaces, '  ', 20))
        msg.append("Schema:\n\n%s\n" % elem_as_string)

        path = self.path
        if path is not None:
            msg.append("Path: %s\n" % path)
        if self.schema_url is not None:
            msg.append("Schema URL: %s\n" % self.schema_url)
            if self.origin_url not in (None, self.schema_url):
                msg.append("Origin URL: %s\n" % self.origin_url)
        return '\n'.join(msg)

    @property
    def msg(self) -> str:
        return self.__str__()

    def __setattr__(self, name: str, value: Any) -> None:
        if name == 'elem' and value is not None:
            if not is_etree_element(value):
                raise XMLSchemaValueError(
                    "'elem' attribute requires an Element, not %r." % type(value)
                )
            if self.source is not None:
                self._path = etree_getpath(
                    elem=value,
                    root=self.source.root,
                    namespaces=self.namespaces,
                    relative=False,
                    add_position=True
                )
                if self.source.is_lazy():
                    value = None  # Don't save the element of a lazy resource
        super(XMLSchemaValidatorError, self).__setattr__(name, value)

    @property
    def sourceline(self) -> Any:
        """XML element *sourceline* if available (lxml Element) and *elem* is set."""
        return getattr(self.elem, 'sourceline', None)

    @property
    def root(self) -> Optional[ElementType]:
        """The XML resource root element if *source* is set."""
        try:
            return self.source.root  # type: ignore[union-attr]
        except AttributeError:
            return None

    @property
    def schema_url(self) -> Optional[str]:
        """The schema URL, if available and the *validator* is an XSD component."""
        url: Optional[str]
        try:
            url = self.validator.schema.source.url  # type: ignore[union-attr]
        except AttributeError:
            return None
        else:
            return url

    @property
    def origin_url(self) -> Optional[str]:
        """The origin schema URL, if available and the *validator* is an XSD component."""
        url: Optional[str]
        try:
            url = self.validator.maps.validator.source.url  # type: ignore[union-attr]
        except AttributeError:
            return None
        else:
            return url

    @property
    def path(self) -> Optional[str]:
        """The XPath of the element, if it's not `None` and the XML resource is set."""
        if self.elem is None or self.source is None:
            return self._path

        return etree_getpath(
            elem=self.elem,
            root=self.source.root,
            namespaces=self.namespaces,
            relative=False,
            add_position=True
        )


class XMLSchemaNotBuiltError(XMLSchemaValidatorError, RuntimeError):
    """
    Raised when there is an improper usage attempt of a not built XSD validator.

    :param validator: the XSD validator.
    :param message: the error message.
    """
    def __init__(self, validator: 'XsdValidator', message: str) -> None:
        super(XMLSchemaNotBuiltError, self).__init__(
            validator=validator,
            message=message,
            elem=getattr(validator, 'elem', None),
            source=getattr(validator, 'source', None),
            namespaces=getattr(validator, 'namespaces', None)
        )


class XMLSchemaParseError(XMLSchemaValidatorError, SyntaxError):  # type: ignore[misc]
    """
    Raised when an error is found during the building of an XSD validator.

    :param validator: the XSD validator.
    :param message: the error message.
    :param elem: the element that contains the error.
    """
    def __init__(self, validator: 'XsdValidator', message: str,
                 elem: Optional[ElementType] = None) -> None:
        super(XMLSchemaParseError, self).__init__(
            validator=validator,
            message=message,
            elem=elem if elem is not None else getattr(validator, 'elem', None),
            source=getattr(validator, 'source', None),
            namespaces=getattr(validator, 'namespaces', None),
        )


class XMLSchemaModelError(XMLSchemaValidatorError, ValueError):
    """
    Raised when a model error is found during the checking of a model group.

    :param group: the XSD model group.
    :param message: the error message.
    """
    def __init__(self, group: 'XsdGroup', message: str) -> None:
        super(XMLSchemaModelError, self).__init__(
            validator=group,
            message=message,
            elem=getattr(group, 'elem', None),
            source=getattr(group, 'source', None),
            namespaces=getattr(group, 'namespaces', None)
        )


class XMLSchemaModelDepthError(XMLSchemaModelError):
    """Raised when recursion depth is exceeded while iterating a model group."""
    def __init__(self, group: 'XsdGroup') -> None:
        msg = "maximum model recursion depth exceeded while iterating {!r}".format(group)
        super(XMLSchemaModelDepthError, self).__init__(group, message=msg)


class XMLSchemaValidationError(XMLSchemaValidatorError, ValueError):
    """
    Raised when the XML data is not validated with the XSD component or schema.
    It's used by decoding and encoding methods. Encoding validation errors do
    not include XML data element and source, so the error is limited to a message
    containing object representation and a reason.

    :param validator: the XSD validator.
    :param obj: the not validated XML data.
    :param reason: the detailed reason of failed validation.
    :param source: the XML resource that contains the error.
    :param namespaces: is an optional mapping from namespace prefix to URI.
    """
    def __init__(self,
                 validator: ValidatorType,
                 obj: Any,
                 reason: Optional[str] = None,
                 source: Optional['XMLResource'] = None,
                 namespaces: Optional[NamespacesType] = None) -> None:
        if not isinstance(obj, str):
            _obj = obj
        else:
            _obj = obj.encode('ascii', 'xmlcharrefreplace').decode('utf-8')

        super(XMLSchemaValidationError, self).__init__(
            validator=validator,
            message="failed validating {!r} with {!r}".format(_obj, validator),
            elem=obj if is_etree_element(obj) else None,
            source=source,
            namespaces=namespaces,
        )
        self.obj = obj
        self.reason = reason

    def __repr__(self) -> str:
        return '%s(reason=%r)' % (self.__class__.__name__, self.reason)

    def __str__(self) -> str:
        msg = ['%s:\n' % self.message]

        if self.reason is not None:
            msg.append('Reason: %s\n' % self.reason)

        if hasattr(self.validator, 'tostring'):
            chunk = self.validator.tostring('  ', 20)
            msg.append("Schema:\n\n%s\n" % chunk)

        if self.elem is not None and is_etree_element(self.elem):
            try:
                elem_as_string = cast(str, etree_tostring(self.elem, self.namespaces, '  ', 20))
            except (ValueError, TypeError):        # pragma: no cover
                elem_as_string = repr(self.elem)   # pragma: no cover

            if hasattr(self.elem, 'sourceline'):
                line = getattr(self.elem, 'sourceline')
                msg.append("Instance (line %r):\n\n%s\n" % (line, elem_as_string))
            else:
                msg.append("Instance:\n\n%s\n" % elem_as_string)

        if self.path is not None:
            msg.append("Path: %s\n" % self.path)

        if len(msg) == 1:
            return msg[0][:-2]

        return '\n'.join(msg)


class XMLSchemaDecodeError(XMLSchemaValidationError):
    """
    Raised when an XML data string is not decodable to a Python object.

    :param validator: the XSD validator.
    :param obj: the not validated XML data.
    :param decoder: the XML data decoder.
    :param reason: the detailed reason of failed validation.
    :param source: the XML resource that contains the error.
    :param namespaces: is an optional mapping from namespace prefix to URI.
    """
    message = "failed decoding {!r} with {!r}.\n"

    def __init__(self, validator: Union['XsdValidator', Callable[[Any], None]],
                 obj: Any,
                 decoder: Any,
                 reason: Optional[str] = None,
                 source: Optional['XMLResource'] = None,
                 namespaces: Optional[NamespacesType] = None) -> None:
        super(XMLSchemaDecodeError, self).__init__(validator, obj, reason, source, namespaces)
        self.decoder = decoder


class XMLSchemaEncodeError(XMLSchemaValidationError):
    """
    Raised when an object is not encodable to an XML data string.

    :param validator: the XSD validator.
    :param obj: the not validated XML data.
    :param encoder: the XML encoder.
    :param reason: the detailed reason of failed validation.
    :param source: the XML resource that contains the error.
    :param namespaces: is an optional mapping from namespace prefix to URI.
    """
    message = "failed encoding {!r} with {!r}.\n"

    def __init__(self, validator: Union['XsdValidator', Callable[[Any], None]],
                 obj: Any,
                 encoder: Any,
                 reason: Optional[str] = None,
                 source: Optional['XMLResource'] = None,
                 namespaces: Optional[NamespacesType] = None) -> None:
        super(XMLSchemaEncodeError, self).__init__(validator, obj, reason, source, namespaces)
        self.encoder = encoder


class XMLSchemaChildrenValidationError(XMLSchemaValidationError):
    """
    Raised when a child element is not validated.

    :param validator: the XSD validator.
    :param elem: the not validated XML element.
    :param index: the child index.
    :param particle: the model particle that generated the error. Maybe the validator itself.
    :param occurs: the particle occurrences.
    :param expected: the expected element tags/object names.
    :param source: the XML resource that contains the error.
    :param namespaces: is an optional mapping from namespace prefix to URI.
    """
    def __init__(self, validator: 'XsdValidator',
                 elem: ElementType,
                 index: int,
                 particle: ModelParticleType,
                 occurs: int = 0,
                 expected: Optional[Iterable[SchemaElementType]] = None,
                 source: Optional['XMLResource'] = None,
                 namespaces: Optional[NamespacesType] = None) -> None:

        self.index = index
        self.particle = particle
        self.occurs = occurs
        self.expected = expected

        tag = get_prefixed_qname(elem.tag, validator.namespaces, use_empty=False)
        if index >= len(elem):
            reason = _("The content of element %r is not complete.") % tag
        else:
            child_tag = get_prefixed_qname(elem[index].tag, validator.namespaces, use_empty=False)
            reason = _("Unexpected child with tag %r at position %d.") % (child_tag, index + 1)

        if occurs and particle.is_missing(occurs):
            reason += " The particle %r occurs %d times but the minimum is %d." % (
                particle, occurs, particle.min_occurs
            )
        elif particle.is_over(occurs):
            reason += " The particle %r occurs %r times but the maximum is %r." % (
                particle, occurs, particle.max_occurs
            )

        if expected is None:
            pass
        else:
            expected_tags = []
            for xsd_element in expected:
                name = xsd_element.prefixed_name
                if name is not None:
                    expected_tags.append(name)
                elif getattr(xsd_element, 'process_contents', '') == 'strict':
                    expected_tags.append(
                        'from %r namespace/s' % xsd_element.namespace  # type: ignore[union-attr]
                    )

            if not expected_tags:
                pass
            elif len(expected_tags) > 1:
                reason += _(" Tag (%s) expected.") % ' | '.join(repr(tag) for tag in expected_tags)
            elif expected_tags[0].startswith('from '):
                reason += _(" Tag %s expected.") % expected_tags[0]
            else:
                reason += _(" Tag %r expected.") % expected_tags[0]

        super(XMLSchemaChildrenValidationError, self).\
            __init__(validator, elem, reason, source, namespaces)


class XMLSchemaIncludeWarning(XMLSchemaWarning):
    """A schema include fails."""


class XMLSchemaImportWarning(XMLSchemaWarning):
    """A schema namespace import fails."""


class XMLSchemaTypeTableWarning(XMLSchemaWarning):
    """Not equivalent type table found in model."""
