#
# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import os
import warnings

from .exceptions import XMLSchemaException, XMLSchemaValueError
from .namespaces import XSD_NAMESPACE, WSDL_NAMESPACE, SCHEMAS_DIR, NamespaceResourcesMap
from .qnames import XSD_ANY_TYPE, XSD_SCHEMA, get_extended_qname
from .resources import is_remote_url, url_path_is_file, fetch_resource
from .documents import XmlDocument
from .validators import XMLSchema10, XMLSchemaImportWarning


# WSDL 1.1 global declarations
WSDL_IMPORT = '{%s}import' % WSDL_NAMESPACE
WSDL_TYPES = '{%s}types' % WSDL_NAMESPACE
WSDL_MESSAGE = '{%s}message' % WSDL_NAMESPACE
WSDL_PORT_TYPE = '{%s}portType' % WSDL_NAMESPACE
WSDL_BINDING = '{%s}binding' % WSDL_NAMESPACE
WSDL_SERVICE = '{%s}service' % WSDL_NAMESPACE

# Other WSDL tags
WSDL_PART = '{%s}part' % WSDL_NAMESPACE
WSDL_PORT = '{%s}port' % WSDL_NAMESPACE
WSDL_INPUT = '{%s}input' % WSDL_NAMESPACE
WSDL_OUTPUT = '{%s}output' % WSDL_NAMESPACE
WSDL_FAULT = '{%s}fault' % WSDL_NAMESPACE
WSDL_OPERATION = '{%s}operation' % WSDL_NAMESPACE


class WsdlParseError(XMLSchemaException, SyntaxError):
    """An error during parsing of a WSDL document."""


class Wsdl11Globals(object):

    def __init__(self, xsd_globals):
        self.namespaces = NamespaceResourcesMap()
        self.xsd_globals = xsd_globals
        self.messages = {}
        self.port_types = {}
        self.bindings = {}
        self.services = {}


class WsdlMessage(object):

    def __init__(self, elem, wsdl_document):
        self.name = elem.get('name')
        self.wsdl_document = wsdl_document

        self.parts = {}
        for child in elem.iterfind(WSDL_PART):
            part_name = child.get('name')
            if part_name is None:
                continue  # Ignore, missing name is already caught by XSD validator
            elif part_name in self.parts:
                msg = "duplicate part {!r} for {!r}"
                wsdl_document.parse_error(msg.format(part_name, self))

            try:
                element_attr = child.attrib['element']
            except KeyError:
                pass
            else:
                if 'type' in child.attrib:
                    msg = "ambiguous binding with both 'type' and 'element' attributes"
                    wsdl_document.parse_error(msg)

                element_name = get_extended_qname(element_attr, wsdl_document.namespaces)
                try:
                    self.parts[part_name] = wsdl_document.schema.maps.elements[element_name]
                except KeyError:
                    msg = "missing schema element {!r}".format(element_name)
                    wsdl_document.parse_error(msg)
                    self.parts[part_name] = wsdl_document.schema.maps.types[XSD_ANY_TYPE]

                continue

            try:
                type_attr = child.attrib['type']
            except KeyError:
                msg = "missing both 'type' and 'element' attributes"
                wsdl_document.parse_error(msg)
            else:
                type_name = get_extended_qname(type_attr, wsdl_document.namespaces)
                try:
                    self.parts[part_name] = wsdl_document.schema.maps.types[type_name]
                except KeyError:
                    msg = "missing schema type {!r}".format(type_name)
                    wsdl_document.parse_error(msg)
                    self.parts[part_name] = wsdl_document.schema.maps.types[XSD_ANY_TYPE]

    def __repr__(self):
        return '%s(name=%r)' % (self.__class__.__name__, self.name)


