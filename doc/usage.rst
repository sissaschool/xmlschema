Usage
=====

.. _lxml: http://lxml.de

.. testsetup::

    import xmlschema
    import os
    import warnings
    os.chdir('..')
    warnings.simplefilter("ignore", xmlschema.XMLSchemaIncludeWarning)

.. testsetup:: vehicles

    import xmlschema
    import os

Import the library in your code with::

    import xmlschema

The module initialization builds the dictionary containing the code points of
the Unicode categories.


Create a schema instance
------------------------

Import the library and then create an instance of a schema using the path of
the file containing the schema as argument:

.. doctest::

    >>> import xmlschema
    >>> schema = xmlschema.XMLSchema('tests/test_cases/examples/vehicles/vehicles.xsd')

Otherwise the argument can be also an opened file-like object:

.. doctest::

    >>> import xmlschema
    >>> schema_file = open('tests/test_cases/examples/collection/collection.xsd')
    >>> schema = xmlschema.XMLSchema(schema_file)

Alternatively you can pass a string containing the schema definition:

.. doctest::

    >>> import xmlschema
    >>> schema = xmlschema.XMLSchema("""
    ... <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
    ... <xs:element name="block" type="xs:string"/>
    ... </xs:schema>
    ... """)

Strings and file-like objects might not work when the schema includes other local subschemas,
because the package cannot knows anything about the schema's source location:

.. doctest::

    >>> import xmlschema
    >>> schema_xsd = open('tests/test_cases/examples/vehicles/vehicles.xsd').read()
    >>> schema = xmlschema.XMLSchema(schema_xsd)
    Traceback (most recent call last):
    ...
    ...
    xmlschema.validators.exceptions.XMLSchemaParseError: unknown element '{http://example.com/vehicles}cars':

    Schema:

      <xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" ref="vh:cars" />

    Path: /xs:schema/xs:element/xs:complexType/xs:sequence/xs:element

In these cases you can provide an appropriate *base_url* optional argument to define the
reference directory path for other includes and imports:

.. doctest::

    >>> import xmlschema
    >>> schema_file = open('tests/test_cases/examples/vehicles/vehicles.xsd')
    >>> schema = xmlschema.XMLSchema(schema_file, base_url='tests/test_cases/examples/vehicles/')


XSD declarations
----------------

The schema object includes XSD components of declarations (*elements*, *attributes* and *notations*)
and definitions (*types*, *model groups*, *attribute groups*, *identity constraints* and *substitution
groups*). The global XSD components are available as attributes of the schema instance:

.. doctest::

    >>> import xmlschema
    >>> from pprint import pprint
    >>> schema = xmlschema.XMLSchema('tests/test_cases/examples/vehicles/vehicles.xsd')
    >>> schema.types
    NamespaceView({'vehicleType': XsdComplexType(name='vehicleType')})
    >>> pprint(dict(schema.elements))
    {'bikes': XsdElement(name='vh:bikes', occurs=[1, 1]),
     'cars': XsdElement(name='vh:cars', occurs=[1, 1]),
     'vehicles': XsdElement(name='vh:vehicles', occurs=[1, 1])}
    >>> schema.attributes
    NamespaceView({'step': XsdAttribute(name='vh:step')})

Global components are local views of *XSD global maps* shared between related schema instances.
The global maps can be accessed through :attr:`XMLSchema.maps` attribute:

.. doctest::

    >>> from pprint import pprint
    >>> pprint(sorted(schema.maps.types.keys())[:5])
    ['{http://example.com/vehicles}vehicleType',
     '{http://www.w3.org/2001/XMLSchema}ENTITIES',
     '{http://www.w3.org/2001/XMLSchema}ENTITY',
     '{http://www.w3.org/2001/XMLSchema}ID',
     '{http://www.w3.org/2001/XMLSchema}IDREF']
    >>> pprint(sorted(schema.maps.elements.keys())[:10])
    ['{http://example.com/vehicles}bikes',
     '{http://example.com/vehicles}cars',
     '{http://example.com/vehicles}vehicles',
     '{http://www.w3.org/2001/XMLSchema}all',
     '{http://www.w3.org/2001/XMLSchema}annotation',
     '{http://www.w3.org/2001/XMLSchema}any',
     '{http://www.w3.org/2001/XMLSchema}anyAttribute',
     '{http://www.w3.org/2001/XMLSchema}appinfo',
     '{http://www.w3.org/2001/XMLSchema}attribute',
     '{http://www.w3.org/2001/XMLSchema}attributeGroup']

