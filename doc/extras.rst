**************
Extra features
**************

The subpackage *xmlschema.extras* acts as a container of a set of extra
modules or subpackages that can be useful for specific needs.

These codes are not imported during normal library usage and may require
additional dependencies to be installed. This choice should be facilitate
the implementation of other optional functionalities without having an
impact on the base configuration.

.. testsetup::

    import xmlschema
    import os
    import warnings

    if os.getcwd().endswith('/doc'):
        os.chdir('..')
    warnings.simplefilter("ignore", xmlschema.XMLSchemaIncludeWarning)


.. _code-generators:

Code generation with Jinja2 templates
=====================================

The module *xmlschema.extras.codegen* provides an abstract base class
:class:`xmlschema.extras.codegen.AbstractGenerator` for generate source
code from parsed XSD schemas. The Jinja2 engine is embedded in that class
and is empowered with a set of custom filters and tests for accessing to
defined XSD schema components.


Schema based filters
--------------------

Within templates you can use a set of additional filters, available for all
generator subclasses:

name
    Get the unqualified name of the object. Invalid
    chars for identifiers are replaced by an underscore.

qname
    Get the QName of the object in prefixed form. Invalid
    chars for identifiers are replaced by an underscore.

namespace
    Get the namespace URI of the XSD component.

type_name
    Get the unqualified name of an XSD type. For default
    'Type' or '_type' suffixes are removed. Invalid
    chars for identifiers are replaced by an underscore.

type_qname
    Get the QName of an XSD type in prefixed form. For
    default 'Type' or '_type' suffixes are removed. Invalid
    chars for identifiers are replaced by an underscore.

sort_types
    Sort a sequence or a map of XSD types, in reverse
    dependency order, detecting circularities.

Schema based tests
------------------

Within templates you can also use a set of tests, available for all generator classes:

derivation
    Test if an XSD type instance is a derivation of any of a list of
    other types. Other types are provided by qualified names.

extension
    Test if an XSD type instance is an extension of any of a list of
    other types. Other types are provided by qualified names.

restriction
    Test if an XSD type instance is a restriction of any of a list of
    other types. Other types are provided by qualified names.

multi_sequence
    Test if an XSD type is a complex type with complex content that at
    least one child can have multiple occurrences.


Type mapping
------------

Each implementation of a generator class has an additional filter for translating
types using the types map of the instance.
For example :class:`xmlschema.extras.codegen.PythonGenerator` has the filter *python_type*.

These filters are based on a common method *map_type* that uses an instance
dictionary built at initialization time from a class maps for builtin types
and an optional initialization argument for the types defined in the schema.


Defining additional Jinja2 filters and tests
--------------------------------------------

Defining a generator class you can add filters and tests using *filter_method*
and *test_method* decorators:

.. doctest::

    >>> from xmlschema.extras.codegen import AbstractGenerator, filter_method, test_method
    >>>
    >>> class DemoGenerator(AbstractGenerator):
    ...     formal_language = 'Demo'
    ...
    ...     @filter_method
    ...     def my_filter_method(self, obj):
    ...         """A method that filters an object using the schema."""
    ...
    ...     @staticmethod
    ...     @test_method
    ...     def my_test_method(obj):
    ...         """A static method that test an object."""
    ...


.. _wsdl11-documents:

WSDL 1.1 documents
==================

The module *xmlschema.extras.wsdl* provides a specialized schema-related
XML document for WSDL 1.1.

An example of
specialization is the class :class:`xmlschema.extras.wsdl.Wsdl11Document`, usable
for validating and parsing WSDL 1.1 documents, that can be imported from *wsdl*
module of the *extra* subpackage:

.. doctest::

    >>> from xmlschema.extras.wsdl import Wsdl11Document
    >>> wsdl_document = Wsdl11Document('tests/test_cases/examples/stockquote/stockquoteservice.wsdl')
    >>> wsdl_document.schema
    XMLSchema10(name='wsdl.xsd', namespace='http://schemas.xmlsoap.org/wsdl/')

A parsed WSDL 1.1 document can aggregate a set of WSDL/XSD files for building
interrelated set of definitions in multiple namespaces. The XMLResource base
class and schema validation assure a fully checked WSDL document with
protections against XML attacks.
See :class:`xmlschema.extras.wsdl.Wsdl11Document` API for details.
