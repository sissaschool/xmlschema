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
from .namespaces import WSDL_NAMESPACE, SCHEMAS_DIR, NamespaceResourcesMap
from .resources import is_remote_url, url_path_is_file, fetch_resource
from .documents import XmlDocument
from .validators import XMLSchema10, XMLSchemaImportWarning


WSDL_IMPORT = '{%s}import' % WSDL_NAMESPACE


class WsdlParseError(XMLSchemaException, SyntaxError):
    """An error during parsing of a WSDL document."""


class Wsdl11Document(XmlDocument):

    schema = XMLSchema10(os.path.join(SCHEMAS_DIR, 'WSDL/wsdl.xsd'), build=False)

    def __init__(self, source, cls=None, validation='strict', namespaces=None, maps=None,
                 locations=None, base_url=None, allow='all', defuse='remote', timeout=300):
        if not self.schema.built:
            self.schema.build()

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
            self.maps = self.schema.maps.copy()

        self._parse_imports()

    def parse_error(self, message):
        if self.validation == 'strict':
            raise WsdlParseError(message)
        elif self.validation == 'lax':
            self.errors.append(WsdlParseError(message))

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
                    # It's not an error if the location access fails (ref. section 4.2.6.2):
                    #   https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/#composition-schemaImport
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
                    # logger.info("Namespace %r imported from %r", namespace, url)
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