Schema objects include methods for finding XSD elements and attributes in the schema.
Those are methods ot the ElementTree's API, so you can use an XPath expression for
defining the search criteria:

.. doctest::

    >>> schema.find('vh:vehicles/vh:bikes')
    XsdElement(ref='vh:bikes', occurs=[1, 1])
    >>> pprint(schema.findall('vh:vehicles/*'))
    [XsdElement(ref='vh:cars', occurs=[1, 1]),
     XsdElement(ref='vh:bikes', occurs=[1, 1])]


Validation
----------

The library provides several methods to validate an XML document with a schema.

The first mode is the method :meth:`XMLSchema.is_valid`. This method returns ``True``
if the XML argument is validated by the schema loaded in the instance,
returns ``False`` if the document is invalid.

.. doctest::

    >>> import xmlschema
    >>> schema = xmlschema.XMLSchema('tests/test_cases/examples/vehicles/vehicles.xsd')
    >>> schema.is_valid('tests/test_cases/examples/vehicles/vehicles.xml')
    True
    >>> schema.is_valid('tests/test_cases/examples/vehicles/vehicles-1_error.xml')
    False
    >>> schema.is_valid("""<?xml version="1.0" encoding="UTF-8"?><fancy_tag/>""")
    False

An alternative mode for validating an XML document is implemented by the method
:meth:`XMLSchema.validate`, that raises an error when the XML doesn't conforms
to the schema:

.. doctest::

    >>> import xmlschema
    >>> schema = xmlschema.XMLSchema('tests/test_cases/examples/vehicles/vehicles.xsd')
    >>> schema.validate('tests/test_cases/examples/vehicles/vehicles.xml')
    >>> schema.validate('tests/test_cases/examples/vehicles/vehicles-1_error.xml')
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


A validation method is also available at module level, useful when you need to
validate a document only once or if you extract information about the schema,
typically the schema location and the namespace, directly from the XML document:

.. doctest::

    >>> import xmlschema
    >>> xmlschema.validate('tests/test_cases/examples/vehicles/vehicles.xml')

.. doctest:: vehicles

    >>> import xmlschema
    >>> os.chdir('tests/test_cases/examples/vehicles/')
    >>> xmlschema.validate('vehicles.xml', 'vehicles.xsd')


Data decoding and encoding
--------------------------

Each schema component includes methods for data conversion:

.. doctest::

    >>> schema.types['vehicleType'].decode
    <bound method XsdComplexType.decode of XsdComplexType(name='vehicleType')>
    >>> schema.elements['cars'].encode
    <bound method ValidationMixin.encode of XsdElement(name='vh:cars', occurs=[1, 1])>


Those methods can be used to decode the correspondents parts of the XML document:

.. doctest::

    >>> import xmlschema
    >>> from pprint import pprint
    >>> from xml.etree import ElementTree
    >>> xs = xmlschema.XMLSchema('tests/test_cases/examples/vehicles/vehicles.xsd')
    >>> xt = ElementTree.parse('tests/test_cases/examples/vehicles/vehicles.xml')
    >>> root = xt.getroot()
    >>> pprint(xs.elements['cars'].decode(root[0]))
    {'{http://example.com/vehicles}car': [{'@make': 'Porsche', '@model': '911'},
                                          {'@make': 'Porsche', '@model': '911'}]}
    >>> pprint(xs.elements['cars'].decode(xt.getroot()[1], validation='skip'))
    None
    >>> pprint(xs.elements['bikes'].decode(root[1], namespaces={'vh': 'http://example.com/vehicles'}))
    {'@xmlns:vh': 'http://example.com/vehicles',
     'vh:bike': [{'@make': 'Harley-Davidson', '@model': 'WL'},
                 {'@make': 'Yamaha', '@model': 'XS650'}]}

