=========
xmlschema
=========

This is an implementation of `XML Schema <http://www.w3.org/2001/XMLSchema>`_
for Python (supports versions 2.7 and Python 3).

Features
--------

* Validate the XML instances to an XML schema

* Provides data type conversion from and to XML

* Converts XML instances to Python dictionaries


Installation and usage
----------------------

You can install the library with::

    pip install xmlschema

then you can import the library::

    import xmlschema

and create an instance of a schema with::

    my_schema = xmlschema.XMLSchema(<path to your XSD schema file>)

Validation
**********

Using a XMLSchema instance you can validate files based on that schema::

   my_schema.is_valid(<path to an XML file based on your XSD schema>)

that returns a boolean value, or::

   my_schema.validate(<path to an XML file based on your XSD schema>)

to raise an error when the file is not validated.

If you need to validate once a file you can the module's call::

   xmlschema.validate(<path to the XML file>, <path to XSD schema file>)

Data conversion
***************

A schema instance includes APIs for XSD types defined on the schema::

    my_schema.types[<XSD type name>].decode(<XML text>)       # Decode XML text to data
    my_schema.types[<XSD type name>].encode(<data instance>)  # Decode a data to and XML text

You can also converts the entire XML document to a nested dictionary with data conversion::

    from xml.etree import ElementTree
    my_xml = ElementTree.parse(<path to an XML file based on your XSD schema>)
    my_schema = xmlschema.XMLSchema(<path to your XSD schema file>)
    xmlschema.etree_to_dict(my_xml, my_schema)


Running Tests
-------------
The package uses the Python's *unitest* library. The tests are located in ``tests/`` directory.
There are three scripts to test the package:

  tests/test_schemas.py
    Tests about parsing of XSD Schemas

  tests/test_validation.py
    Tests about XML validation

  tests/test_decoding.py
    Tests regarding XML data decoding

There are some basic tests published on xmlschema's GitHub repository, but you can add your
own tests in a subdirectory as a Git module::

    mkdir tests/my_schemas
    cd tests/my_schemas
    git init
    touch testfiles

Add to this file the relative or absolute paths of files to be tested, one per line.
The file path maybe followed by the number of errors that have to be found in the XML
to pass the test.


Release Notes
-------------
This release conforming to XML Schema version 1.0, but maybe extended to 1.1 in nearly
future releases. Maybe soon will be available a manual for users and developers.

License
-------
This software is distributed under the terms of the MIT License.
See the file 'LICENSE' in the root directory of the present
distribution, or http://opensource.org/licenses/MIT.
