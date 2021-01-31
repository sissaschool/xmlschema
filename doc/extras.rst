**************
Extra features
**************

The subpackage *xmlschema.extras* contains a set of extra modules or subpackages
required for specific needs.
These codes are not imported during normal library usage and may require additional
dependencies to be installed. This choice facilitate the library users to pull
other code to the library without burdening the loading of the package.
In any case any contribution is encouraged providing well formatted and tested code.

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

Provides a base class and a sample for generating source code from parsed
XSD schemas. The Jinja2 engine il empowered with a set of custom filters
and tests for accessing schema components information (PSVI).
Located into module *xmlschema.extras.codegen*

Usage
=====

.. doctest::

    >>> from xmlschema.extras.codegen import PythonGenerator
    >>> codegen = PythonGenerator('tests/test_cases/examples/collection/collection.xsd')
    >>> # TODO ... codegen.render_to_files('*', output_dir='./output')


Schema based filters
--------------------

Within templates you can use a set of addional filters, available for all
generator subclasses:

name
    Get the unqualified name of the object. Invalid
    chars for identifiers are replaced by an underscore.

qname
    Get the QName of the object in prefixed form. Invalid
    chars for identifiers are replaced by an underscore.

namespace
    Get the namespace URI associated to the object.

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


Type mapping
------------

Each concrete generator class must have an additional filter for translating
types using an extendable map. For example :class:`PythonGenerator` has a
filter *python_type*.

These filters are based on a common method *map_type* that uses the instance dictionary
called *types_map*, built at initialization time from a class maps for builtin types
and for schema types and an optional initialization argument.


Defining additional filters
---------------------------

Additional or overriding filters can be passed at instance creation using the argument
*filters*. If you want to derive a custom generator class you can provide your additional
filters also using class decorator function or decorating a method.

.. doctest::

    >>> from xmlschema.extras.codegen import AbstractGenerator, filter_method
    >>>
    >>> class FooGenerator(AbstractGenerator):
    ...     formal_language = 'Foo'
    ...
    ...     @filter_method
    ...     def my_filter_method(self, obj):
    ...         """A method that filters an object using the schema."""
    ...
    ...     @staticmethod
    ...     @filter_method
    ...     def my_static_test_method(obj):
    ...         """A static method that filters an object."""
    ...
    >>>
    >>> @FooGenerator.register_filter
    ... def my_test_function(obj):
    ...     """A function that filters an object."""
    ...


.. _wsdl11-documents:

WSDL 1.1 documents
==================

The module *xmlschema.extras.wsdl* provides a specialized schema-related
XML document through

An example of
specialization is the class :class:`Wsdl11Document`, usable for validating and
parsing WSDL 1.1 documents, that can be imported from *wsdl* module of the *extra*
subpackage:

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