You can also decode the entire XML document to a nested dictionary:

.. doctest::

    >>> import xmlschema
    >>> from pprint import pprint
    >>> xs = xmlschema.XMLSchema('tests/test_cases/examples/vehicles/vehicles.xsd')
    >>> pprint(xs.to_dict('tests/test_cases/examples/vehicles/vehicles.xml'))
    {'@xmlns:vh': 'http://example.com/vehicles',
     '@xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
     '@xsi:schemaLocation': 'http://example.com/vehicles vehicles.xsd',
     'vh:bikes': {'vh:bike': [{'@make': 'Harley-Davidson', '@model': 'WL'},
                              {'@make': 'Yamaha', '@model': 'XS650'}]},
     'vh:cars': {'vh:car': [{'@make': 'Porsche', '@model': '911'},
                            {'@make': 'Porsche', '@model': '911'}]}}

The decoded values coincide with the datatypes declared in the XSD schema:

.. doctest::

    >>> import xmlschema
    >>> from pprint import pprint
    >>> xs = xmlschema.XMLSchema('tests/test_cases/examples/collection/collection.xsd')
    >>> pprint(xs.to_dict('tests/test_cases/examples/collection/collection.xml'))
    {'@xmlns:col': 'http://example.com/ns/collection',
     '@xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
     '@xsi:schemaLocation': 'http://example.com/ns/collection collection.xsd',
     'object': [{'@available': True,
                 '@id': 'b0836217462',
                 'author': {'@id': 'PAR',
                            'born': '1841-02-25',
                            'dead': '1919-12-03',
                            'name': 'Pierre-Auguste Renoir',
                            'qualification': 'painter'},
                 'estimation': Decimal('10000.00'),
                 'position': 1,
                 'title': 'The Umbrellas',
                 'year': '1886'},
                {'@available': True,
                 '@id': 'b0836217463',
                 'author': {'@id': 'JM',
                            'born': '1893-04-20',
                            'dead': '1983-12-25',
                            'name': 'Joan Miró',
                            'qualification': 'painter, sculptor and ceramicist'},
                 'position': 2,
                 'title': None,
                 'year': '1925'}]}

If you need to decode only a part of the XML document you can pass also an XPath
expression using in the *path* argument.

.. doctest::

    >>> xs = xmlschema.XMLSchema('tests/test_cases/examples/vehicles/vehicles.xsd')
    >>> pprint(xs.to_dict('tests/test_cases/examples/vehicles/vehicles.xml', '/vh:vehicles/vh:bikes'))
    {'vh:bike': [{'@make': 'Harley-Davidson', '@model': 'WL'},
                 {'@make': 'Yamaha', '@model': 'XS650'}]}

.. note::

    Decode using an XPath could be simpler than using subelements, method illustrated previously.
    An XPath expression for the schema *considers the schema as the root element with global
    elements as its children*.

All the decoding and encoding methods are based on two generator methods of the `XMLSchema` class,
namely *iter_decode()* and *iter_encode()*, that yield both data and validation errors.
See :ref:`schema-level-api` section for more information.


Validating and decoding ElementTree's elements
----------------------------------------------

Validation and decode API works also with XML data loaded in ElementTree structures:

.. doctest::

    >>> import xmlschema
    >>> from pprint import pprint
    >>> from xml.etree import ElementTree
    >>> xs = xmlschema.XMLSchema('tests/test_cases/examples/vehicles/vehicles.xsd')
    >>> xt = ElementTree.parse('tests/test_cases/examples/vehicles/vehicles.xml')
    >>> xs.is_valid(xt)
    True
    >>> pprint(xs.to_dict(xt, process_namespaces=False), depth=2)
    {'@{http://www.w3.org/2001/XMLSchema-instance}schemaLocation': 'http://...',
     '{http://example.com/vehicles}bikes': {'{http://example.com/vehicles}bike': [...]},
     '{http://example.com/vehicles}cars': {'{http://example.com/vehicles}car': [...]}}

