************
Introduction
************

The *xmlschema* library is an implementation of `XML Schema <http://www.w3.org/2001/XMLSchema>`_
for Python (supports versions 2.7 and Python 3.3+).

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