class Wsdl11Document(XmlDocument):

    def __init__(self, source, cls=None, validation='strict', namespaces=None, maps=None,
                 locations=None, base_url=None, allow='all', defuse='remote', timeout=300):

        self.schema = (cls or XMLSchema10)(os.path.join(SCHEMAS_DIR, 'WSDL/wsdl.xsd'))
        super(Wsdl11Document, self).__init__(
            source=source,
            schema=self.schema,
            validation=validation,
            namespaces=namespaces,
            locations=locations,
            base_url=base_url,
            allow=allow,
            defuse=defuse,
            timeout=timeout,
        )
        self.target_namespace = self._root.get('targetNamespace', '')
        self.imports = {}
        self.warnings = []
        self.locations = NamespaceResourcesMap(self.get_locations(locations))

        if maps is None:
            self.maps = Wsdl11Globals(xsd_globals=self.schema.maps)
        else:
            self.maps = maps

        if self.namespace == XSD_NAMESPACE:
            # Build schema for XSD documents
            self.schema.__class__(self, locations=locations, global_maps=self.schema.maps)
            return

        self._parse_imports()
        self._parse_types()
        self._parse_messages()

    def parse_error(self, message):
        if self.validation == 'strict':
            raise WsdlParseError(message)
        elif self.validation == 'lax':
            self.errors.append(WsdlParseError(message))

    def _parse_types(self):
        nsmap = []
        path = '{}/{}'.format(WSDL_TYPES, XSD_SCHEMA)

        for child in self.iterfind(path, nsmap=nsmap):
            namespaces = self.namespaces.copy()
            namespaces.update(nsmap)

            schema = self.schema.__class__(child, global_maps=self.schema.maps, build=False)
            schema.namespaces.update(namespaces)
            schema.build()

    def _parse_messages(self):
        for child in self.iterfind(WSDL_MESSAGE):
            message = WsdlMessage(child, self)
            if message.name in self.maps.messages:
                self.parse_error("duplicate message {!r}".format(message.name))
                continue

            name = '{%s}%s' % (self.target_namespace, message.name)
            self.maps.messages[name] = message

    def _parse_port_types(self):
        pass

    def _parse_services(self):
        pass

    def _parse_bindings(self):
        pass

    def _parse_imports(self):
        namespace_imports = NamespaceResourcesMap(map(
            lambda x: (x.get('namespace', ''), x.get('location', '')),
            filter(lambda x: x.tag == WSDL_IMPORT, self.root)
        ))

        for namespace, locations in namespace_imports.items():
            if namespace == self.target_namespace:
                self.parse_error("the attribute 'namespace' must be different from "
                                 "the 'targetNamespace' of the WSDL document")
                continue
            elif self.imports.get(namespace) is not None:
                continue
            elif namespace in self.maps.namespaces:
                self.imports[namespace] = self.maps.namespaces[namespace][0]
                continue

            locations = [url for url in locations if url]
            if not namespace:
                pass
            elif not locations:
                try:
                    locations = list(self.locations[namespace])
                except KeyError:
                    pass
            elif all(is_remote_url(url) for url in locations):
                # Try the local hints before schema locations.
                local_hints = [url for url in self.locations.get(namespace, ())
                               if url and url_path_is_file(url)]
                if local_hints:
                    locations = local_hints + locations

            import_error = None
            for url in locations:
                try:
                    self.import_namespace(namespace, url, self.base_url)
                except (OSError, IOError) as err:
                    if import_error is None:
                        import_error = err
                except (TypeError, SyntaxError) as err:
                    msg = "cannot import namespace %r: %s." % (namespace, err)
                    if isinstance(err, SyntaxError):
                        self.parse_error(msg)
                    elif self.validation == 'strict':
                        raise type(err)(msg)
                    else:
                        self.errors.append(type(err)(msg))
                except XMLSchemaValueError as err:
                    self.parse_error(err)
                else:
                    break
            else:
                if import_error is not None:
                    msg = "Import of namespace {!r} from {!r} failed: {}."
                    self.warnings.append(msg.format(namespace, locations, str(import_error)))
                    warnings.warn(self.warnings[-1], XMLSchemaImportWarning, stacklevel=4)
                self.imports[namespace] = None

    def import_namespace(self, namespace, location, base_url=None, build=False):
        """
        Imports definitions for an external namespace, from a specific URL.

        :param namespace: is the URI of the external namespace.
        :param location: is the URL of the schema.
        :param base_url: is an optional base URL for fetching the WSDL resource.
        :param build: defines when to build the imported WSDL, the default is to not build.
        :return: the imported :class:`XMLSchema` instance.
        """
        if location == self.url:
            return self
        elif self.imports.get(namespace) is not None:
            return self.imports[namespace]
        elif namespace in self.maps.namespaces:
            self.imports[namespace] = self.maps.namespaces[namespace][0]
            return self.imports[namespace]

        url = fetch_resource(location, base_url)
        if self.imports.get(namespace) is not None and self.imports[namespace].url == url:
            return self.imports[namespace]
        elif namespace in self.maps.namespaces:
            for wsdl_document in self.maps.namespaces[namespace]:
                if url == wsdl_document.url:
                    self.imports[namespace] = wsdl_document
                    return wsdl_document

        wsdl_document = type(self)(
            source=url,
            validation=self.validation,
            maps=self.maps,
            base_url=self.base_url,
            allow=self.allow,
            defuse=self.defuse,
            timeout=self.timeout,
        )
        if wsdl_document.target_namespace != namespace:
            raise XMLSchemaValueError(
                'imported %r has an unmatched namespace %r' % (wsdl_document, namespace)
            )
        self.imports[namespace] = wsdl_document
        return wsdl_document
