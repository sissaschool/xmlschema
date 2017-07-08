Usage
=====

.. _lxml: http://lxml.de

.. testsetup::

    import xmlschema
    import os
    os.chdir('..')

.. testsetup:: vehicles

    import xmlschema
    import os

Import the library in your code with::

    import xmlschema

The module initialization builds the XSD meta-schemas and of the dictionary
containing the code points of the Unicode categories.


Create a schema instance
------------------------

Import the library and then create an instance of a schema using the path of
the file containing the schema as argument:

.. doctest::

    >>> import xmlschema
    >>> my_schema = xmlschema.XMLSchema('xmlschema/tests/examples/vehicles/vehicles.xsd')

Otherwise the argument can be also an opened file-like object:

.. doctest::

    >>> import xmlschema
    >>> schema_file = open('xmlschema/tests/examples/vehicles/vehicles.xsd')
    >>> my_schema = xmlschema.XMLSchema(schema_file)

Alternatively you can pass a string containing the schema definition:

.. doctest::

    >>> import xmlschema
    >>> my_schema = xmlschema.XMLSchema("""
    ... <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
    ... <xs:element name="block" type="xs:string"/>
    ... </xs:schema>
    ... """)

This last option has limitations when the schema requires to include other local subschemas
because the package cannot knows anything about the schema's source location:

.. doctest::

    >>> import xmlschema
    >>> schema_xsd = open('xmlschema/tests/examples/vehicles/vehicles.xsd').read()
    >>> my_schema = xmlschema.XMLSchema(schema_xsd)
    Traceback (most recent call last):
      File "/usr/lib64/python2.7/doctest.py", line 1315, in __run
        compileflags, 1) in test.globs
      File "<doctest default[2]>", line 1, in <module>
        my_schema = xmlschema.XMLSchema(schema_xsd)
      File "/home/brunato/Development/projects/xmlschema/xmlschema/schema.py", line 270, in __init__
        self.include_schemas(self.root, check_schema)
      File "/home/brunato/Development/projects/xmlschema/xmlschema/schema.py", line 380, in include_schemas
        reason="cannot include %r: %s" % (location, err.reason)
    XMLSchemaURLError: <urlopen error cannot include 'cars.xsd': cannot access resource from 'cars.xsd': [OSError(2, 'No such file or directory')]>


XSD declarations
----------------

The schema object includes XSD declarations (*types*, *elements*, *attributes*,
*groups*, *attribute_groups*). The global XSD declarations are available as
dictionary attributes of the schema instance:

.. doctest::

    >>> import xmlschema
    >>> from pprint import pprint
    >>> my_schema = xmlschema.XMLSchema('xmlschema/tests/examples/vehicles/vehicles.xsd')
    >>> my_schema.types
    <NamespaceView {u'vehicleType': <XsdComplexType u'{http://example.com/vehicles}vehicleType' at 0x...>} at 0x...>
    >>> pprint(dict(my_schema.elements))
    {u'bikes': <XsdElement u'{http://example.com/vehicles}bikes' at 0x...>,
     u'cars': <XsdElement u'{http://example.com/vehicles}cars' at 0x...>,
     u'vehicles': <XsdElement u'{http://example.com/vehicles}vehicles' at 0x...>}
    >>> my_schema.attributes
    <NamespaceView {u'step': <XsdAttribute u'{http://example.com/vehicles}step' at 0x...>} at 0x...>

Those declarations are local views of the XSD global maps shared between related
schema instances, that can be accessed through :attr:`XMLSchema.maps` attribute:

.. doctest::

    >>> from pprint import pprint
    >>> pprint(sorted(my_schema.maps.types.keys())[:5])
    [u'{http://example.com/vehicles}vehicleType',
     u'{http://www.w3.org/1999/xlink}actuateType',
     u'{http://www.w3.org/1999/xlink}arcType',
     u'{http://www.w3.org/1999/xlink}arcroleType',
     u'{http://www.w3.org/1999/xlink}extended']
    >>> pprint(sorted(my_schema.maps.elements.keys())[:10])
    [u'{http://example.com/vehicles}bikes',
     u'{http://example.com/vehicles}cars',
     u'{http://example.com/vehicles}vehicles',
     u'{http://www.w3.org/1999/xlink}arc',
     u'{http://www.w3.org/1999/xlink}locator',
     u'{http://www.w3.org/1999/xlink}resource',
     u'{http://www.w3.org/1999/xlink}title',
     u'{http://www.w3.org/2001/XMLSchema-hasFacetAndProperty}hasFacet',
     u'{http://www.w3.org/2001/XMLSchema-hasFacetAndProperty}hasProperty',
     u'{http://www.w3.org/2001/XMLSchema}all']

