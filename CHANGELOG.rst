*********
CHANGELOG
*********

v0.9.19
=======
* Substitution groups support
* Added *fetch_schema_locations* function to API
* Added *locations* argument to *fetch_schema*, *validate* and *to_dict* API functions
* A more useful __repr__ for XSD component classes
* Fixes for issues #35, #38, #39

v0.9.18
=======
* Fixed issue #34 (min_occurs == 0 check in XsdGroup.is_emptiable)
* Updated copyright information
* Updated schema class creation (now use a metaclass)
* Added index and expected attributes to XMLSchemaChildrenValidationError
* Added *locations* optional argument to XMLSchema class

v0.9.17
=======
* Key/Unique/Keyref constraints partially rewritten
* Fixed ad issue with UCS-2/4 and maxunicode

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
