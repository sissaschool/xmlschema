from typing import Iterator, Optional
from xml.etree import ElementTree
import xmlschema

document = ElementTree.fromstring("<id>http://example.org</id>")
schema = xmlschema.XMLSchema11("""\
<?xml version="1.0" encoding="utf-8"?>
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <xsd:element name="id" type="xsd:anyURI" />
</xsd:schema>
""")


def extra_validator1(
    element: ElementTree.Element,
    xsd_element: xmlschema.XsdElement,
) -> Optional[Iterator[xmlschema.XMLSchemaValidationError]]:
    _ = element.tag, xsd_element.type.name
    return None


schema.validate(document, extra_validator=extra_validator1)


def extra_validator2(
    element: ElementTree.Element,
    xsd_element: xmlschema.XsdElement,
) -> Optional[Iterator[xmlschema.XMLSchemaValidationError]]:
    _ = element.tag, xsd_element.type.name
    return None


schema.validate(document, extra_validator=extra_validator2)
