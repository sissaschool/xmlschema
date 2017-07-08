*********
xmlschema
*********

This package is an implementation of `XML Schema <http://www.w3.org/2001/XMLSchema>`_
for Python (supports versions 2.7 and Python 3.3+).

This is a library that arises from the needs of a solid Python layer for processing XML
Schema based files for
`MaX (Materials design at the Exascale) <http://www.max-centre.eu>`_  European project.
A significant problem is the encoding and the decoding of the XML data files
produced by different simulation software.
Another important requirement is the XML data validation, in order to put the
produced data under control. The lack of a suitable alternative for Python in
the schema-based decoding of XML data has led to build this library. Obviously
this library can be useful for other cases related to XML Schema based processing,
not only for the original scope.

Features
========

The xmlschema library includes the following features:

* Building of XML schema objects from XSD files
* Validation of XML instances with XSD schemas
* Decoding of XML data into Python data structures
* An XPath based API for finding schema's elements and attributes
* Support of XSD validation modes

Installation
============

You can install the library with *pip* in a Python 2.7 or Python 3.3+ environment::

    pip install xmlschema

The library uses the Python's ElementTree XML library and doesn't require additional
packages. The library includes also the schemas of the XML Schema standards for working
offline and to speed-up the building of schema instances.

Usage
=====

Import the library and then create an instance of a schema using the path of
the file containing the schema as argument:

.. code-block:: pycon

    >>> import xmlschema
    >>> my_schema = xmlschema.XMLSchema('xmlschema/tests/examples/vehicles/vehicles.xsd')

The schema can be used to validate XML documents:

.. code-block:: pycon

    >>> my_schema.is_valid('xmlschema/tests/examples/vehicles/vehicles.xml')
    True
    >>> my_schema.is_valid('xmlschema/tests/examples/vehicles/vehicles-1_error.xml')
    False
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

Using a schema you can also decode the XML documents to nested dictionaries, with
values that corresponds to the data types declared by the schema:

.. code-block:: pycon

    >>> import xmlschema
    >>> from pprint import pprint
    >>> xs = xmlschema.XMLSchema('xmlschema/tests/examples/collection/collection.xsd')
    >>> pprint(xs.to_dict('xmlschema/tests/examples/collection/collection.xml'))
    {u'@xsi:schemaLocation': 'http://example.com/ns/collection collection.xsd',
     'object': [{'@available': True,
                 '@id': u'b0836217462',
                 'author': {'@id': u'PAR',
                            'born': u'1841-02-25',
                            'dead': u'1919-12-03',
                            'name': u'Pierre-Auguste Renoir',
                            'qualification': u'painter'},
                 'estimation': Decimal('10000.00'),
                 'position': 1,
                 'title': u'The Umbrellas',
                 'year': u'1886'},
                {'@available': True,
                 '@id': u'b0836217463',
                 'author': {'@id': u'JM',
                            'born': u'1893-04-20',
                            'dead': u'1983-12-25',
                            'name': u'Joan Mir\xf3',
                            'qualification': u'painter, sculptor and ceramicist'},
                 'position': 2,
                 'title': None,
                 'year': u'1925'}]}

License
-------
This software is distributed under the terms of the MIT License.
See the file 'LICENSE' in the root directory of the present
distribution, or http://opensource.org/licenses/MIT.

Roadmap
-------

* Full XSD 1.0 support
* Validated XML data encoding
* XSD 1.1