Schema objects include methods for finding XSD elements and attributes in the schema.
Those methods are ElementTree's API equivalents, so use an XPath expression for
defining the search criteria:

.. doctest::

    >>> my_schema.find('vh:vehicles/vh:bikes')
    <XsdElement u'{http://example.com/vehicles}bikes' at 0x...>
    >>> pprint(my_schema.findall('vh:vehicles/*'))
    [<XsdElement u'{http://example.com/vehicles}cars' at 0x...>,
     <XsdElement u'{http://example.com/vehicles}bikes' at 0x...>]


Validation
----------

The library provides several methods to validate an XML document with a schema.

The first mode is the method :meth:`XMLSchema.is_valid`. This method returns ``True``
if the XML argument is validated by the schema loaded in the instance,
returns ``False`` if the document is invalid.

.. doctest::

    >>> import xmlschema
    >>> my_schema = xmlschema.XMLSchema('xmlschema/tests/examples/vehicles/vehicles.xsd')
    >>> my_schema.is_valid('xmlschema/tests/examples/vehicles/vehicles.xml')
    True
    >>> my_schema.is_valid('xmlschema/tests/examples/vehicles/vehicles-1_error.xml')
    False
    >>> my_schema.is_valid("""<?xml version="1.0" encoding="UTF-8"?><fancy_tag/>""")
    False

An alternative mode for validating an XML document is implemented by the method
:meth:`XMLSchema.validate`, that raises an error when the XML doesn't conforms
to the schema:

.. doctest::

    >>> import xmlschema
    >>> my_schema = xmlschema.XMLSchema('xmlschema/tests/examples/vehicles/vehicles.xsd')
    >>> my_schema.validate('xmlschema/tests/examples/vehicles/vehicles.xml')
    >>> my_schema.validate('xmlschema/tests/examples/vehicles/vehicles-1_error.xml')
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File "/home/brunato/Development/projects/xmlschema/xmlschema/schema.py", line 220, in validate
        raise error
    xmlschema.exceptions.XMLSchemaValidationError: failed validating <Element ...

    Reason: character data between child elements not allowed!

    Schema:

      <xs:sequence xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:element maxOccurs="unbounded" minOccurs="0" name="car" type="vh:vehicleType" />
      </xs:sequence>

    Instance:

      <ns0:cars xmlns:ns0="http://example.com/vehicles">
        NOT ALLOWED CHARACTER DATA
        <ns0:car make="Porsche" model="911" />
        <ns0:car make="Porsche" model="911" />
      </ns0:cars>


A validation method is also available at module level, useful when you want to
validate a document only once or if you extract information about the schema,
typically the schema location and the namespace, directly from the XML document:

.. doctest::

    >>> import xmlschema
    >>> xmlschema.validate('xmlschema/tests/examples/vehicles/vehicles.xml')

.. doctest:: vehicles

    >>> import xmlschema
    >>> os.chdir('xmlschema/tests/examples/vehicles/')
    >>> xmlschema.validate('vehicles.xml', 'vehicles.xsd')


Data decoding and encoding
--------------------------

Each schema component includes methods for data conversion:

.. doctest::

    >>> my_schema.types['vehicleType'].decode
    <bound method XsdComplexType.decode of <XsdComplexType ...>>
    >>> my_schema.elements['cars'].encode
    <bound method XsdElement.encode of <XsdElement ...>>

.. warning::

    The *encode* methods are not completed yet for this version of the library.


Those methods can be used to decode the correspondents parts of the XML document:

.. doctest::

    >>> import xmlschema
    >>> from pprint import pprint
    >>> from xml.etree import ElementTree
    >>> xs = xmlschema.XMLSchema('xmlschema/tests/examples/vehicles/vehicles.xsd')
    >>> xt = ElementTree.parse('xmlschema/tests/examples/vehicles/vehicles.xml')
    >>> pprint(xs.elements['cars'].decode(xt.getroot()[0]))
    {'{http://example.com/vehicles}car': [{u'@make': u'Porsche',
                                           u'@model': u'911'},
                                          {u'@make': u'Porsche',
                                           u'@model': u'911'}]}
    >>> pprint(xs.elements['cars'].decode(xt.getroot()[1]))
    None
    >>> pprint(xs.elements['bikes'].decode(xt.getroot()[1]))
    {'{http://example.com/vehicles}bike': [{u'@make': u'Harley-Davidson',
                                            u'@model': u'WL'},
                                           {u'@make': u'Yamaha',
                                            u'@model': u'XS650'}]}

You can also decode the entire XML document to a nested dictionary:

.. doctest::

    >>> import xmlschema
    >>> from pprint import pprint
    >>> xs = xmlschema.XMLSchema('xmlschema/tests/examples/vehicles/vehicles.xsd')
    >>> pprint(xs.to_dict('xmlschema/tests/examples/vehicles/vehicles.xml'))
    {u'@xsi:schemaLocation': 'http://example.com/vehicles vehicles.xsd',
     u'vh:bikes': {u'vh:bike': [{u'@make': u'Harley-Davidson', u'@model': u'WL'},
                                {u'@make': u'Yamaha', u'@model': u'XS650'}]},
     u'vh:cars': {u'vh:car': [{u'@make': u'Porsche', u'@model': u'911'},
                              {u'@make': u'Porsche', u'@model': u'911'}]}}

The decoded values coincide with the datatypes declared in the XSD schema:

.. doctest::

    >>> import xmlschema
    >>> from pprint import pprint
    >>> xs = xmlschema.XMLSchema('xmlschema/tests/examples/collection/collection.xsd')
    >>> pprint(xs.to_dict('xmlschema/tests/examples/collection/collection.xml'))
    {u'@xsi:schemaLocation': 'http://example.com/ns/collection collection.xsd',
     'object': [{u'@available': True,
                 u'@id': u'b0836217462',
                 'author': {u'@id': u'PAR',
                            'born': u'1841-02-25',
                            'dead': u'1919-12-03',
                            'name': u'Pierre-Auguste Renoir',
                            'qualification': u'painter'},
                 'estimation': Decimal('10000.00'),
                 'position': 1,
                 'title': u'The Umbrellas',
                 'year': u'1886'},
                {u'@available': True,
                 u'@id': u'b0836217463',
                 'author': {u'@id': u'JM',
                            'born': u'1893-04-20',
                            'dead': u'1983-12-25',
                            'name': u'Joan Mir\xf3',
                            'qualification': u'painter, sculptor and ceramicist'},
                 'position': 2,
                 'title': None,
                 'year': u'1925'}]}

If you need to decode only a part of the XML document you can pass also an XPath
expression using in the *path* argument.

.. doctest::

    >>> xs = xmlschema.XMLSchema('xmlschema/tests/examples/vehicles/vehicles.xsd')
    >>> pprint(xs.to_dict('xmlschema/tests/examples/vehicles/vehicles.xml', './vh:vehicles/vh:bikes'))
    {u'vh:bike': [{u'@make': u'Harley-Davidson', u'@model': u'WL'},
                  {u'@make': u'Yamaha', u'@model': u'XS650'}]}

.. note::

    Decode using an XPath could be simpler than using subelements, method illustrated previously.
    An XPath expression for the schema *considers the schema as the root element with global
    elements as its children*.


Validating and decoding ElementTree XML data
--------------------------------------------

Validation and decode API works also with XML data loaded in ElementTree structures:

.. doctest::

    >>> import xmlschema
    >>> from pprint import pprint
    >>> from xml.etree import ElementTree
    >>> xs = xmlschema.XMLSchema('xmlschema/tests/examples/vehicles/vehicles.xsd')
    >>> xt = ElementTree.parse('xmlschema/tests/examples/vehicles/vehicles.xml')
    >>> xs.is_valid(xt)
    True
    >>> pprint(xs.to_dict(xt, process_namespaces=False), depth=2)
    {u'@{http://www.w3.org/2001/XMLSchema-instance}schemaLocation': 'http://example.com/vehicles vehicles.xsd',
     '{http://example.com/vehicles}bikes': {'{http://example.com/vehicles}bike': [...]},
     '{http://example.com/vehicles}cars': {'{http://example.com/vehicles}car': [...]}}