The standard ElementTree library lacks of namespace information in trees, so you
have to provide a map to convert URIs to prefixes:

    >>> namespaces = {'xsi': 'http://www.w3.org/2001/XMLSchema-instance', 'vh': 'http://example.com/vehicles'}
    >>> pprint(xs.to_dict(xt, namespaces=namespaces))
    {'@xmlns:vh': 'http://example.com/vehicles',
     '@xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
     '@xsi:schemaLocation': 'http://example.com/vehicles vehicles.xsd',
     'vh:bikes': {'vh:bike': [{'@make': 'Harley-Davidson', '@model': 'WL'},
                              {'@make': 'Yamaha', '@model': 'XS650'}]},
     'vh:cars': {'vh:car': [{'@make': 'Porsche', '@model': '911'},
                            {'@make': 'Porsche', '@model': '911'}]}}

You can also convert XML data using the lxml_ library, that works better because
namespace information is associated within each node of the trees:

.. doctest::

    >>> import xmlschema
    >>> from pprint import pprint
    >>> import lxml.etree as ElementTree
    >>> xs = xmlschema.XMLSchema('tests/test_cases/examples/vehicles/vehicles.xsd')
    >>> xt = ElementTree.parse('tests/test_cases/examples/vehicles/vehicles.xml')
    >>> xs.is_valid(xt)
    True
    >>> pprint(xs.to_dict(xt))
    {'@xmlns:vh': 'http://example.com/vehicles',
     '@xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
     '@xsi:schemaLocation': 'http://example.com/vehicles vehicles.xsd',
     'vh:bikes': {'vh:bike': [{'@make': 'Harley-Davidson', '@model': 'WL'},
                              {'@make': 'Yamaha', '@model': 'XS650'}]},
     'vh:cars': {'vh:car': [{'@make': 'Porsche', '@model': '911'},
                            {'@make': 'Porsche', '@model': '911'}]}}
    >>> pprint(xmlschema.to_dict(xt, 'tests/test_cases/examples/vehicles/vehicles.xsd'))
    {'@xmlns:vh': 'http://example.com/vehicles',
     '@xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
     '@xsi:schemaLocation': 'http://example.com/vehicles vehicles.xsd',
     'vh:bikes': {'vh:bike': [{'@make': 'Harley-Davidson', '@model': 'WL'},
                              {'@make': 'Yamaha', '@model': 'XS650'}]},
     'vh:cars': {'vh:car': [{'@make': 'Porsche', '@model': '911'},
                            {'@make': 'Porsche', '@model': '911'}]}}


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
For instance you can use the *Badgerfish* converter for a schema instance:

.. doctest::

    >>> import xmlschema
    >>> from pprint import pprint
    >>> xml_schema = 'tests/test_cases/examples/vehicles/vehicles.xsd'
    >>> xml_document = 'tests/test_cases/examples/vehicles/vehicles.xml'
    >>> xs = xmlschema.XMLSchema(xml_schema, converter=xmlschema.BadgerFishConverter)
    >>> pprint(xs.to_dict(xml_document, dict_class=dict), indent=4)
    {   '@xmlns': {   'vh': 'http://example.com/vehicles',
                      'xsi': 'http://www.w3.org/2001/XMLSchema-instance'},
        'vh:vehicles': {   '@xsi:schemaLocation': 'http://example.com/vehicles '
                                                  'vehicles.xsd',
                           'vh:bikes': {   'vh:bike': [   {   '@make': 'Harley-Davidson',
                                                              '@model': 'WL'},
                                                          {   '@make': 'Yamaha',
                                                              '@model': 'XS650'}]},
                           'vh:cars': {   'vh:car': [   {   '@make': 'Porsche',
                                                            '@model': '911'},
                                                        {   '@make': 'Porsche',
                                                            '@model': '911'}]}}}

