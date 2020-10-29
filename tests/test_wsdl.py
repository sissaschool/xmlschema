#!/usr/bin/env python
#
# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""Tests concerning WSDL documents. Examples from WSDL 1.1 definition document."""

import unittest
import os

from xmlschema import XMLSchemaValidationError
from xmlschema.etree import ParseError
from xmlschema.wsdl import WsdlParseError, WsdlComponent, WsdlMessage, \
    WsdlPortType, WsdlOperation, WsdlBinding, WsdlService, Wsdl11Document

from xml.etree import ElementTree


TEST_CASES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_cases/')


def casepath(relative_path):
    return os.path.join(TEST_CASES_DIR, relative_path)


WSDL_DOCUMENT_EXAMPLE = """<?xml version="1.0"?>
<definitions name="StockQuote"
          targetNamespace="http://example.com/stockquote.wsdl"
          xmlns:tns="http://example.com/stockquote.wsdl"
          xmlns:xsd1="http://example.com/stockquote.xsd"
          xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/"
          xmlns="http://schemas.xmlsoap.org/wsdl/">

    <types>
       <schema targetNamespace="http://example.com/stockquote.xsd"
              xmlns="http://www.w3.org/2001/XMLSchema">
           <element name="TradePriceRequest">
              <complexType>
                  <all>
                      <element name="tickerSymbol" type="string"/>
                  </all>
              </complexType>
           </element>
           <element name="TradePrice">
              <complexType>
                  <all>
                      <element name="price" type="float"/>
                  </all>
              </complexType>
           </element>
       </schema>
    </types>

    <message name="GetLastTradePriceInput">
        <part name="body" element="xsd1:TradePriceRequest"/>
    </message>

    <message name="GetLastTradePriceOutput">
        <part name="body" element="xsd1:TradePrice"/>
    </message>

    <portType name="StockQuotePortType">
        <operation name="GetLastTradePrice">
           <input message="tns:GetLastTradePriceInput"/>
           <output message="tns:GetLastTradePriceOutput"/>
        </operation>
    </portType>

    <binding name="StockQuoteBinding" type="tns:StockQuotePortType">
        <soap:binding style="document" transport="http://schemas.xmlsoap.org/soap/http"/>
        <operation name="GetLastTradePrice">
           <soap:operation soapAction="http://example.com/GetLastTradePrice"/>
           <input>
               <soap:body use="literal"/>
           </input>
           <output>
               <soap:body use="literal"/>
           </output>
        </operation>
    </binding>

    <service name="StockQuoteService">
        <documentation>My first service</documentation>
        <port name="StockQuotePort" binding="tns:StockQuoteBinding">
           <soap:address location="http://example.com/stockquote"/>
        </port>
    </service>

</definitions>
"""


