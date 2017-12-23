*********
CHANGELOG
*********

v0.9.16
=======
* UnicodeSubset class rewritten (more speed, less memory)
* Updated unicode_categories.json to Python 3.6 unicodedata 
* Added XMLSchemaChildrenValidationError exception

v0.9.15
=======
* Some bug fixes
* Code cleaning
* XSD components modules has been merged with schema's modules into 'validators' subpackage

v0.9.14
=======
* Improved test scripts with a *SchemaObserver* class and test line arguments
* Full support for date and time XSD builtin types

v0.9.12
=======
* Added identity constraints
* Some bug fix

v0.9.10
=======
* Factories code moved to XsdComponent subclasses for simplify parsing and debugging
* All XSD components built from ElementTree elements with a lazy approach
* Implementation of the XSD validation modes ('strict'/'lax'/'skip') both for validating
  schemas and for validating/decoding XML files
* Defined an XsdBaseComponent class as the common base class for all XSD components,
  schemas and global maps
* Defined a ValidatorMixin for sharing a common API between validators/decoders classes
* Added built and validity checks for all XSD components

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
