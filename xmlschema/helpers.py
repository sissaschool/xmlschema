#
# Copyright (c), 2016-2021, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import re
from collections import Counter
from decimal import Decimal
from typing import Any, Callable, Iterator, List, MutableMapping, \
    Optional, Tuple, Union
from xml.etree.ElementTree import ParseError

from .exceptions import XMLSchemaValueError, XMLSchemaTypeError
from .names import XSI_SCHEMA_LOCATION, XSI_NONS_SCHEMA_LOCATION
from .aliases import ElementType, NamespacesType, AtomicValueType, NumericValueType

###
# Helper functions for QNames

NAMESPACE_PATTERN = re.compile(r'{([^}]*)}')


def get_namespace(qname: str, namespaces: Optional[NamespacesType] = None) -> str:
    """
    Returns the namespace URI associated with a QName. If a namespace map is
    provided tries to resolve a prefixed QName and then to extract the namespace.

    :param qname: an extended QName or a local name or a prefixed QName.
    :param namespaces: optional mapping from prefixes to namespace URIs.
    """
    if not qname:
        return ''
    elif qname[0] != '{':
        if namespaces is None:
            return ''
        qname = get_extended_qname(qname, namespaces)

    try:
        return NAMESPACE_PATTERN.match(qname).group(1)  # type: ignore[union-attr]
    except (AttributeError, TypeError):
        return ''


def get_qname(uri: Optional[str], name: str) -> str:
    """
    Returns an expanded QName from URI and local part. If any argument has boolean value
    `False` or if the name is already an expanded QName, returns the *name* argument.

    :param uri: namespace URI
    :param name: local or qualified name
    :return: string or the name argument
    """
    if not uri or not name or name[0] in '{./[':
        return name
    else:
        return f'{{{uri}}}{name}'


def local_name(qname: str) -> str:
    """
    Return the local part of an expanded QName or a prefixed name. If the name
    is `None` or empty returns the *name* argument.

    :param qname: an expanded QName or a prefixed name or a local name.
    """
    try:
        if qname[0] == '{':
            _namespace, qname = qname.split('}')
        elif ':' in qname:
            _prefix, qname = qname.split(':')
    except IndexError:
        return ''
    except ValueError:
        raise XMLSchemaValueError("the argument 'qname' has an invalid value %r" % qname)
    except TypeError:
        raise XMLSchemaTypeError("the argument 'qname' must be a string-like object")
    else:
        return qname


def get_prefixed_qname(qname: str,
                       namespaces: Optional[MutableMapping[str, str]],
                       use_empty: bool = True) -> str:
    """
    Get the prefixed form of a QName, using a namespace map.

    :param qname: an extended QName or a local name or a prefixed QName.
    :param namespaces: an optional mapping from prefixes to namespace URIs.
    :param use_empty: if `True` use the empty prefix for mapping.
    """
    if not namespaces or not qname or qname[0] != '{':
        return qname

    namespace = get_namespace(qname)
    prefixes = [x for x in namespaces if namespaces[x] == namespace]

    if not prefixes:
        return qname
    elif prefixes[0]:
        return f"{prefixes[0]}:{qname.split('}', 1)[1]}"
    elif len(prefixes) > 1:
        return f"{prefixes[1]}:{qname.split('}', 1)[1]}"
    elif use_empty:
        return qname.split('}', 1)[1]
    else:
        return qname


def get_extended_qname(qname: str, namespaces: Optional[MutableMapping[str, str]]) -> str:
    """
    Get the extended form of a QName, using a namespace map.
    Local names are mapped to the default namespace.

    :param qname: a prefixed QName or a local name or an extended QName.
    :param namespaces: an optional mapping from prefixes to namespace URIs.
    """
    if not namespaces:
        return qname

    try:
        if qname[0] == '{':
            return qname
    except IndexError:
        return qname

    try:
        prefix, name = qname.split(':', 1)
    except ValueError:
        if not namespaces.get(''):
            return qname
        else:
            return f"{{{namespaces['']}}}{qname}"
    else:
        try:
            uri = namespaces[prefix]
        except KeyError:
            return qname
        else:
            return f'{{{uri}}}{name}' if uri else name


###
# Helper functions for ElementTree structures

def is_etree_element(obj: object) -> bool:
    """A checker for valid ElementTree elements that excludes XsdElement objects."""
    return hasattr(obj, 'append') and hasattr(obj, 'tag') and hasattr(obj, 'attrib')


def is_etree_document(obj: object) -> bool:
    """A checker for valid ElementTree objects."""
    return hasattr(obj, 'getroot') and hasattr(obj, 'parse') and hasattr(obj, 'iter')


