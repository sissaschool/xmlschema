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
import pathlib
from xml.etree import ElementTree

from xmlschema import XMLSchemaValidationError, XMLSchema10, XMLSchema11
from xmlschema.extras.wsdl import WsdlParseError, WsdlComponent, WsdlMessage, \
    WsdlPortType, WsdlOperation, WsdlBinding, WsdlService, Wsdl11Document, \
    WsdlInput, SoapHeader


TEST_CASES_DIR = str(pathlib.Path(__file__).absolute().parent.joinpath('test_cases'))


def casepath(relative_path):
    return str(pathlib.Path(TEST_CASES_DIR).joinpath(relative_path))


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

WSDL_DOCUMENT_NO_SOAP = """<?xml version="1.0"?>
<wsdl:definitions name="minimal"
        xmlns:wsdl="http://schemas.xmlsoap.org/wsdl/"
        xmlns:xs="http://www.w3.org/2001/XMLSchema">

    <wsdl:message name="myMessage">
        <wsdl:part name="content" type="xs:string"/>
    </wsdl:message>

    <wsdl:portType name="myPortType">
        <wsdl:operation name="myOperation">
           <wsdl:input message="myMessage"/>
        </wsdl:operation>
    </wsdl:portType>

    <wsdl:binding name="myBinding" type="myPortType">
        <wsdl:operation name="myOperation">
           <wsdl:input/>
        </wsdl:operation>
    </wsdl:binding>

    <wsdl:service name="myService">
        <wsdl:port name="myPort" binding="myBinding"/>
    </wsdl:service>

</wsdl:definitions>
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
        self.assertIsInstance(wsdl_document.schema, XMLSchema10)

        wsdl_document = Wsdl11Document(WSDL_DOCUMENT_EXAMPLE, cls=XMLSchema11)
        self.assertIsInstance(wsdl_document.schema, XMLSchema11)

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

        wsdl_document = Wsdl11Document(WSDL_DOCUMENT_EXAMPLE, locations=[('x', 'y'), ('x', 'z')])
        self.assertEqual(wsdl_document.locations, {'x': ['y', 'z']})

    def test_schema_class(self):
        wsdl_document = Wsdl11Document(WSDL_DOCUMENT_EXAMPLE)
        self.assertIsInstance(wsdl_document.schema, XMLSchema10)

        wsdl_document = Wsdl11Document(WSDL_DOCUMENT_EXAMPLE, cls=XMLSchema11)
        self.assertIsInstance(wsdl_document.schema, XMLSchema11)

    def test_validation_mode(self):
        wsdl_document = Wsdl11Document(WSDL_DOCUMENT_EXAMPLE)
        self.assertEqual(wsdl_document.validation, 'strict')

        with self.assertRaises(WsdlParseError) as ctx:
            wsdl_document.parse_error('wrong syntax')
        self.assertIn("wrong syntax", str(ctx.exception))

        wsdl_document = Wsdl11Document(WSDL_DOCUMENT_EXAMPLE, validation='lax')
        self.assertEqual(wsdl_document.validation, 'lax')

        wsdl_document.parse_error('wrong syntax')
        self.assertEqual(len(wsdl_document.errors), 1)
        self.assertIn("wrong syntax", str(wsdl_document.errors[0]))

        wsdl_document = Wsdl11Document(WSDL_DOCUMENT_EXAMPLE, validation='skip')
        self.assertEqual(wsdl_document.validation, 'skip')
        wsdl_document.parse_error('wrong syntax')
        self.assertEqual(len(wsdl_document.errors), 0)

        with self.assertRaises(ValueError) as ctx:
            Wsdl11Document(WSDL_DOCUMENT_EXAMPLE, validation='invalid')
        self.assertEqual("'invalid' is not a validation mode", str(ctx.exception))

    def test_example3(self):
        original_example3_file = casepath('features/wsdl/wsdl11_example3.wsdl')
        with self.assertRaises(XMLSchemaValidationError):
            Wsdl11Document(original_example3_file)

        wsdl_document = Wsdl11Document(original_example3_file, validation='lax')
        self.assertEqual(len(wsdl_document.errors), 1)

        example3_file = casepath('features/wsdl/wsdl11_example3_valid.wsdl')
        wsdl_document = Wsdl11Document(example3_file)

        message_name = '{http://example.com/stockquote.wsdl}SubscribeToQuotes'
        self.assertListEqual(list(wsdl_document.messages), [message_name])
        message = wsdl_document.messages[message_name]

        self.assertListEqual(list(message.parts), ['body', 'subscribeheader'])

        port_type_name = '{http://example.com/stockquote.wsdl}StockQuotePortType'
        self.assertListEqual(list(wsdl_document.port_types), [port_type_name])
        port_type = wsdl_document.port_types[port_type_name]

        self.assertEqual(list(port_type.operations), [('SubscribeToQuotes', None, None)])

        operation = port_type.operations[('SubscribeToQuotes', None, None)]
        self.assertIsNone(operation.soap_operation)
        self.assertEqual(operation.input.soap_body.use, 'literal')
        self.assertEqual(len(operation.input.soap_headers), 1)

        self.assertIs(operation.input.soap_headers[0].message, message)
        self.assertIs(operation.input.soap_headers[0].part, message.parts['subscribeheader'])

        binding_name = '{http://example.com/stockquote.wsdl}StockQuoteSoap'
        self.assertListEqual(list(wsdl_document.bindings), [binding_name])
        binding = wsdl_document.bindings[binding_name]

        self.assertIs(binding.port_type, port_type)
        self.assertEqual(binding.soap_transport, "http://example.com/smtp")
        self.assertEqual(binding.soap_style, "document")

        service_name = '{http://example.com/stockquote.wsdl}StockQuoteService'
        self.assertListEqual(list(wsdl_document.services), [service_name])
        self.assertEqual(list(wsdl_document.services[service_name].ports), ['StockQuotePort'])

        port = wsdl_document.services[service_name].ports['StockQuotePort']
        self.assertEqual(port.soap_location, 'mailto:subscribe@example.com')

    def test_example3_without_types__issue_347(self):
        no_types_file = casepath('features/wsdl/wsdl11_example3_no_types.wsdl')
        with self.assertRaises(WsdlParseError):
            Wsdl11Document(no_types_file)

        schema_file = casepath('features/wsdl/wsdl11_example3_types.xsd')
        wsdl_document = Wsdl11Document(no_types_file, schema=schema_file)

        self.assertIn('{http://example.com/stockquote.xsd}SubscribeToQuotes',
                      wsdl_document.schema.maps.elements)
        self.assertIn('{http://example.com/stockquote.xsd}SubscriptionHeader',
                      wsdl_document.schema.maps.elements)

    def test_example4(self):
        original_example4_file = casepath('features/wsdl/wsdl11_example4.wsdl')
        with self.assertRaises(XMLSchemaValidationError):
            Wsdl11Document(original_example4_file)

        example_4_file = casepath('features/wsdl/wsdl11_example4_valid.wsdl')
        wsdl_document = Wsdl11Document(example_4_file)

        message1_name = '{http://example.com/stockquote.wsdl}GetTradePriceInput'
        message2_name = '{http://example.com/stockquote.wsdl}GetTradePriceOutput'
        self.assertListEqual(list(wsdl_document.messages), [message1_name, message2_name])

        message1 = wsdl_document.messages[message1_name]
        message2 = wsdl_document.messages[message2_name]

        self.assertListEqual(list(message1.parts), ['tickerSymbol', 'time'])
        self.assertListEqual(list(message2.parts), ['result'])

        port_type_name = '{http://example.com/stockquote.wsdl}StockQuotePortType'
        self.assertListEqual(list(wsdl_document.port_types), [port_type_name])
        port_type = wsdl_document.port_types[port_type_name]

        self.assertEqual(list(port_type.operations), [('GetTradePrice', None, None)])

        operation = port_type.operations[('GetTradePrice', None, None)]
        self.assertIsNotNone(operation.soap_operation)
        self.assertEqual(operation.soap_action, 'http://example.com/GetTradePrice')
        self.assertEqual(operation.soap_style, 'document')

        self.assertIs(operation.input.message, message1)
        self.assertIs(operation.output.message, message2)

        self.assertEqual(operation.input.soap_body.use, 'encoded')
        self.assertEqual(operation.input.soap_body.namespace, 'http://example.com/stockquote')
        self.assertEqual(operation.input.soap_body.encoding_style,
                         'http://schemas.xmlsoap.org/soap/encoding/')
        self.assertEqual(len(operation.input.soap_headers), 0)

        self.assertEqual(operation.output.soap_body.use, 'encoded')
        self.assertEqual(operation.output.soap_body.namespace, 'http://example.com/stockquote')
        self.assertEqual(operation.output.soap_body.encoding_style,
                         'http://schemas.xmlsoap.org/soap/encoding/')
        self.assertEqual(len(operation.output.soap_headers), 0)

        binding_name = '{http://example.com/stockquote.wsdl}StockQuoteBinding'
        self.assertListEqual(list(wsdl_document.bindings), [binding_name])
        binding = wsdl_document.bindings[binding_name]

        self.assertIs(binding.port_type, port_type)
        self.assertEqual(binding.soap_transport, "http://schemas.xmlsoap.org/soap/http")
        self.assertEqual(binding.soap_style, "rpc")

        service_name = '{http://example.com/stockquote.wsdl}StockQuoteService'
        self.assertListEqual(list(wsdl_document.services), [service_name])
        self.assertEqual(list(wsdl_document.services[service_name].ports), ['StockQuotePort'])

        port = wsdl_document.services[service_name].ports['StockQuotePort']
        self.assertEqual(port.soap_location, 'http://example.com/stockquote')

    def test_example5(self):
        original_example5_file = casepath('features/wsdl/wsdl11_example5.wsdl')
        with self.assertRaises(ElementTree.ParseError):
            Wsdl11Document(original_example5_file)

        example5_file = casepath('features/wsdl/wsdl11_example5_valid.wsdl')
        wsdl_document = Wsdl11Document(example5_file)

        message1_name = '{http://example.com/stockquote.wsdl}GetTradePricesInput'
        message2_name = '{http://example.com/stockquote.wsdl}GetTradePricesOutput'
        self.assertListEqual(list(wsdl_document.messages), [message1_name, message2_name])

        message1 = wsdl_document.messages[message1_name]
        message2 = wsdl_document.messages[message2_name]

        self.assertListEqual(list(message1.parts), ['tickerSymbol', 'timePeriod'])
        self.assertListEqual(list(message2.parts), ['result', 'frequency'])

        port_type_name = '{http://example.com/stockquote.wsdl}StockQuotePortType'
        self.assertListEqual(list(wsdl_document.port_types), [port_type_name])
        port_type = wsdl_document.port_types[port_type_name]

        self.assertEqual(list(port_type.operations), [('GetTradePrices', None, None)])

        operation = port_type.operations[('GetTradePrices', None, None)]
        self.assertIsNotNone(operation.soap_operation)
        self.assertEqual(operation.soap_action, 'http://example.com/GetTradePrices')

        self.assertIs(operation.input.message, message1)
        self.assertIs(operation.output.message, message2)

        self.assertEqual(operation.input.soap_body.use, 'encoded')
        self.assertEqual(operation.input.soap_body.namespace, 'http://example.com/stockquote')
        self.assertEqual(operation.input.soap_body.encoding_style,
                         'http://schemas.xmlsoap.org/soap/encoding/')
        self.assertEqual(len(operation.input.soap_headers), 0)

        self.assertEqual(operation.output.soap_body.use, 'encoded')
        self.assertEqual(operation.output.soap_body.namespace, 'http://example.com/stockquote')
        self.assertEqual(operation.output.soap_body.encoding_style,
                         'http://schemas.xmlsoap.org/soap/encoding/')
        self.assertEqual(len(operation.output.soap_headers), 0)

        binding_name = '{http://example.com/stockquote.wsdl}StockQuoteBinding'
        self.assertListEqual(list(wsdl_document.bindings), [binding_name])
        binding = wsdl_document.bindings[binding_name]

        self.assertIs(binding.port_type, port_type)
        self.assertEqual(binding.soap_transport, "http://schemas.xmlsoap.org/soap/http")
        self.assertEqual(binding.soap_style, "rpc")

        service_name = '{http://example.com/stockquote.wsdl}StockQuoteService'
        self.assertListEqual(list(wsdl_document.services), [service_name])
        self.assertEqual(list(wsdl_document.services[service_name].ports), ['StockQuotePort'])

        port = wsdl_document.services[service_name].ports['StockQuotePort']
        self.assertEqual(port.soap_location, 'http://example.com/stockquote')

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

        wsdl_document._parse_imports()
        self.assertListEqual(list(wsdl_document.imports), [
            'http://example.com/stockquote/schemas',
        ])

        stockquote_service_file = casepath('examples/stockquote/stockquoteservice.wsdl')

        wsdl_document = Wsdl11Document(stockquote_service_file)
        self.assertListEqual(list(wsdl_document.imports), [
            'http://example.com/stockquote/schemas',
            'http://example.com/stockquote/definitions'
        ])

    def test_wsdl_document_invalid_imports(self):
        wsdl_template = """<?xml version="1.0"?>
        <definitions name="import-test1"
                xmlns="http://schemas.xmlsoap.org/wsdl/">
            <import namespace="http://example.com/ns" location="{0}"/>
        </definitions>"""

        wsdl_document = Wsdl11Document(wsdl_template.format(''))
        self.assertIsNone(wsdl_document.imports['http://example.com/ns'])

        with self.assertRaises(WsdlParseError) as ctx:
            Wsdl11Document(wsdl_template.format('missing-file'))
        self.assertIn('import of namespace', str(ctx.exception))

        locations = [('http://example.com/ns', 'missing-file2')]
        with self.assertRaises(WsdlParseError) as ctx:
            Wsdl11Document(wsdl_template.format('missing-file'), locations=locations)
        self.assertIn('import of namespace', str(ctx.exception))

        malformed_file = casepath('resources/malformed.xml')
        with self.assertRaises(WsdlParseError) as ctx:
            Wsdl11Document(wsdl_template.format(malformed_file))
        self.assertIn('cannot import namespace', str(ctx.exception))
        self.assertIn('no element found', str(ctx.exception))

        wsdl_template = """<?xml version="1.0"?>
        <definitions name="import-test1"
                targetNamespace="http://example.com/ns"
                xmlns="http://schemas.xmlsoap.org/wsdl/">
            <import namespace="http://example.com/ns" location="{0}"/>
        </definitions>"""

        stockquote_file = casepath('examples/stockquote/stockquote.wsdl')
        with self.assertRaises(WsdlParseError) as ctx:
            Wsdl11Document(wsdl_template.format(stockquote_file))
        self.assertIn('namespace to import must be different', str(ctx.exception))

        wsdl_template = """<?xml version="1.0"?>
        <definitions name="import-test1"
                targetNamespace="http://example.com/stockquote/definitions"
                xmlns="http://schemas.xmlsoap.org/wsdl/">
            <import namespace="http://example.com/ns" location="{0}"/>
        </definitions>"""

        with self.assertRaises(WsdlParseError) as ctx:
            Wsdl11Document(wsdl_template.format(stockquote_file))
        self.assertIn('imported Wsdl11Document', str(ctx.exception))
        self.assertIn('has an unmatched namespace', str(ctx.exception))

    def test_wsdl_document_maps(self):
        stockquote_file = casepath('examples/stockquote/stockquote.wsdl')
        wsdl_document = Wsdl11Document(stockquote_file)

        self.assertListEqual(list(wsdl_document.maps.imports),
                             ['http://example.com/stockquote/schemas'])
        self.assertEqual(len(wsdl_document.maps.messages), 2)
        self.assertEqual(len(wsdl_document.maps.port_types), 1)
        self.assertEqual(len(wsdl_document.maps.bindings), 0)
        self.assertEqual(len(wsdl_document.maps.services), 0)

        wsdl_document.maps.clear()
        self.assertListEqual(list(wsdl_document.maps.imports), [])
        self.assertEqual(len(wsdl_document.maps.messages), 0)

        wsdl_document.parse(stockquote_file)
        self.assertListEqual(list(wsdl_document.maps.imports),
                             ['http://example.com/stockquote/schemas'])
        self.assertEqual(len(wsdl_document.maps.messages), 2)

        stockquote_service_file = casepath('examples/stockquote/stockquoteservice.wsdl')
        wsdl_document = Wsdl11Document(stockquote_service_file)
        self.assertListEqual(list(wsdl_document.maps.imports),
                             ['http://example.com/stockquote/schemas',
                              'http://example.com/stockquote/definitions'])
        self.assertEqual(len(wsdl_document.maps.messages), 2)
        self.assertEqual(len(wsdl_document.maps.port_types), 1)
        self.assertEqual(len(wsdl_document.maps.bindings), 1)
        self.assertEqual(len(wsdl_document.maps.services), 1)

        with self.assertRaises(WsdlParseError) as ctx:
            wsdl_document.parse(stockquote_file, lazy=True)
        self.assertIn('instance cannot be lazy', str(ctx.exception))

        wsdl_document.parse(stockquote_file)
        self.assertListEqual(list(wsdl_document.maps.imports),
                             ['http://example.com/stockquote/schemas'])
        self.assertEqual(len(wsdl_document.maps.messages), 2)
        self.assertEqual(len(wsdl_document.maps.port_types), 1)
        self.assertEqual(len(wsdl_document.maps.bindings), 0)
        self.assertEqual(len(wsdl_document.maps.services), 0)

        wsdl_document.parse(stockquote_service_file)
        self.assertListEqual(list(wsdl_document.maps.imports),
                             ['http://example.com/stockquote/schemas',
                              'http://example.com/stockquote/definitions'])
        self.assertEqual(len(wsdl_document.maps.messages), 2)
        self.assertEqual(len(wsdl_document.maps.port_types), 1)
        self.assertEqual(len(wsdl_document.maps.bindings), 1)
        self.assertEqual(len(wsdl_document.maps.services), 1)

    def test_wsdl_component(self):
        wsdl_document = Wsdl11Document(WSDL_DOCUMENT_EXAMPLE)

        elem = ElementTree.Element('foo', bar='abc')
        wsdl_component = WsdlComponent(elem, wsdl_document)
        self.assertIsNone(wsdl_component.prefixed_name)
        self.assertIs(wsdl_component.attrib, elem.attrib)
        self.assertEqual(wsdl_component.get('bar'), 'abc')

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

        with self.assertRaises(WsdlParseError) as ctx:
            wsdl_document._parse_messages()
        self.assertIn("duplicated message 'tns:GetLastTradePriceInput'", str(ctx.exception))

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

        with self.assertRaises(WsdlParseError) as ctx:
            wsdl_document._parse_port_types()
        self.assertIn("duplicated port type 'tns:StockQuotePortType'", str(ctx.exception))

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
        self.assertEqual(wsdl_operation.transmission, 'request-response')

        elem[1].attrib['name'] = 'output'
        wsdl_operation = WsdlOperation(elem, wsdl_document)
        self.assertEqual(wsdl_operation.key, ('GetLastTradePrice', 'input', 'output'))

        # Check the missing of soap bindings
        self.assertIsNone(wsdl_operation.soap_operation)
        self.assertIsNone(wsdl_operation.soap_action)
        self.assertIsNone(wsdl_operation.soap_style)

        elem = ElementTree.XML('<operation xmlns="http://schemas.xmlsoap.org/wsdl/"\n'
                               '           xmlns:tns="http://example.com/stockquote.wsdl"\n'
                               '           name="GetLastTradePrice">\n'
                               '  <output name="send" message="tns:GetLastTradePriceOutput"/>\n'
                               '  <input name="receive" message="tns:GetLastTradePriceInput"/>\n'
                               '</operation>')

        wsdl_operation = WsdlOperation(elem, wsdl_document)
        self.assertEqual(wsdl_operation.key, ('GetLastTradePrice', 'receive', 'send'))
        self.assertEqual(wsdl_operation.transmission, 'solicit-response')

        elem = ElementTree.XML('<operation xmlns="http://schemas.xmlsoap.org/wsdl/"\n'
                               '           xmlns:tns="http://example.com/stockquote.wsdl"\n'
                               '           name="GetLastTradePrice">\n'
                               '  <input message="tns:GetLastTradePriceInput"/>\n'
                               '</operation>')

        wsdl_operation = WsdlOperation(elem, wsdl_document)
        self.assertEqual(wsdl_operation.key, ('GetLastTradePrice', None, None))
        self.assertEqual(wsdl_operation.transmission, 'one-way')

        elem = ElementTree.XML('<operation xmlns="http://schemas.xmlsoap.org/wsdl/"\n'
                               '           xmlns:tns="http://example.com/stockquote.wsdl"\n'
                               '           name="GetLastTradePrice">\n'
                               '  <output message="tns:GetLastTradePriceOutput"/>\n'
                               '</operation>')
        wsdl_operation = WsdlOperation(elem, wsdl_document)
        self.assertEqual(wsdl_operation.key, ('GetLastTradePrice', None, None))
        self.assertEqual(wsdl_operation.transmission, 'notification')

        # Only for testing code, with faults is better to add specific messages.
        elem = ElementTree.XML('<operation xmlns="http://schemas.xmlsoap.org/wsdl/"\n'
                               '           xmlns:tns="http://example.com/stockquote.wsdl"\n'
                               '           name="GetLastTradePrice">\n'
                               '  <input message="tns:GetLastTradePriceInput"/>\n'
                               '  <fault message="tns:GetLastTradePriceInput"/>\n'
                               '</operation>')

        wsdl_operation = WsdlOperation(elem, wsdl_document)
        self.assertEqual(wsdl_operation.faults, {})  # not inserted if name is missing ...
        elem[1].attrib['name'] = 'foo'
        wsdl_operation = WsdlOperation(elem, wsdl_document)
        self.assertEqual(list(wsdl_operation.faults), ['foo'])

        message_name = '{http://example.com/stockquote.wsdl}GetLastTradePriceInput'
        message = wsdl_document.messages[message_name]
        self.assertIs(wsdl_operation.faults['foo'].message, message)

        elem.append(elem[1])  # create a fake duplicated fault

        with self.assertRaises(WsdlParseError) as ctx:
            WsdlOperation(elem, wsdl_document)
        self.assertIn("duplicated fault 'foo'", str(ctx.exception))

        elem.clear()
        wsdl_operation = WsdlOperation(elem, wsdl_document)
        self.assertIsNone(wsdl_operation.input)
        self.assertIsNone(wsdl_operation.output)
        self.assertIsNone(wsdl_operation.transmission)
        self.assertEqual(wsdl_operation.faults, {})

    def test_wsdl_binding(self):
        wsdl_document = Wsdl11Document(WSDL_DOCUMENT_EXAMPLE)

        with self.assertRaises(WsdlParseError) as ctx:
            wsdl_document._parse_bindings()
        self.assertIn("duplicated binding 'tns:StockQuoteBinding'", str(ctx.exception))

        elem = ElementTree.XML(
            '<binding xmlns="http://schemas.xmlsoap.org/wsdl/"\n'
            '     xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/"\n'
            '     name="StockQuoteBinding" type="tns:StockQuotePortType"\n>'
            '  <soap:binding transport="http://schemas.xmlsoap.org/soap/http"/>\n'
            '  <operation name="GetLastTradePrice">'
            '    <input/>'
            '    <output/>'
            '    <fault><soap:fault name=""/></fault>'
            '  </operation>'
            '</binding>')

        wsdl_binding = WsdlBinding(elem, wsdl_document)
        self.assertEqual(wsdl_binding.port_type, list(wsdl_document.port_types.values())[0])
        self.assertEqual(list(wsdl_binding.operations), [('GetLastTradePrice', None, None)])

        del elem[1][0]  # remove <input/>
        wsdl_binding = WsdlBinding(elem, wsdl_document)
        self.assertEqual(wsdl_binding.port_type, list(wsdl_document.port_types.values())[0])
        self.assertEqual(list(wsdl_binding.operations), [('GetLastTradePrice', None, None)])

        del elem[1][0]  # remove <output/>
        wsdl_binding = WsdlBinding(elem, wsdl_document)
        self.assertEqual(wsdl_binding.port_type, list(wsdl_document.port_types.values())[0])
        self.assertEqual(list(wsdl_binding.operations), [('GetLastTradePrice', None, None)])

        elem[1][0].attrib['name'] = 'unknown'  # set an unknown name to <fault/>
        with self.assertRaises(WsdlParseError) as ctx:
            WsdlBinding(elem, wsdl_document)
        self.assertIn("missing fault 'unknown'", str(ctx.exception))
        del elem[1][0]  # remove <fault/>

        elem.append(elem[1])
        with self.assertRaises(WsdlParseError) as ctx:
            WsdlBinding(elem, wsdl_document)
        self.assertIn("duplicated operation 'GetLastTradePrice'", str(ctx.exception))

        del elem[2]
        elem[1].attrib['name'] = 'unknown'
        with self.assertRaises(WsdlParseError) as ctx:
            WsdlBinding(elem, wsdl_document)
        self.assertIn("operation 'unknown' not found", str(ctx.exception))

        del elem[1].attrib['name']
        wsdl_binding = WsdlBinding(elem, wsdl_document)
        self.assertEqual(wsdl_binding.operations, {})

        elem.attrib['type'] = 'tns:unknown'
        with self.assertRaises(WsdlParseError) as ctx:
            WsdlBinding(elem, wsdl_document)
        self.assertIn("missing port type", str(ctx.exception))

        del elem[0]
        with self.assertRaises(WsdlParseError) as ctx:
            WsdlBinding(elem, wsdl_document)
        self.assertIn("missing soap:binding element", str(ctx.exception))

    def test_wsdl_service(self):
        wsdl_document = Wsdl11Document(WSDL_DOCUMENT_EXAMPLE)

        with self.assertRaises(WsdlParseError) as ctx:
            wsdl_document._parse_services()
        self.assertIn("duplicated service 'tns:StockQuoteService'", str(ctx.exception))

        elem = ElementTree.XML(
            '<service xmlns="http://schemas.xmlsoap.org/wsdl/"\n'
            '     xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/"\n'
            '     name="StockQuoteService"\n>'
            '  <port name="StockQuotePort" binding="tns:StockQuoteBinding">'
            '       <soap:address location="http://example.com/stockquote"/>'
            '  </port>'
            '</service>')

        wsdl_service = WsdlService(elem, wsdl_document)
        binding_name = '{http://example.com/stockquote.wsdl}StockQuoteBinding'
        binding = wsdl_document.bindings[binding_name]
        self.assertIs(wsdl_service.ports['StockQuotePort'].binding, binding)

        elem[0].attrib['binding'] = 'tns:unknown'
        with self.assertRaises(WsdlParseError) as ctx:
            WsdlService(elem, wsdl_document)
        self.assertIn('unknown binding', str(ctx.exception))

        del elem[0].attrib['binding']
        wsdl_service = WsdlService(elem, wsdl_document)
        self.assertIsNone(wsdl_service.ports['StockQuotePort'].binding)
        self.assertEqual(wsdl_service.ports['StockQuotePort'].soap_location,
                         'http://example.com/stockquote')

        del elem[0][0]
        wsdl_service = WsdlService(elem, wsdl_document)
        self.assertIsNone(wsdl_service.ports['StockQuotePort'].soap_location)

        elem.append(elem[0])
        with self.assertRaises(WsdlParseError) as ctx:
            WsdlService(elem, wsdl_document)
        self.assertIn('duplicated port', str(ctx.exception))

        del elem[0].attrib['name']
        wsdl_service = WsdlService(elem, wsdl_document)
        self.assertEqual(wsdl_service.ports, {})

    def test_wsdl_missing_message_reference(self):
        wsdl_document = Wsdl11Document(WSDL_DOCUMENT_EXAMPLE)

        elem = ElementTree.XML('<input xmlns="http://schemas.xmlsoap.org/wsdl/"\n'
                               '       xmlns:tns="http://example.com/stockquote.wsdl"\n'
                               '       message="tns:unknown"/>')

        with self.assertRaises(WsdlParseError) as ctx:
            WsdlInput(elem, wsdl_document)
        self.assertIn('unknown message', str(ctx.exception))

        elem = ElementTree.XML('<input xmlns="http://schemas.xmlsoap.org/wsdl/"/>')

        input_op = WsdlInput(elem, wsdl_document)
        self.assertIsNone(input_op.message)

    def test_wsdl_soap_header_bindings(self):
        wsdl_document = Wsdl11Document(WSDL_DOCUMENT_EXAMPLE)

        elem = ElementTree.XML('<header xmlns="http://schemas.xmlsoap.org/wsdl/soap/"\n'
                               '        xmlns:tns="http://example.com/stockquote.wsdl"\n'
                               '        message="tns:SubscribeToQuotes"\n'
                               '        part="subscribeheader" use="literal"/>')

        with self.assertRaises(WsdlParseError) as ctx:
            SoapHeader(elem, wsdl_document)
        self.assertIn('unknown message', str(ctx.exception))

        elem.attrib['message'] = 'tns:GetLastTradePriceInput'
        with self.assertRaises(WsdlParseError) as ctx:
            SoapHeader(elem, wsdl_document)
        self.assertIn("missing message part 'subscribeheader'", str(ctx.exception))

        elem.attrib['part'] = 'body'
        soap_header = SoapHeader(elem, wsdl_document)
        message_name = '{http://example.com/stockquote.wsdl}GetLastTradePriceInput'
        self.assertIs(wsdl_document.messages[message_name], soap_header.message)
        self.assertIs(wsdl_document.messages[message_name].parts['body'], soap_header.part)

        del elem.attrib['part']
        soap_header = SoapHeader(elem, wsdl_document)
        self.assertIs(wsdl_document.messages[message_name], soap_header.message)
        self.assertIsNone(soap_header.part)

        elem = ElementTree.XML('<header xmlns="http://schemas.xmlsoap.org/wsdl/soap/"\n'
                               '        xmlns:tns="http://example.com/stockquote.wsdl"\n'
                               '        message="tns:GetLastTradePriceInput"\n'
                               '        part="body" use="literal">\n'
                               '   <headerfault message="tns:GetLastTradePriceInput"\n'
                               '          part="body" use="literal"/>\n'
                               '</header>')

        soap_header = SoapHeader(elem, wsdl_document)
        message = wsdl_document.messages[message_name]
        self.assertIs(message, soap_header.message)
        self.assertIs(message.parts['body'], soap_header.part)
        self.assertEqual(len(soap_header.faults), 1)
        self.assertIs(message, soap_header.faults[0].message)
        self.assertIs(message.parts['body'], soap_header.faults[0].part)

    def test_wsdl_no_soap_bindings(self):
        wsdl_document = Wsdl11Document(WSDL_DOCUMENT_NO_SOAP)
        self.assertEqual(list(wsdl_document.messages), ['myMessage'])
        self.assertEqual(list(wsdl_document.port_types), ['myPortType'])
        self.assertEqual(list(wsdl_document.bindings), ['myBinding'])
        self.assertEqual(list(wsdl_document.services), ['myService'])

        self.assertIsNone(wsdl_document.bindings['myBinding'].soap_transport)
        self.assertIsNone(wsdl_document.bindings['myBinding'].soap_style)

    def test_wsdl_and_soap_faults(self):
        example5_file_with_fault = casepath('features/wsdl/wsdl11_example5_with_fault.wsdl')
        wsdl_document = Wsdl11Document(example5_file_with_fault)

        port_type_name = '{http://example.com/stockquote.wsdl}StockQuotePortType'
        self.assertListEqual(list(wsdl_document.port_types), [port_type_name])
        port_type = wsdl_document.port_types[port_type_name]
        operation = port_type.operations[('GetTradePrices', None, None)]

        message_name = '{http://example.com/stockquote.wsdl}FaultMessage'
        message = wsdl_document.messages[message_name]
        self.assertIs(operation.faults['fault'].message, message)

        elem = ElementTree.XML(
            '<binding xmlns="http://schemas.xmlsoap.org/wsdl/"\n'
            '     xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/"\n'
            '     name="StockQuoteBinding" type="tns:StockQuotePortType"\n>'
            '  <soap:binding transport="http://schemas.xmlsoap.org/soap/http"/>\n'
            '  <operation name="GetTradePrices">'
            '    <input/>'
            '    <output/>'
            '    <fault><soap:fault name="exception"/></fault>'
            '  </operation>'
            '</binding>')

        with self.assertRaises(WsdlParseError) as ctx:
            WsdlBinding(elem, wsdl_document)
        self.assertIn("missing fault 'exception'", str(ctx.exception))

    def test_loading_from_unrelated_dirs__issue_237(self):
        relpath = str(pathlib.Path(__file__).parent.joinpath(
            'test_cases/issues/issue_237/dir1/stockquoteservice.wsdl'
        ))
        wsdl_document = Wsdl11Document(relpath)
        self.assertIn('http://example.com/stockquote/schemas', wsdl_document.imports)
        self.assertEqual(
            wsdl_document.imports['http://example.com/stockquote/schemas'].name,
            'stockquote.xsd'
        )
        self.assertIn('http://example.com/stockquote/definitions', wsdl_document.imports)
        self.assertEqual(
            wsdl_document.imports['http://example.com/stockquote/definitions'].name,
            'stockquote.wsdl'
        )


if __name__ == '__main__':
    import platform
    header_template = "Test xmlschema WSDL documents with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