You can also change the data decoding process providing the keyword argument *converter* to the method call:

.. doctest::

    >>> pprint(xs.to_dict(xml_document, converter=xmlschema.ParkerConverter, dict_class=dict), indent=4)
    {'vh:bikes': {'vh:bike': [None, None]}, 'vh:cars': {'vh:car': [None, None]}}


See the :ref:`customize-output-data` section for more information about converters.


Decoding to JSON
----------------

The data structured created by the decoder can be easily serialized to JSON. But if you data
include `Decimal` values (for *decimal* XSD built-in type) you cannot convert the data to JSON:

.. doctest::

    >>> import xmlschema
    >>> import json
    >>> xml_document = 'tests/test_cases/examples/collection/collection.xml'
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

From version 1.0 there are two module level API for simplify the JSON serialization and deserialization task.
See the :meth:`xmlschema.to_json` and :meth:`xmlschema.from_json` in the :ref:`document-level-api` section.

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
the *validation* argument, provided when creating the schema instance or when you want to
validate/decode XML data.
For example you can build a schema using a *strict* mode and then decode XML data
using the *validation* argument setted to 'lax'.

.. note::
    From release v1.1.1 the *iter_decode()* and *iter_encode()* methods propagate
    errors also for *skip* validation mode. The errors generated in *skip* mode are
    discarded by the top-level methods *decode()* and *encode()*.


Lazy validation
---------------

From release v1.0.12 the document validation and decoding API has an optional argument `lazy=False`,
that can be changed to True for operating with a lazy :class:`XMLResource`. The lazy mode can be
useful for validating and decoding big XML data files. This is still an experimental feature that
will be refined and integrated in future versions.


XSD 1.0 and 1.1 support
-----------------------
From release v1.0.14 XSD 1.1 support has been added to the library through the class
:class:`XMLSchema11`. You have to use this class for XSD 1.1 schemas instead the default
class :class:`XMLSchema` that is still linked to XSD 1.0 validator :class:`XMLSchema10`.
From next minor release (v1.1) the default class will become :class:`XMLSchema11`.


XML entity-based attacks protection
-----------------------------------

The XML data resource loading is protected using the  `SafeXMLParser` class, a subclass of
the pure Python version of XMLParser that forbids the use of entities.
The protection is applied both to XSD schemas and to XML data. The usage of this feature is
regulated by the XMLSchema's argument *defuse*.
For default this argument has value *'remote'* that means the protection on XML data is
applied only to data loaded from remote. Other values for this argument can be *'always'*
and *'never'*.

Processing limits
-----------------

From release v1.0.16 a module has been added in order to group constants that define
processing limits, generally to protect against attacks prepared to exhaust system
resources. These limits usually don't need to be changed, but this possibility has
been left at the module level for situations where a different setting is needed.

Limit on XSD model groups checking
..................................

Model groups of the schemas are checked against restriction violations and *Unique Particle
Attribution* violations. To avoids XSD model recursion attacks a depth limit of 15 levels
is set. If this limit is exceeded an ``XMLSchemaModelDepthError`` is raised, the error is
caught and a warning is generated. If you need to set an higher limit for checking all your
groups you can import the library and change the value of ``MAX_MODEL_DEPTH`` in the limits
module:

.. doctest::

    >>> import xmlschema
    >>> xmlschema.limits.MAX_MODEL_DEPTH = 20


Limit on XML data depth
.......................

A limit of 9999 on maximum depth is set for XML validation/decoding/encoding to avoid
attacks based on extremely deep XML data. To increase or decrease this limit change the
value of ``MAX_XML_DEPTH`` in the module *limits* after the import of the package:

.. doctest::

    >>> import xmlschema
    >>> xmlschema.limits.MAX_XML_DEPTH = 1000


