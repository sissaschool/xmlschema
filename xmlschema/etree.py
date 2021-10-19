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
A unified setup module for ElementTree with a safe parser and helper functions.
"""
import sys
import re
from collections import namedtuple
from typing import Any, MutableMapping, Optional, Union

from .exceptions import XMLSchemaTypeError

_REGEX_NS_PREFIX = re.compile(r'ns\d+$')

###
# Programmatic import of xml.etree.ElementTree
#
# In Python 3 the pure python implementation is overwritten by the C module API,
# so use a programmatic re-import to obtain the pure Python module, necessary for
# defining a safer XMLParser.
#
if '_elementtree' in sys.modules:
    if 'xml.etree.ElementTree' not in sys.modules:
        raise RuntimeError("Inconsistent status for ElementTree module: module "
                           "is missing but the C optimized version is imported.")

    import xml.etree.ElementTree as ElementTree

    # Temporary remove the loaded modules
    sys.modules.pop('xml.etree.ElementTree')
    _cmod = sys.modules.pop('_elementtree')

    # Load the pure Python module
    sys.modules['_elementtree'] = None  # type: ignore[assignment]
    import xml.etree.ElementTree as PyElementTree
    import xml.etree

    # Restore original modules
    sys.modules['_elementtree'] = _cmod
    xml.etree.ElementTree = ElementTree
    sys.modules['xml.etree.ElementTree'] = ElementTree

else:
    # Load the pure Python module
    sys.modules['_elementtree'] = None  # type: ignore[assignment]
    import xml.etree.ElementTree as PyElementTree

    # Remove the pure Python module from imported modules
    del sys.modules['xml.etree']
    del sys.modules['xml.etree.ElementTree']
    del sys.modules['_elementtree']

    # Load the C optimized ElementTree module
    import xml.etree.ElementTree as ElementTree


etree_element = ElementTree.Element
ParseError = ElementTree.ParseError
py_etree_element = PyElementTree.Element


class SafeXMLParser(PyElementTree.XMLParser):
    """
    An XMLParser that forbids entities processing. Drops the *html* argument
    that is deprecated since version 3.4.

    :param target: the target object called by the `feed()` method of the \
    parser, that defaults to `TreeBuilder`.
    :param encoding: if provided, its value overrides the encoding specified \
    in the XML file.
    """
    def __init__(self, target: Optional[Any] = None, encoding: Optional[str] = None) -> None:
        super(SafeXMLParser, self).__init__(target=target, encoding=encoding)
        self.parser.EntityDeclHandler = self.entity_declaration
        self.parser.UnparsedEntityDeclHandler = self.unparsed_entity_declaration
        self.parser.ExternalEntityRefHandler = self.external_entity_reference

    def entity_declaration(self, entity_name, is_parameter_entity, value, base,  # type: ignore
                           system_id, public_id, notation_name):
        raise PyElementTree.ParseError(
            "Entities are forbidden (entity_name={!r})".format(entity_name)
        )

    def unparsed_entity_declaration(self, entity_name, base, system_id,  # type: ignore
                                    public_id, notation_name):
        raise PyElementTree.ParseError(
            "Unparsed entities are forbidden (entity_name={!r})".format(entity_name)
        )

    def external_entity_reference(self, context, base, system_id, public_id):  # type: ignore
        raise PyElementTree.ParseError(
            "External references are forbidden (system_id={!r}, "
            "public_id={!r})".format(system_id, public_id)
        )  # pragma: no cover (EntityDeclHandler is called before)


ElementData = namedtuple('ElementData', ['tag', 'text', 'content', 'attributes'])
"""
Namedtuple for Element data interchange between decoders and converters.
The field *tag* is a string containing the Element's tag, *text* can be `None`
or a string representing the Element's text, *content* can be `None`, a list
containing the Element's children or a dictionary containing element name to
list of element contents for the Element's children (used for unordered input
data), *attributes* can be `None` or a dictionary containing the Element's
attributes.
"""


def is_etree_element(obj: Any) -> bool:
    """A checker for valid ElementTree elements that excludes XsdElement objects."""
    return hasattr(obj, 'append') and hasattr(obj, 'tag') and hasattr(obj, 'attrib')


def etree_tostring(elem: etree_element,
                   namespaces: Optional[MutableMapping[str, str]] = None,
                   indent: str = '',
                   max_lines: Optional[int] = None,
                   spaces_for_tab: Optional[int] = None,
                   xml_declaration: Optional[bool] = None,
                   encoding: str = 'unicode',
                   method: str = 'xml') -> Union[str, bytes]:
    """
    Serialize an Element tree to a string. Tab characters are replaced by whitespaces.

    :param elem: the Element instance.
    :param namespaces: is an optional mapping from namespace prefix to URI. \
    Provided namespaces are registered before serialization.
    :param indent: the base line indentation.
    :param max_lines: if truncate serialization after a number of lines \
    (default: do not truncate).
    :param spaces_for_tab: number of spaces for replacing tab characters. \
    For default tabs are replaced with 4 spaces, but only if not empty \
    indentation or a max lines limit are provided.
    :param xml_declaration: if set to `True` inserts the XML declaration at the head.
    :param encoding: if "unicode" (the default) the output is a string, otherwise it’s binary.
    :param method: is either "xml" (the default), "html" or "text".
    :return: a Unicode string.
    """
    def reindent(line: str) -> str:
        if not line:
            return line
        elif line.startswith(min_indent):
            return line[start:] if start >= 0 else indent[start:] + line
        else:
            return indent + line

    etree_module: Any
    if not is_etree_element(elem):
        raise XMLSchemaTypeError("{!r} is not an Element".format(elem))

    elif isinstance(elem, py_etree_element):
        etree_module = PyElementTree
    elif not hasattr(elem, 'nsmap'):
        etree_module = ElementTree
    else:
        import lxml.etree as etree_module  # type: ignore[no-redef]

    if namespaces:
        default_namespace = namespaces.get('')
        for prefix, uri in namespaces.items():
            if prefix and not _REGEX_NS_PREFIX.match(prefix):
                etree_module.register_namespace(prefix, uri)
                if uri == default_namespace:
                    default_namespace = None

        if default_namespace and not hasattr(elem, 'nsmap'):
            etree_module.register_namespace('', default_namespace)

    xml_text = etree_module.tostring(elem, encoding=encoding, method=method)
    if isinstance(xml_text, bytes):
        xml_text = xml_text.decode('utf-8')

    if spaces_for_tab:
        xml_text = xml_text.replace('\t', ' ' * spaces_for_tab)
    elif method != 'text' and (indent or max_lines):
        xml_text = xml_text.replace('\t', ' ' * 4)

    if xml_text.startswith('<?xml '):
        if xml_declaration is False:
            lines = xml_text.splitlines()[1:]
        else:
            lines = xml_text.splitlines()
    elif xml_declaration and encoding.lower() != 'unicode':
        lines = ['<?xml version="1.0" encoding="{}"?>'.format(encoding)]
        lines.extend(xml_text.splitlines())
    else:
        lines = xml_text.splitlines()

    # Clear ending empty lines
    while lines and not lines[-1].strip():
        lines.pop(-1)

    if not lines or method == 'text' or (not indent and not max_lines):
        if encoding == 'unicode':
            return '\n'.join(lines)
        return '\n'.join(lines).encode(encoding)

    last_indent = ' ' * min(k for k in range(len(lines[-1])) if lines[-1][k] != ' ')
    if len(lines) > 2:
        child_indent = ' ' * min(
            k for line in lines[1:-1] for k in range(len(line)) if line[k] != ' '
        )
        min_indent = min(child_indent, last_indent)
    else:
        min_indent = child_indent = last_indent

    start = len(min_indent) - len(indent)

    if max_lines is not None and len(lines) > max_lines + 2:
        lines = lines[:max_lines] + [child_indent + '...'] * 2 + lines[-1:]

    if encoding == 'unicode':
        return '\n'.join(reindent(line) for line in lines)
    return '\n'.join(reindent(line) for line in lines).encode(encoding)


__all__ = ['ElementTree', 'PyElementTree', 'ParseError', 'SafeXMLParser', 'etree_element',
           'py_etree_element', 'ElementData', 'is_etree_element', 'etree_tostring']