def etree_iterpath(elem: ElementType,
                   tag: Optional[str] = None,
                   path: str = '.',
                   namespaces: Optional[NamespacesType] = None,
                   add_position: bool = False) -> Iterator[Tuple[ElementType, str]]:
    """
    Creates an iterator for the element and its subelements that yield elements and paths.
    If tag is not `None` or '*', only elements whose matches tag are returned from the iterator.

    :param elem: the element to iterate.
    :param tag: tag filtering.
    :param path: the current path, '.' for default.
    :param namespaces: is an optional mapping from namespace prefix to URI.
    :param add_position: add context position to child elements that appear multiple times.
    """
    if tag == "*":
        tag = None
    if not path:
        path = '.'
    if tag is None or elem.tag == tag:
        yield elem, path

    if add_position:
        children_tags = Counter(e.tag for e in elem)
        positions = Counter(t for t in children_tags if children_tags[t] > 1)
    else:
        positions = Counter()

    for child in elem:
        if callable(child.tag):
            continue  # Skip comments and PIs

        child_name = child.tag if namespaces is None else get_prefixed_qname(child.tag, namespaces)
        if path == '/':
            child_path = f'/{child_name}'
        else:
            child_path = '/'.join((path, child_name))

        if child.tag in positions:
            child_path += '[%d]' % positions[child.tag]
            positions[child.tag] += 1

        yield from etree_iterpath(child, tag, child_path, namespaces, add_position)


def etree_getpath(elem: ElementType,
                  root: ElementType,
                  namespaces: Optional[NamespacesType] = None,
                  relative: bool = True,
                  add_position: bool = False,
                  parent_path: bool = False) -> Optional[str]:
    """
    Returns the XPath path from *root* to descendant *elem* element.

    :param elem: the descendant element.
    :param root: the root element.
    :param namespaces: an optional mapping from namespace prefix to URI.
    :param relative: returns a relative path.
    :param add_position: add context position to child elements that appear multiple times.
    :param parent_path: if set to `True` returns the parent path. Default is `False`.
    :return: An XPath expression or `None` if *elem* is not a descendant of *root*.
    """
    if relative:
        path = '.'
    elif namespaces:
        path = f'/{get_prefixed_qname(root.tag, namespaces)}'
    else:
        path = f'/{root.tag}'

    if not parent_path:
        for e, path in etree_iterpath(root, elem.tag, path, namespaces, add_position):
            if e is elem:
                return path
    else:
        for e, path in etree_iterpath(root, None, path, namespaces, add_position):
            if elem in e:
                return path
    return None


def etree_iter_location_hints(elem: ElementType) -> Iterator[Tuple[Any, Any]]:
    """Yields schema location hints contained in the attributes of an element."""
    if XSI_SCHEMA_LOCATION in elem.attrib:
        locations = elem.attrib[XSI_SCHEMA_LOCATION].split()
        for ns, url in zip(locations[0::2], locations[1::2]):
            yield ns, url

    if XSI_NONS_SCHEMA_LOCATION in elem.attrib:
        for url in elem.attrib[XSI_NONS_SCHEMA_LOCATION].split():
            yield '', url


def prune_etree(root: ElementType, selector: Callable[[ElementType], bool]) \
        -> Optional[bool]:
    """
    Removes from a tree structure the elements that verify the selector
    function. The checking and eventual removals are performed using a
    breadth-first visit method.

    :param root: the root element of the tree.
    :param selector: the single argument function to apply on each visited node.
    :return: `True` if the root node verify the selector function, `None` otherwise.
    """
    def _prune_subtree(elem: ElementType) -> None:
        for child in elem[:]:
            if selector(child):
                elem.remove(child)

        for child in elem:
            _prune_subtree(child)

    if selector(root):
        del root[:]
        return True
    _prune_subtree(root)
    return None


def count_digits(number: NumericValueType) -> Tuple[int, int]:
    """
    Counts the digits of a number.

    :param number: an int or a float or a Decimal or a string representing a number.
    :return: a couple with the number of digits of the integer part and \
    the number of digits of the decimal part.
    """
    if isinstance(number, str):
        number = str(Decimal(number)).lstrip('-+')
    elif isinstance(number, bytes):
        number = str(Decimal(number.decode())).lstrip('-+')
    else:
        number = str(number).lstrip('-+')

    if 'E' in number:
        significand, _, _exponent = number.partition('E')
    elif 'e' in number:
        significand, _, _exponent = number.partition('e')
    elif '.' not in number:
        return len(number.lstrip('0')), 0
    else:
        integer_part, _, decimal_part = number.partition('.')
        return len(integer_part.lstrip('0')), len(decimal_part.rstrip('0'))

    significand = significand.strip('0')
    exponent = int(_exponent)

    num_digits = len(significand) - 1 if '.' in significand else len(significand)
    if exponent > 0:
        return num_digits + exponent, 0
    else:
        return 0, num_digits - exponent - 1


def strictly_equal(obj1: object, obj2: object) -> bool:
    """Checks if the objects are equal and are of the same type."""
    return obj1 == obj2 and type(obj1) is type(obj2)


def raw_xml_encode(value: Union[None, AtomicValueType, List[AtomicValueType],
                                Tuple[AtomicValueType, ...]]) -> Optional[str]:
    """Encodes a simple value to XML."""
    if isinstance(value, bool):
        return 'true' if value else 'false'
    elif isinstance(value, (list, tuple)):
        return ' '.join(str(e) for e in value)
    else:
        return str(value) if value is not None else None


def is_defuse_error(err: Exception) -> bool:
    """
    Returns `True` if the error is related to defuse of XML data in the DTD
    of the source (forbid entities or external references), `False` otherwise.
    """
    if not isinstance(err, ParseError):
        return False

    msg = str(err)
    return "Entities are forbidden" in msg or \
        "Unparsed entities are forbidden" in msg or \
        "External references are forbidden" in msg
