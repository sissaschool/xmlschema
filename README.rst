=========
xmlschema
=========

This is an implementation of `XML Schema <http://www.w3.org/2001/XMLSchema>`_
for Python (supports versions 2.7 and Python 3).

Features
--------

* Builds XML schema objects from XSD files

* Validates the XML instances with the XSD schema

* Converts XML instances into Python dictionaries

* Provides decoding and encoding APIs for XML's elements and attributes


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

Using a XMLSchema object you can validate XML files based on that schema::

   my_schema.is_valid(<path to an XML file based on your XSD schema>)  # returns True or False

If you prefer to raise an exception when the XML file is not validated you can choose another call::

   my_schema.validate(<path to an XML file based on your XSD schema>)

If you need to validate only once a file with a particular schema you can use the module's call::

   xmlschema.validate(<path to the XML file>, <path to XSD schema file>)

Data decode and encode
**********************

A schema object includes APIs for decoding and encoding the XSD types defined in the schema::

    my_schema.types[<XSD type name>].decode(<XML text>)       # Decode XML text or elem to data
    my_schema.types[<XSD type name>].encode(<data instance>)  # Decode a data to and XML text

You can also convert the entire XML document to a nested dictionary with data conversion::

    my_schema = xmlschema.XMLSchema(<path to your XSD schema file>)
    my_schema.to_dict(<path to an XML file based on your XSD schema>)


Running Tests
-------------
The package uses the Python's *unitest* library. The tests are located in the
directory ``tests/``. There are three scripts to test the package:

  tests/test_schemas.py
    Tests about parsing of XSD Schemas

  tests/test_validation.py
    Tests about XML validation

  tests/test_decoding.py
    Tests regarding XML data decoding

There are only some basic tests published on xmlschema's GitHub repository, but you
can add your own tests in a subdirectory as a Git module::

    git clone https://github.com/brunato/xmlschema.git
    mkdir xmlschema/xmlschema/tests/extra-schemas
    cd xmlschema/xmlschema/tests/extra-schemas
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