class TestWsdlDocuments(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.vh_dir = casepath('examples/vehicles')
        cls.vh_xsd_file = casepath('examples/vehicles/vehicles.xsd')
        cls.vh_xml_file = casepath('examples/vehicles/vehicles.xml')

        cls.col_dir = casepath('examples/collection')
        cls.col_xsd_file = casepath('examples/collection/collection.xsd')
        cls.col_xml_file = casepath('examples/collection/collection.xml')

    def test_wsdl_document_init(self):
        wsdl_document = Wsdl11Document(WSDL_DOCUMENT_EXAMPLE)
        self.assertEqual(wsdl_document.target_namespace, "http://example.com/stockquote.wsdl")

        self.assertIn('http://example.com/stockquote.xsd', wsdl_document.schema.maps.namespaces)
        self.assertIn('{http://example.com/stockquote.xsd}TradePriceRequest',
                      wsdl_document.schema.maps.elements)
        self.assertIn('{http://example.com/stockquote.xsd}TradePrice',
                      wsdl_document.schema.maps.elements)

        self.assertIn('{http://example.com/stockquote.wsdl}GetLastTradePriceInput',
                      wsdl_document.maps.messages)
        self.assertIn('{http://example.com/stockquote.wsdl}GetLastTradePriceOutput',
                      wsdl_document.maps.messages)

        for message in wsdl_document.maps.messages.values():
            self.assertIsInstance(message, WsdlMessage)

        self.assertIn('{http://example.com/stockquote.wsdl}StockQuotePortType',
                      wsdl_document.maps.port_types)

        for port_type in wsdl_document.maps.port_types.values():
            self.assertIsInstance(port_type, WsdlPortType)
            for operation in port_type.operations.values():
                self.assertIsInstance(operation, WsdlOperation)

        self.assertIn('{http://example.com/stockquote.wsdl}StockQuoteBinding',
                      wsdl_document.maps.bindings)

        for bindings in wsdl_document.maps.bindings.values():
            self.assertIsInstance(bindings, WsdlBinding)
            for operation in bindings.operations.values():
                self.assertIsInstance(operation, WsdlOperation)

        self.assertIn('{http://example.com/stockquote.wsdl}StockQuoteService',
                      wsdl_document.maps.services)

        for service in wsdl_document.maps.services.values():
            self.assertIsInstance(service, WsdlService)

    def test_example3(self):
        original_example3_file = casepath('features/wsdl/wsdl11_example3.wsdl')
        with self.assertRaises(XMLSchemaValidationError):
            Wsdl11Document(original_example3_file)

        example3_file = casepath('features/wsdl/wsdl11_example3_valid.wsdl')
        wsdl_document = Wsdl11Document(example3_file)

        self.assertListEqual(list(wsdl_document.messages),
                             ['{http://example.com/stockquote.wsdl}SubscribeToQuotes'])
        self.assertListEqual(list(wsdl_document.port_types),
                             ['{http://example.com/stockquote.wsdl}StockQuotePortType'])
        self.assertListEqual(list(wsdl_document.bindings),
                             ['{http://example.com/stockquote.wsdl}StockQuoteSoap'])
        self.assertListEqual(list(wsdl_document.services),
                             ['{http://example.com/stockquote.wsdl}StockQuoteService'])

    def test_example4(self):
        original_example4_file = casepath('features/wsdl/wsdl11_example4.wsdl')
        with self.assertRaises(XMLSchemaValidationError):
            Wsdl11Document(original_example4_file)

        example_4_file = casepath('features/wsdl/wsdl11_example4_valid.wsdl')
        Wsdl11Document(example_4_file)

    def test_example5(self):
        original_example5_file = casepath('features/wsdl/wsdl11_example5.wsdl')
        with self.assertRaises(ParseError):
            Wsdl11Document(original_example5_file)

        example5_file = casepath('features/wsdl/wsdl11_example5_valid.wsdl')
        Wsdl11Document(example5_file)

    def test_wsdl_document_imports(self):
        stockquote_file = casepath('examples/stockquote/stockquote.wsdl')
        wsdl_document = Wsdl11Document(stockquote_file)
        self.assertEqual(wsdl_document.target_namespace,
                         "http://example.com/stockquote/definitions")
        self.assertIn('http://example.com/stockquote/schemas', wsdl_document.imports)
        self.assertIsInstance(
            wsdl_document.imports['http://example.com/stockquote/schemas'], Wsdl11Document
        )
        self.assertEqual(len(wsdl_document.maps.messages), 2)

        stockquote_service_file = casepath('examples/stockquote/stockquoteservice.wsdl')
        wsdl_document = Wsdl11Document(stockquote_service_file)
        self.assertListEqual(list(wsdl_document.imports), [
            'http://example.com/stockquote/schemas',
            'http://example.com/stockquote/definitions'
        ])

        wsdl_source = """<?xml version="1.0"?>
        <definitions name="StockQuote"
                  targetNamespace="http://example.com/stockquote.wsdl"
                  xmlns:xsd1="http://example.com/stockquote.xsd"
                  xmlns="http://schemas.xmlsoap.org/wsdl/">
            <import namespace="http://example.com/stockquote.xsd" location="not-found"/>
        </definitions>"""

        with self.assertRaises(WsdlParseError) as ctx:
            Wsdl11Document(wsdl_source)
        self.assertIn('Import of namespace', str(ctx.exception))

    def test_wsdl_document_clear_maps(self):
        stockquote_file = casepath('examples/stockquote/stockquote.wsdl')
        wsdl_document = Wsdl11Document(stockquote_file)

        self.assertListEqual(list(wsdl_document.maps.imports),
                             ['http://example.com/stockquote/schemas'])
        self.assertEqual(len(wsdl_document.maps.messages), 2)
        wsdl_document.maps.clear()
        self.assertListEqual(list(wsdl_document.maps.imports), [])
        self.assertEqual(len(wsdl_document.maps.messages), 0)

        wsdl_document.parse(stockquote_file)
        self.assertListEqual(list(wsdl_document.maps.imports),
                             ['http://example.com/stockquote/schemas'])
        self.assertEqual(len(wsdl_document.maps.messages), 2)

        stockquote_service_file = casepath('examples/stockquote/stockquoteservice.wsdl')
        wsdl_document = Wsdl11Document(stockquote_service_file)

    def test_wsdl_component(self):
        wsdl_document = Wsdl11Document(WSDL_DOCUMENT_EXAMPLE)

        elem = ElementTree.Element('foo')
        wsdl_component = WsdlComponent(elem, wsdl_document)
        self.assertIsNone(wsdl_component.prefixed_name)

        elem = ElementTree.Element('foo', name='bar')
        wsdl_component = WsdlComponent(elem, wsdl_document)
        self.assertEqual(wsdl_component.prefixed_name, 'tns:bar')

        self.assertEqual(wsdl_component.map_qname('{http://example.com/stockquote.wsdl}bar'),
                         'tns:bar')
        self.assertEqual(wsdl_component.unmap_qname('tns:bar'),
                         '{http://example.com/stockquote.wsdl}bar')

        elem = ElementTree.Element('foo', a1='tns:bar', a2='unknown:bar')
        self.assertEqual(wsdl_component._parse_reference(elem, 'a1'),
                         '{http://example.com/stockquote.wsdl}bar')
        self.assertEqual(wsdl_component._parse_reference(elem, 'a2'), 'unknown:bar')
        self.assertIsNone(wsdl_component._parse_reference(elem, 'a3'))

    def test_wsdl_message(self):
        wsdl_document = Wsdl11Document(WSDL_DOCUMENT_EXAMPLE)

        elem = ElementTree.XML('<message xmlns="http://schemas.xmlsoap.org/wsdl/"\n'
                               '         name="GetLastTradePriceInput">\n'
                               '  <part name="body" element="xsd1:unknown"/>\n'
                               '</message>')

        with self.assertRaises(WsdlParseError) as ctx:
            WsdlMessage(elem, wsdl_document)
        self.assertIn('missing schema element', str(ctx.exception))

        elem[0].attrib['element'] = 'xsd1:TradePriceRequest'
        wsdl_message = WsdlMessage(elem, wsdl_document)
        self.assertEqual(list(wsdl_message.parts), ['body'])

        elem.append(elem[0])
        with self.assertRaises(WsdlParseError) as ctx:
            WsdlMessage(elem, wsdl_document)
        self.assertIn("duplicated part 'body'", str(ctx.exception))

        elem[0].attrib['type'] = 'xsd1:TradePriceRequest'
        with self.assertRaises(WsdlParseError) as ctx:
            WsdlMessage(elem, wsdl_document)
        self.assertIn("ambiguous binding", str(ctx.exception))

        del elem[0].attrib['name']
        wsdl_message = WsdlMessage(elem, wsdl_document)
        self.assertEqual(wsdl_message.parts, {})

        elem = ElementTree.XML('<message xmlns="http://schemas.xmlsoap.org/wsdl/"\n'
                               '         xmlns:xs="http://www.w3.org/2001/XMLSchema"\n'
                               '         name="GetLastTradePriceInput">\n'
                               '  <part name="body" type="xs:string"/>\n'
                               '</message>')

        with self.assertRaises(WsdlParseError) as ctx:
            WsdlMessage(elem, wsdl_document)
        self.assertIn('missing schema type', str(ctx.exception))

        wsdl_document.namespaces['xs'] = "http://www.w3.org/2001/XMLSchema"
        wsdl_message = WsdlMessage(elem, wsdl_document)
        self.assertEqual(list(wsdl_message.parts), ['body'])

        del elem[0].attrib['type']
        with self.assertRaises(WsdlParseError) as ctx:
            WsdlMessage(elem, wsdl_document)
        self.assertEqual("missing both 'type' and 'element' attributes", str(ctx.exception))

    def test_wsdl_port_type(self):
        wsdl_document = Wsdl11Document(WSDL_DOCUMENT_EXAMPLE)

        elem = ElementTree.XML('<portType xmlns="http://schemas.xmlsoap.org/wsdl/"\n'
                               '          name="StockQuotePortType">\n'
                               '  <operation name="GetLastTradePrice">\n'
                               '    <input message="tns:GetLastTradePriceInput"/>\n'
                               '    <output message="tns:GetLastTradePriceOutput"/>\n'
                               '  </operation>\n'
                               '</portType>')


        wsdl_port_type = WsdlPortType(elem, wsdl_document)
        self.assertEqual(list(wsdl_port_type.operations), [('GetLastTradePrice', None, None)])

        elem.append(elem[0])  # Duplicate operation ...
        with self.assertRaises(WsdlParseError) as ctx:
            WsdlPortType(elem, wsdl_document)
        self.assertIn('duplicated operation', str(ctx.exception))

        del elem[0].attrib['name']
        wsdl_port_type = WsdlPortType(elem, wsdl_document)
        self.assertEqual(list(wsdl_port_type.operations), [])

    def test_wsdl_operation(self):
        wsdl_document = Wsdl11Document(WSDL_DOCUMENT_EXAMPLE)

        elem = ElementTree.XML('<operation xmlns="http://schemas.xmlsoap.org/wsdl/"\n'
                               '           xmlns:tns="http://example.com/stockquote.wsdl"\n'
                               '           name="GetLastTradePrice">\n'
                               '  <input name="input" message="tns:GetLastTradePriceInput"/>\n'
                               '  <output message="tns:GetLastTradePriceOutput"/>\n'
                               '</operation>')

        wsdl_operation = WsdlOperation(elem, wsdl_document)
        self.assertEqual(wsdl_operation.key, ('GetLastTradePrice', 'input', None))

        elem[1].attrib['name'] = 'output'
        wsdl_operation = WsdlOperation(elem, wsdl_document)
        self.assertEqual(wsdl_operation.key, ('GetLastTradePrice', 'input', 'output'))

        elem = ElementTree.XML('<operation xmlns="http://schemas.xmlsoap.org/wsdl/"\n'
                               '           xmlns:tns="http://example.com/stockquote.wsdl"\n'
                               '           name="GetLastTradePrice">\n'
                               '  <input message="tns:GetLastTradePriceInput"/>\n'
                               '</operation>')

        wsdl_operation = WsdlOperation(elem, wsdl_document)
        self.assertEqual(wsdl_operation.key, ('GetLastTradePrice', None, None))

        elem = ElementTree.XML('<operation xmlns="http://schemas.xmlsoap.org/wsdl/"\n'
                               '           xmlns:tns="http://example.com/stockquote.wsdl"\n'
                               '           name="GetLastTradePrice">\n'
                               '  <output message="tns:GetLastTradePriceOutput"/>\n'
                               '</operation>')
        wsdl_operation = WsdlOperation(elem, wsdl_document)
        self.assertEqual(wsdl_operation.key, ('GetLastTradePrice', None, None))


if __name__ == '__main__':
    import platform
    header_template = "Test xmlschema WSDL documents with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