The standard ElementTree library lacks of namespace information in trees, so you
have to provide a map to convert URIs to prefixes:

    >>> namespaces = {'xsi': 'http://www.w3.org/2001/XMLSchema-instance', 'vh': 'http://example.com/vehicles'}
    >>> pprint(xs.to_dict(xt, namespaces=namespaces))
    {u'@xsi:schemaLocation': 'http://example.com/vehicles vehicles.xsd',
     u'vh:bikes': {u'vh:bike': [{u'@make': u'Harley-Davidson', u'@model': u'WL'},
                                {u'@make': u'Yamaha', u'@model': u'XS650'}]},
     u'vh:cars': {u'vh:car': [{u'@make': u'Porsche', u'@model': u'911'},
                              {u'@make': u'Porsche', u'@model': u'911'}]}}

You can also convert XML data using the lxml_ library, that works better because
namespace information is associated within each node of the trees:

.. doctest::

    >>> import xmlschema
    >>> from pprint import pprint
    >>> import lxml.etree as ElementTree
    >>> xs = xmlschema.XMLSchema('xmlschema/tests/examples/vehicles/vehicles.xsd')
    >>> xt = ElementTree.parse('xmlschema/tests/examples/vehicles/vehicles.xml')
    >>> xs.is_valid(xt)
    True
    >>> pprint(xs.to_dict(xt))
    {u'@xsi:schemaLocation': 'http://example.com/vehicles vehicles.xsd',
     u'vh:bikes': {u'vh:bike': [{u'@make': u'Harley-Davidson', u'@model': u'WL'},
                                {u'@make': u'Yamaha', u'@model': u'XS650'}]},
     u'vh:cars': {u'vh:car': [{u'@make': u'Porsche', u'@model': u'911'},
                              {u'@make': u'Porsche', u'@model': u'911'}]}}
    >>> pprint(xmlschema.to_dict(xt, 'xmlschema/tests/examples/vehicles/vehicles.xsd'))
    {u'@xsi:schemaLocation': 'http://example.com/vehicles vehicles.xsd',
     u'vh:bikes': {u'vh:bike': [{u'@make': u'Harley-Davidson', u'@model': u'WL'},
                                {u'@make': u'Yamaha', u'@model': u'XS650'}]},
     u'vh:cars': {u'vh:car': [{u'@make': u'Porsche', u'@model': u'911'},
                              {u'@make': u'Porsche', u'@model': u'911'}]}}


Customize the decoded data structure
------------------------------------

Starting from the version 0.9.9 the package includes converter objects, in order to
control the decoding process and produce different data structures. Those objects
intervene at element level to compose the decoded data (attributes and content) into
a data structure.

The default converter produces a data structure similar to the format produced by
previous versions of the package. You can customize the conversion process providing
a converter instance or subclass when you create a schema instance or when you want
to decode an XML document.
For instance, for use a Badgerfish convention converter for a schema instance:

.. doctest::

    >>> import xmlschema
    >>> from pprint import pprint
    >>> xml_schema = 'xmlschema/tests/examples/vehicles/vehicles.xsd'
    >>> xml_document = 'xmlschema/tests/examples/vehicles/vehicles.xml'
    >>> xs = xmlschema.XMLSchema(xml_schema, converter=xmlschema.BadgerFishConverter)
    >>> pprint(xs.to_dict(xml_document, dict_class=dict), indent=4)
    {   '@xmlns': {   u'vh': 'http://example.com/vehicles',
                      u'xsi': 'http://www.w3.org/2001/XMLSchema-instance'},
        u'vh:vehicles': {   u'@xsi:schemaLocation': 'http://example.com/vehicles vehicles.xsd',
                            u'vh:bikes': {   u'vh:bike': [   {   u'@make': u'Harley-Davidson',
                                                                 u'@model': u'WL'},
                                                             {   u'@make': u'Yamaha',
                                                                 u'@model': u'XS650'}]},
                            u'vh:cars': {   u'vh:car': [   {   u'@make': u'Porsche',
                                                               u'@model': u'911'},
                                                           {   u'@make': u'Porsche',
                                                               u'@model': u'911'}]}}}

