*********
xmlschema
*********

.. xmlschema-introduction-start

The *xmlschema* library is an implementation of `XML Schema <http://www.w3.org/2001/XMLSchema>`_
for Python (supports Python 2.7 and Python 3.4+).

This library arises from the needs of a solid Python layer for processing XML
Schema based files for
`MaX (Materials design at the Exascale) <http://www.max-centre.eu>`_  European project.
A significant problem is the encoding and the decoding of the XML data files
produced by different simulation software.
Another important requirement is the XML data validation, in order to put the
produced data under control. The lack of a suitable alternative for Python in
the schema-based decoding of XML data has led to build this library. Obviously
this library can be useful for other cases related to XML Schema based processing,
not only for the original scope.

The full `xmlschema documentation is available on "Read the Docs" <http://xmlschema.readthedocs.io/en/latest/>`_.


Features
========

The xmlschema library includes the following features:

* Full XSD 1.0 support
* Building of XML schema objects from XSD files
* Validation of XML instances against XSD schemas
* Decoding of XML data into Python data structures
* An XPath based API for finding schema's elements and attributes
* Support of XSD validation modes
* XML-based attacks prevention using the external package *defusedxml*


Installation
============

You can install the library with *pip* in a Python 2.7 or Python 3.4+ environment::

    pip install xmlschema

The library uses the Python's ElementTree XML library and doesn't require additional
packages. The library includes also the schemas of the XML Schema standards for working
offline and to speed-up the building of schema instances.

.. xmlschema-introduction-end


Usage
=====

Import the library and then create a schema instance using the path of
the file containing the schema as argument:

.. code-block:: pycon

    >>> import xmlschema
    >>> my_schema = xmlschema.XMLSchema('xmlschema/tests/cases/examples/vehicles/vehicles.xsd')

The schema can be used to validate XML documents:

.. code-block:: pycon

    >>> my_schema.is_valid('xmlschema/tests/cases/examples/vehicles/vehicles.xml')
    True
    >>> my_schema.is_valid('xmlschema/tests/cases/examples/vehicles/vehicles-1_error.xml')
    False
    >>> my_schema.validate('xmlschema/tests/cases/examples/vehicles/vehicles-1_error.xml')
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File "/home/brunato/Development/projects/xmlschema/xmlschema/validators/xsdbase.py", line 393, in validate
        raise error
    xmlschema.validators.exceptions.XMLSchemaValidationError: failed validating <Element '{http://example.com/vehicles}cars' at 0x7f8032768458> with XsdGroup(model='sequence').

    Reason: character data between child elements not allowed!

    Schema:

      <xs:sequence xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:element maxOccurs="unbounded" minOccurs="0" name="car" type="vh:vehicleType" />
      </xs:sequence>

    Instance:

      <vh:cars xmlns:vh="http://example.com/vehicles">
        NOT ALLOWED CHARACTER DATA
        <vh:car make="Porsche" model="911" />
        <vh:car make="Porsche" model="911" />
      </vh:cars>

Using a schema you can also decode the XML documents to nested dictionaries, with
values that match to the data types declared by the schema:

.. code-block:: pycon

    >>> import xmlschema
    >>> from pprint import pprint
    >>> xs = xmlschema.XMLSchema('xmlschema/tests/cases/examples/collection/collection.xsd')
    >>> pprint(xs.to_dict('xmlschema/tests/cases/examples/collection/collection.xml'))
    {'@xsi:schemaLocation': 'http://example.com/ns/collection collection.xsd',
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

License
=======
This software is distributed under the terms of the MIT License.
See the file 'LICENSE' in the root directory of the present
distribution, or http://opensource.org/licenses/MIT.

Roadmap
=======

* Validated XML data encoding
* XSD 1.1
