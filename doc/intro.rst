************
Introduction
************

The *xmlschema* library arises from the needs of a solid Python layer for processing XML Schema
based files for `MaX (Materials design at the Exascale) <http://www.max-centre.eu>`_  European project.
A significant problem was the encoding and the decoding of the XML data files produced by different
simulation software.
Another important requirement was the XML data validation, in order to put the data production under control.
The lack of a suitable alternative for Python in the encoding/decoding of data has led to build a new library.
This library is obviously useful for all the cases related to XML Schema based processing, not only for
the original scope.

Features
========

The xmlschema library include those features:

* Builds XML schema objects from XSD files
* Validates the XML instances with the XSD schema
* Converts XML instances into Python dictionaries
* Provides decoding and encoding APIs for XML's elements and attributes

Installation
============

You can install the library with *pip* in a Python 2.7 or Python 3.4+ environment::

    pip install xmlschema

The library uses the Python's ElementTree XML library and doesn't require additional packages.
The library includes also the schemas of the XML Schema standards for working offline and to
speed-up the building of schema instances.