You can also change the data decoding process providing the keyword argument *converter*
at method level:

.. doctest::

    >>> pprint(xs.to_dict(xml_document, converter=xmlschema.ParkerConverter, dict_class=dict), indent=4)
    {   u'vh:bikes': {   u'vh:bike': [None, None]},
        u'vh:cars': {   u'vh:car': [None, None]}}


Decoding to JSON
----------------

The data structured created by the decoder can be easily serialized to JSON. But if you data
include `Decimal` values (for *decimal* XSD built-in type) you cannot convert the data to JSON:

.. doctest::

    >>> import xmlschema
    >>> import json
    >>> xml_document = 'xmlschema/tests/examples/collection/collection.xml'
    >>> print(json.dumps(xmlschema.to_dict(xml_document), indent=4))
    Traceback (most recent call last):
      File "/usr/lib64/python2.7/doctest.py", line 1315, in __run
        compileflags, 1) in test.globs
      File "<doctest default[3]>", line 1, in <module>
        print(json.dumps(xmlschema.to_dict(xml_document), indent=4))
      File "/usr/lib64/python2.7/json/__init__.py", line 251, in dumps
        sort_keys=sort_keys, **kw).encode(obj)
      File "/usr/lib64/python2.7/json/encoder.py", line 209, in encode
        chunks = list(chunks)
      File "/usr/lib64/python2.7/json/encoder.py", line 434, in _iterencode
        for chunk in _iterencode_dict(o, _current_indent_level):
      File "/usr/lib64/python2.7/json/encoder.py", line 408, in _iterencode_dict
        for chunk in chunks:
      File "/usr/lib64/python2.7/json/encoder.py", line 332, in _iterencode_list
        for chunk in chunks:
      File "/usr/lib64/python2.7/json/encoder.py", line 408, in _iterencode_dict
        for chunk in chunks:
      File "/usr/lib64/python2.7/json/encoder.py", line 442, in _iterencode
        o = _default(o)
      File "/usr/lib64/python2.7/json/encoder.py", line 184, in default
        raise TypeError(repr(o) + " is not JSON serializable")
    TypeError: Decimal('10000.00') is not JSON serializable

This problem is resolved providing an alternative JSON-compatible type for `Decimal` values,
using the keyword argument *decimal_type*:

.. doctest::

    >>> print(json.dumps(xmlschema.to_dict(xml_document, decimal_type=str), indent=4))  # doctest: +SKIP
    {
        "object": [
            {
                "@available": true,
                "author": {
                    "qualification": "painter",
                    "born": "1841-02-25",
                    "@id": "PAR",
                    "name": "Pierre-Auguste Renoir",
                    "dead": "1919-12-03"
                },
                "title": "The Umbrellas",
                "year": "1886",
                "position": 1,
                "estimation": "10000.00",
                "@id": "b0836217462"
            },
            {
                "@available": true,
                "author": {
                    "qualification": "painter, sculptor and ceramicist",
                    "born": "1893-04-20",
                    "@id": "JM",
                    "name": "Joan Mir\u00f3",
                    "dead": "1983-12-25"
                },
                "title": null,
                "year": "1925",
                "position": 2,
                "@id": "b0836217463"
            }
        ],
        "@xsi:schemaLocation": "http://example.com/ns/collection collection.xsd"
    }


XSD validation modes
--------------------

Starting from the version 0.9.10 the library uses XSD validation modes *strict*/*lax*/*skip*,
both for schemas and for XML instances. Each validation mode defines a specific behaviour:

strict
    Schemas are validated against the meta-schema. The processor stops when an error is
    found in a schema or during the validation/decode of XML data.

lax
    Schemas are validated against the meta-schema. The processor collects the errors
    and continues, eventually replacing missing parts with wildcards.
    Undecodable XML data are replaced with `None`.

skip
    Schemas are not validated against the meta-schema. The processor doesn't collect
    any error. Undecodable XML data are replaced with the original text.

The default mode is *strict*, both for schemas and for XML data. The mode is set with
*validation* argument, provided when creating the schema instance or when you want to
validate/decode XML data.
For example you can build a schema using a *strict* mode and then decode XML data
using a *validation* argument set to 'lax'.
