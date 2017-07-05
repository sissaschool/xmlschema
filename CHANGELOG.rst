*********
CHANGELOG
*********

v0.9.10
=======
* Factories code moved to XsdComponent subclasses (for simplify parsing and debugging)
* All XSD components built from ElementTree elements with a lazy approach
* Implementation of the XSD validation modes ('strict'/'lax'/'skip') both for validating
  schemas and for validating/decoding XML files
* Defined the XMLSchemaValidator class as a common base class for schema and all XSD components
* Added the check of XSD components for built schemas

v0.9.9
======
* Added converters for decode/encode data with different conventions
* Modifications on iter_decode() arguments in order to use converters

v0.9.8
======
* Added notations and substitution groups
* Created a subpackage for XSD components

v0.9.7
======
* Documentation extended and tested
* Improved tests for XPath, validation and decoding

v0.9.6
======
* Added an XPath parser
* Added iterfind(), find() and findall() APIs for searching XSD element declarations using XPath
