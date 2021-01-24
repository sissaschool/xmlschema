*********
CHANGELOG
*********

`v1.4.2`_ (2021-01-24)
======================
* Add decoding of binary datatypes (xs:hexBinary and xs:base64Binary)
* Fix encoding from string values for some builtin datatypes
  (decimal, binary, duration and datetime).

`v1.4.1`_ (2020-12-24)
======================
* Include the pull request #220 (fix xml.etree import)
* Additional tests for schema components

`v1.4.0`_ (2020-12-23)
======================
* Fix for issues #213, #214, #215 and #218
* Code cleaning and optimizations on schema components
* Reducing and grouping helper functions

`v1.3.1`_ (2020-11-10)
======================
* Apply patches for packaging (issue #210)

`v1.3.0`_ (2020-11-09)
======================
* Drop support for Python 3.5
* Add XmlDocument and Wsdl11Document classes
* Refactoring of XMLResource to support ElementTree-like XPath API
  on both full and lazy modes

`v1.2.5`_ (2020-09-26)
======================
* Add schema export API to schema and global maps (issue #187)
* Fix decoding with lax/skip validation modes (issue #204)
* Add *keep_unknown* optional argument for *iter_decode()* methods

`v1.2.4`_ (2020-09-13)
======================
* Use the regex engine of *elementpath* library
* Fix and extend tests on xs:assert

`v1.2.3`_ (2020-08-14)
======================
* Full coverage of W3C tests (excluding ones for unavailable or unimplemented features)
* Update and restrict elementpath dependency to v2.0.x
* Fix check and iteration of empty model group
* Fix substitution group iteration for local elements

`v1.2.2`_ (2020-06-15)
======================
* Fix XPath context for schema nodes
* Fix XPath parser and context for identities

`v1.2.1`_ (2020-06-12)
======================
* Fix content type classification (issue #195)
* Make sandbox mode more explicit (PR #191)
* Allow alphanumeric prefixes for the base converter
* Fix XPath issues with default namespace
* Fix W3C tests on XSD identities

`v1.2.0`_ (2020-05-28)
======================
* Add ColumnarConverter class
* Add command-line interface utility for document API
* Fix a stable public API for XSD types, elements and attributes
* Add security modes for accessing URLs

`v1.1.3`_ (2020-04-28)
======================
* Clean component parsing
* Fix namespace loading for chameleon schemas
* Fix UPA checks with nested choice/all models
* Fixed issues #182 and #183

`v1.1.2`_ (2020-03-22)
======================
* Extension of validation tests with *XMLSchema11* validator
* Fixed several bugs
* Extended testing with Travis CI

`v1.1.1`_ (2020-02-19)
======================
* Change of *skip* validation mode with errors filtering in decode() or encode()
* Extension of location hints by argument to imported/included schemas
* Fixed lazy validation with identity constraints
* Fixed many W3C instance tests (remain ~100 over 15344 tests)

`v1.1.0`_ (2020-01-23)
=======================
* Removed Python 2 compatibility code
* Removed tests code from binary package
* Improved identity constraints validation
* Added JSON lazy decoding as experimental feature

`v1.0.18`_ (2019-12-24)
=======================
* Fix for *ModelVisitor.iter_unordered_content()*
* Fixed default converter, AbderaConverter and JsonMLConverter for xs:anyType decode
* Fixed validation tests with all converters
* Added UnorderedConverter to validation tests

`v1.0.17`_ (2019-12-22)
=======================
* Enhancement of validation-only speed (~15%)
* Added *is_valid()* and *iter_errors()* to module API

`v1.0.16`_ (2019-11-18)
=======================
* Improved XMLResource class for working with compressed files
* Fix for validation with XSD wildcards and 'lax' process content
* Fix ambiguous items validation for xs:choice and xs:sequence models

`v1.0.15`_ (2019-10-13)
=======================
* Improved XPath 2.0 bindings
* Added logging for schema initialization and building (handled with argument *loglevel*)
* Update encoding of collapsed contents with a new model based reordering method
* Removed XLink namespace from meta-schema (loaded from a fallback location like XHTML)
* Fixed half of failed W3C instance tests (remain 255 over 15344 tests)

`v1.0.14`_ (2019-08-27)
=======================
* Added XSD 1.1 validator with class *XMLSchema11*
* Memory usage optimization with lazy build of the XSD 1.0 and 1.1 meta-schemas
* Added facilities for the encoding of unordered and collapsed content

`v1.0.13`_ (2019-06-19)
=======================
* Fix path normalization and tests for Windows platform
* Added XML resource validation in lazy mode (experimental feature)
* Added arguments *filler* and *fill_missing* to XSD decode/encode methods
* Added arguments *preserve_root*, *strip_namespaces*, *force_dict* and *force_list* to XMLSchemaConverter
* Added code coverage and pep8 testing
* Drop support for Python 3.4

`v1.0.11`_ (2019-05-05)
=======================
* Added a script for running the W3C XSD test suite.
* Check restrictions and model groups UPA violations
* Model groups splitted between two modules for more focusing on models basics
* Added two new exceptions for model group errors
* More control on imported namespaces
* Added *use_meta* argument to schema classes
* Added *includes* list and *imports* dict to schema classes
* Many fixes for passing the W3C's tests for XSD 1.0 schemas
* Added a test for issue #105 and a fix for issue #103

`v1.0.10`_ (2019-02-25)
=======================
* Fixed Element type mismatch issue when apply *SafeXMLParser* to schema resources
* More XSD 1.1 features implemented (open content and versioning namespace are missing)

`v1.0.9`_ (2019-02-03)
======================
* Programmatic import of ElementTree for avoid module mismatches
* Cleaning and refactoring of test scripts

`v1.0.8`_ (2019-01-30)
======================
* Dependency *defusedxml* package replaced by a custom XMLParser for ElementTree
* Optional decoding of XSD date/time/duration builtin types
* Fixes for issues #93, #96, #97 and #99

`v1.0.7`_ (2018-11-15)
======================
* Fixes for issues #87 and #88
* Merged with PR #89 (simpleType restriction annotation parsing)
* XSD 1.1 development: added assertion facet (still to be completed)

`v1.0.6`_ (2018-10-21)
======================
* Fixes for issues #85 and #86
* XSD 1.1 development: added explicitTimezone facet and XSD 1.1 builtin types

`v1.0.5`_ (2018-09-27)
======================
* Fix for issue #82 and for similar unprotected XSD component lookups
* Added checks for namespace mapping of encoded trees and error messages

`v1.0.4`_ (2018-09-22)
======================
* Unification of XSD group decode and encode methods
* Children validation error class improved
* Fixes for issues #77, #79 and #80
* Added test scripts for helpers and ElementTree

`v1.0.3`_ (2018-08-26)
======================
* Improved model validation for XSD groups encoding
* Added parent reference to XSD components
* Extended validator errors classes
* Optimized error generation using helper methods
* Improved particle parsing

`v1.0.2`_ (2018-07-26)
======================
* Improved ElementTree and XPath API

`v1.0.1`_ (2018-07-14)
======================
* Validated data encoding to XML
* Improved converters with decoding/encoding of namespace information
* Added helper functions for encoding and decoding to JSON
* Added XMLResource class for managing access to XML data sources
* Added warnings for failed schema includes and namespace imports

`v0.9.31`_ (2018-06-24)
=======================
* Schema serialization with pickle for Python 3 (enhancement related to issue #68)
* Data encoding with the default converter
* Improved decoding for xs:union

`v0.9.30`_ (2018-06-06)
=======================
* First experimental version of data encoding with the default converter
* Fixes for issues #65, #66 and #67

`v0.9.29`_ (2018-06-03)
=======================
* Extended the tests on lxml XML data
* Fixes for issues #61, #63 and #64

`v0.9.28`_ (2018-05-18)
=======================
* Encoding of XSD builtin types (strings and numerical)
* Fix for issue #62
* Drop support for Python 3.3

`v0.9.27`_ (2018-05-08)
=======================
* Add support for preventing XML attacks with the use of the
  *defusedxml* package (added *defuse* argument to schemas)
* Fix for group circularity (issue #58)
* Fix for billion laughs attacks using XSD groups expansion

`v0.9.26`_ (2018-04-12)
=======================
* Added checks for model restrictions

`v0.9.25`_ (2018-04-05)
=======================
* Removed XsdAnnotated class
* Added XsdType class as common class for XSD types
* Fixes for issues #55 and #56

`v0.9.24`_ (2018-04-03)
=======================
* Added XPath 1.0/2.0 full parsing with the derived *elementpath* package
* Fixes for issues #52 and #54
* Test package improved (tox.ini, other checks with test_package.py)

`v0.9.23`_ (2018-03-10)
=======================
* Fixes for issues #45, #46, #51
* Added kwargs to *iter_decode()*, *dict_class* and *list_class* arguments have
  been removed
* Added kwargs to converters initialization in order to push variable keyword
  arguments from *iter_decode()*

`v0.9.21`_ (2018-02-15)
=======================
* Fixes 'final' derivation attribute for complexType
* Decoupling of the XPath module from XsdComponent API
* Fix for issue #41

`v0.9.20`_ (2018-01-22)
=======================
* Substitution groups support
* Added *fetch_schema_locations* function to API
* Added *locations* argument to *fetch_schema*, *validate* and *to_dict* API functions
* A more useful __repr__ for XSD component classes
* Fixes for issues #35, #38, #39

`v0.9.18`_ (2018-01-12)
=======================
* Fixed issue #34 (min_occurs == 0 check in XsdGroup.is_emptiable)
* Updated copyright information
* Updated schema class creation (now use a metaclass)
* Added index and expected attributes to XMLSchemaChildrenValidationError
* Added *locations* optional argument to XMLSchema class

`v0.9.17`_ (2017-12-28)
=======================
* Key/Unique/Keyref constraints partially rewritten
* Fixed ad issue with UCS-2/4 and maxunicode

`v0.9.16`_ (2017-12-23)
=======================
* UnicodeSubset class rewritten (more speed, less memory)
* Updated unicode_categories.json to Python 3.6 unicodedata 
* Added XMLSchemaChildrenValidationError exception

`v0.9.15`_ (2017-12-15)
=======================
* Some bug fixes
* Code cleaning
* XSD components modules has been merged with schema's modules into 'validators' subpackage

`v0.9.14`_ (2017-11-23)
=======================
* Improved test scripts with a *SchemaObserver* class and test line arguments
* Full support for date and time XSD builtin types

`v0.9.12`_ (2017-09-14)
=======================
* Added identity constraints
* Some bug fix

`v0.9.10`_ (2017-07-08)
=======================
* Factories code moved to XsdComponent subclasses for simplify parsing and debugging
* All XSD components built from ElementTree elements with a lazy approach
* Implementation of the XSD validation modes ('strict'/'lax'/'skip') both for validating
  schemas and for validating/decoding XML files
* Defined an XsdBaseComponent class as the common base class for all XSD components,
  schemas and global maps
* Defined a ValidatorMixin for sharing a common API between validators/decoders classes
* Added built and validity checks for all XSD components

`v0.9.9`_ (2017-06-12)
======================
* Added converters for decode/encode data with different conventions
* Modifications on iter_decode() arguments in order to use converters

`v0.9.8`_ (2017-05-27)
======================
* Added notations and substitution groups
* Created a subpackage for XSD components

`v0.9.7`_ (2017-05-21)
======================
* Documentation extended and tested
* Improved tests for XPath, validation and decoding

v0.9.6 (2017-05-05)
===================
* Added an XPath parser
* Added iterfind(), find() and findall() APIs for searching XSD element declarations using XPath


.. _v0.9.7: https://github.com/brunato/xmlschema/compare/v0.9.6...v0.9.7
.. _v0.9.8: https://github.com/brunato/xmlschema/compare/v0.9.7...v0.9.8
.. _v0.9.9: https://github.com/brunato/xmlschema/compare/v0.9.8...v0.9.9
.. _v0.9.10: https://github.com/brunato/xmlschema/compare/v0.9.9...v0.9.10
.. _v0.9.12: https://github.com/brunato/xmlschema/compare/v0.9.10...v0.9.12
.. _v0.9.14: https://github.com/brunato/xmlschema/compare/v0.9.12...v0.9.14
.. _v0.9.15: https://github.com/brunato/xmlschema/compare/v0.9.14...v0.9.15
.. _v0.9.16: https://github.com/brunato/xmlschema/compare/v0.9.15...v0.9.16
.. _v0.9.17: https://github.com/brunato/xmlschema/compare/v0.9.16...v0.9.17
.. _v0.9.18: https://github.com/brunato/xmlschema/compare/v0.9.17...v0.9.18
.. _v0.9.20: https://github.com/brunato/xmlschema/compare/v0.9.18...v0.9.20
.. _v0.9.21: https://github.com/brunato/xmlschema/compare/v0.9.20...v0.9.21
.. _v0.9.23: https://github.com/brunato/xmlschema/compare/v0.9.21...v0.9.23
.. _v0.9.24: https://github.com/brunato/xmlschema/compare/v0.9.23...v0.9.24
.. _v0.9.25: https://github.com/brunato/xmlschema/compare/v0.9.24...v0.9.25
.. _v0.9.26: https://github.com/brunato/xmlschema/compare/v0.9.25...v0.9.26
.. _v0.9.27: https://github.com/brunato/xmlschema/compare/v0.9.26...v0.9.27
.. _v0.9.28: https://github.com/brunato/xmlschema/compare/v0.9.27...v0.9.28
.. _v0.9.29: https://github.com/brunato/xmlschema/compare/v0.9.28...v0.9.29
.. _v0.9.30: https://github.com/brunato/xmlschema/compare/v0.9.29...v0.9.30
.. _v0.9.31: https://github.com/brunato/xmlschema/compare/v0.9.30...v0.9.31
.. _v1.0.1: https://github.com/brunato/xmlschema/compare/v0.9.31...v1.0.1
.. _v1.0.2: https://github.com/brunato/xmlschema/compare/v1.0.1...v1.0.2
.. _v1.0.3: https://github.com/brunato/xmlschema/compare/v1.0.2...v1.0.3
.. _v1.0.4: https://github.com/brunato/xmlschema/compare/v1.0.3...v1.0.4
.. _v1.0.5: https://github.com/brunato/xmlschema/compare/v1.0.4...v1.0.5
.. _v1.0.6: https://github.com/brunato/xmlschema/compare/v1.0.5...v1.0.6
.. _v1.0.7: https://github.com/brunato/xmlschema/compare/v1.0.6...v1.0.7
.. _v1.0.8: https://github.com/brunato/xmlschema/compare/v1.0.7...v1.0.8
.. _v1.0.9: https://github.com/brunato/xmlschema/compare/v1.0.8...v1.0.9
.. _v1.0.10: https://github.com/brunato/xmlschema/compare/v1.0.9...v1.0.10
.. _v1.0.11: https://github.com/brunato/xmlschema/compare/v1.0.10...v1.0.11
.. _v1.0.13: https://github.com/brunato/xmlschema/compare/v1.0.11...v1.0.13
.. _v1.0.14: https://github.com/brunato/xmlschema/compare/v1.0.13...v1.0.14
.. _v1.0.15: https://github.com/brunato/xmlschema/compare/v1.0.14...v1.0.15
.. _v1.0.16: https://github.com/brunato/xmlschema/compare/v1.0.15...v1.0.16
.. _v1.0.17: https://github.com/brunato/xmlschema/compare/v1.0.16...v1.0.17
.. _v1.0.18: https://github.com/brunato/xmlschema/compare/v1.0.17...v1.0.18
.. _v1.1.0: https://github.com/brunato/xmlschema/compare/v1.0.18...v1.1.0
.. _v1.1.1: https://github.com/brunato/xmlschema/compare/v1.1.0...v1.1.1
.. _v1.1.2: https://github.com/brunato/xmlschema/compare/v1.1.1...v1.1.2
.. _v1.1.3: https://github.com/brunato/xmlschema/compare/v1.1.2...v1.1.3
.. _v1.2.0: https://github.com/brunato/xmlschema/compare/v1.1.3...v1.2.0
.. _v1.2.1: https://github.com/brunato/xmlschema/compare/v1.2.0...v1.2.1
.. _v1.2.2: https://github.com/brunato/xmlschema/compare/v1.2.1...v1.2.2
.. _v1.2.3: https://github.com/brunato/xmlschema/compare/v1.2.2...v1.2.3
.. _v1.2.4: https://github.com/brunato/xmlschema/compare/v1.2.3...v1.2.4
.. _v1.2.5: https://github.com/brunato/xmlschema/compare/v1.2.4...v1.2.5
.. _v1.3.0: https://github.com/brunato/xmlschema/compare/v1.2.5...v1.3.0
.. _v1.3.1: https://github.com/brunato/xmlschema/compare/v1.3.0...v1.3.1
.. _v1.4.0: https://github.com/brunato/xmlschema/compare/v1.3.1...v1.4.0
.. _v1.4.1: https://github.com/brunato/xmlschema/compare/v1.4.0...v1.4.1
.. _v1.4.2: https://github.com/brunato/xmlschema/compare/v1.4.1...v1.4.2
