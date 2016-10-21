************
Introduction
************

The *xmlschema* library arises from the need of a solid Python layer for processing XML Schema
based files for `MaX (Materials design at the Exascale) <http://www.max-centre.eu>`_  European project.
The main problem was the encoding and the decoding of XML data files produced by simulation software.
Another important requirement was the XML data validation, in order to put the data production under control.
The lack of a suitable alternative for Python, particularly in the encoding/decoding of data, resulted
to the decision of creating a new library.
The library is obviously useful for all the cases related to XML Schema based processing,
not only for the original scope.

Features
========

The xmlschema library include those features:

* Validate the XML instances to an XML schema
* Provides data type conversion from and to XML
* Converts XML instances to Python dictionaries

Installation
============

You can install the library with *pip* in a Python 2.7 or Python 3.4+ environment::

    pip install xmlschema

The library uses the Python's ElementTree XML library and doesn't require additional packages.
The library includes also the schemas of the XML Schema standards for working offline and to
speed-up the building of schema instances.
