*********
CHANGELOG
*********

v0.9.30
=======
* First experimental version of data encoding with the default converter
* Fixes for issues #65, #66 and #67

v0.9.29
=======
* Extended the tests on lxml XML data
* Fixes for issues #61, #63 and #64

v0.9.28
=======
* Encoding of XSD builtin types (strings and numerical)
* Fix for issue #62
* Drop support for Python 3.3

v0.9.27
=======
* Add support for preventing XML attacks with the use of the
  *defusedxml* package (added *defuse* argument to schemas)
* Fix for group circularity (issue #58)
* Fix for billion laughs attacks using XSD groups expansion

v0.9.26
=======
* Added checks for model restrictions

v0.9.25
=======
* Removed XsdAnnotated class
* Added XsdType class as common class for XSD types
* Fixes for issues #55 and #56

v0.9.24
=======
* Added XPath 1.0/2.0 full parsing with the derived *elementpath* package
* Fixes for issues #52 and #54
* Test package improved (tox.ini, other checks with test_package.py)

v0.9.23
=======
* Fixes for issues #45, #46, #51
* Added kwargs to *iter_decode()*, *dict_class* and *list_class* arguments have
  been removed
* Added kwargs to converters initialization in order to push variable keyword
  arguments from *iter_decode()*

v0.9.21
=======
* Fixes 'final' derivation attribute for complexType
* Decoupling of the XPath module from XsdComponent API
* Fix for issue #41

v0.9.20
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
