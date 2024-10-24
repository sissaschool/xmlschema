.. _schema-components:

*****************
Schema components
*****************

After the building a schema object contains a set of components that represent
the definitions/declarations defined in loaded schema files. These components,
sometimes referred as *Post Schema Validation Infoset* or **PSVI**, constitute
an augmentation of the original information contained into schema files.

.. testsetup:: collection

    import xmlschema
    import os
    import warnings

    if os.getcwd().endswith('/doc'):
        os.chdir('..')
    warnings.simplefilter("ignore", xmlschema.XMLSchemaIncludeWarning)
    schema = xmlschema.XMLSchema('tests/test_cases/examples/collection/collection.xsd')


Accessing schema components
===========================

Taking the *collection.xsd* as sample schema to illustrate the access to components, we
can iterate the entire set of components, globals an locals, using the *iter_components()*
generator function:

.. doctest:: collection

    >>> import xmlschema
    >>> schema = xmlschema.XMLSchema('tests/test_cases/examples/collection/collection.xsd')
    >>> for xsd_component in schema.iter_components():
    ...     xsd_component
    ...
    XMLSchema10(name='collection.xsd', namespace='http://example.com/ns/collection')
    XsdComplexType(name='personType')
    XsdAttributeGroup(['id'])
    XsdAttribute(name='id')
    XsdGroup(model='sequence', occurs=[1, 1])
    XsdElement(name='name', occurs=[1, 1])
    ...
    ...
    XsdElement(name='object', occurs=[1, None])
    XsdElement(name='person', occurs=[1, 1])

For taking only global components use *iter_globals()* instead:

.. doctest:: collection

    >>> for xsd_component in schema.iter_globals():
    ...     xsd_component
    ...
    XsdComplexType(name='personType')
    XsdComplexType(name='objType')
    XsdElement(name='collection', occurs=[1, 1])
    XsdElement(name='person', occurs=[1, 1])


Access with XPath API
---------------------

Another method for retrieving XSD elements and attributes of a schema is
to use XPath expressions with *find* or *findall* methods:

.. doctest:: collection

    >>> from pprint import pprint
    >>> namespaces = {'': 'http://example.com/ns/collection'}
    >>> schema.find('collection/object', namespaces)
    XsdElement(name='object', occurs=[1, None])
    >>> pprint(schema.findall('collection/object/*', namespaces))
    [XsdElement(name='position', occurs=[1, 1]),
     XsdElement(name='title', occurs=[1, 1]),
     XsdElement(name='year', occurs=[1, 1]),
     XsdElement(name='author', occurs=[1, 1]),
     XsdElement(name='estimation', occurs=[0, 1]),
     XsdElement(name='characters', occurs=[0, 1])]


Access to global components
---------------------------

Accessing a specific type of global component a dictionary access may be preferred:

.. doctest:: collection

    >>> schema.elements['person']
    XsdElement(name='person', occurs=[1, 1])
    >>> schema.types['personType']
    XsdComplexType(name='personType')

The schema object has a dictionary attribute for each type of XSD declarations
(*elements*, *attributes* and *notations*) and for each type of XSD definitions
(*types*, *model groups*, *attribute groups*, *identity constraints* and *substitution
groups*).

These dictionaries are only views of common dictionaries, shared by all the
loaded schemas in a structure called *maps*:

.. doctest:: collection

    >>> schema.maps
    XsdGlobals(validator=XMLSchema10(name='collection.xsd', ...)

.. doctest:: collection

    >>> person = schema.elements['person']
    >>> person
    XsdElement(name='person', occurs=[1, 1])
    >>> schema.maps.elements[person.qualified_name]
    XsdElement(name='person', occurs=[1, 1])


Component structure
===================

Only the main component classes are available at package level:

XsdComponent
    The base class of every XSD component.

XsdType
    The base class of every XSD type, both complex and simple types.

XsdElement
    The XSD 1.0 element class, base also of XSD 1.1 element class.

XsdAttribute
    The XSD 1.0 attribute class, base also of XSD 1.1 attribute class.


The full schema components are provided only by accessing the `xmlschema.validators`
subpackage, for example:

.. doctest::

    >>> import xmlschema
    >>> xmlschema.validators.Xsd11Element
    <class 'xmlschema.validators.elements.Xsd11Element'>


Connection with the schema
--------------------------

Every component is linked to its container schema and a reference node of its
XSD schema document:

.. doctest:: collection

    >>> person = schema.elements['person']
    >>> person.schema
    XMLSchema10(name='collection.xsd', namespace='http://example.com/ns/collection')
    >>> person.elem
    <Element '{http://www.w3.org/2001/XMLSchema}element' at ...>
    >>> person.tostring()
    '<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="person" type="personType" />'


Naming options
--------------

A component that has a name (eg. elements or global types) can be referenced with
a different name format, so there are some properties for getting these formats:

.. doctest:: collection

    >>> vh_schema = xmlschema.XMLSchema('tests/test_cases/examples/vehicles/vehicles.xsd')
    >>> car = vh_schema.find('vh:vehicles/vh:cars/vh:car')
    >>> car.name
    '{http://example.com/vehicles}car'
    >>> car.local_name
    'car'
    >>> car.prefixed_name
    'vh:car'
    >>> car.qualified_name
    '{http://example.com/vehicles}car'
    >>> car.attributes['model'].name
    'model'
    >>> car.attributes['model'].qualified_name
    '{http://example.com/vehicles}model'


Decoding and encoding
---------------------

Every schema component includes methods for data conversion:

.. doctest::

    >>> schema = xmlschema.XMLSchema('tests/test_cases/examples/vehicles/vehicles.xsd')
    >>> schema.types['vehicleType'].decode
    <bound method XsdComplexType.decode of XsdComplexType(name='vehicleType')>
    >>> schema.elements['cars'].encode
    <bound method ValidationMixin.encode of XsdElement(name='vh:cars', occurs=[1, 1])>


Those methods can be used to decode the correspondents parts of the XML document:

.. doctest::

    >>> import xmlschema
    >>> from pprint import pprint
    >>> from xml.etree import ElementTree
    >>> xs = xmlschema.XMLSchema('tests/test_cases/examples/vehicles/vehicles.xsd')
    >>> xt = ElementTree.parse('tests/test_cases/examples/vehicles/vehicles.xml')
    >>> root = xt.getroot()
    >>> pprint(xs.elements['cars'].decode(root[0]))
    {'{http://example.com/vehicles}car': [{'@make': 'Porsche', '@model': '911'},
                                          {'@make': 'Porsche', '@model': '911'}]}
    >>> pprint(xs.elements['cars'].decode(xt.getroot()[1], validation='skip'))
    None
    >>> pprint(xs.elements['bikes'].decode(root[1], namespaces={'vh': 'http://example.com/vehicles'}))
    {'@xmlns:vh': 'http://example.com/vehicles',
     'vh:bike': [{'@make': 'Harley-Davidson', '@model': 'WL'},
                 {'@make': 'Yamaha', '@model': 'XS650'}]}


XSD types
=========

Every element or attribute declaration has a *type* attribute for accessing its XSD type:

.. doctest:: collection

    >>> person = schema.elements['person']
    >>> person.type
    XsdComplexType(name='personType')


Simple types
------------

Simple types are used on attributes and elements that contains a text value:

.. doctest::

    >>> schema = xmlschema.XMLSchema('tests/test_cases/examples/vehicles/vehicles.xsd')
    >>> schema.attributes['step']
    XsdAttribute(name='vh:step')
    >>> schema.attributes['step'].type
    XsdAtomicBuiltin(name='xs:positiveInteger')

A simple type doesn't have attributes but can have facets-related validators or properties:

.. doctest::

    >>> schema.attributes['step'].type.attributes
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
    AttributeError: 'XsdAtomicBuiltin' object has no attribute 'attributes'
    >>> schema.attributes['step'].type.validators
    [<function positive_int_validator at ...>]
    >>> schema.attributes['step'].type.white_space
    'collapse'

To check if a type is a simpleType use *is_simple()*:

.. doctest::

    >>> schema.attributes['step'].type.is_simple()
    True


Complex types
-------------

Complex types are used only for elements with attributes or with child elements.

For accessing the attributes there is always defined and attribute group, also
when the complex type has no attributes:

.. doctest:: collection

    >>> schema.types['objType']
    XsdComplexType(name='objType')
    >>> schema.types['objType'].attributes
    XsdAttributeGroup(['id', 'available'])
    >>> schema.types['objType'].attributes['available']
    XsdAttribute(name='available')

For accessing the content model there use the attribute *content*. In most
cases the element's type is a complexType with a complex content and in these
cases *content* is a not-empty `XsdGroup`:

.. doctest:: collection

    >>> person = schema.elements['person']
    >>> person.type.has_complex_content()
    True
    >>> person.type.content
    XsdGroup(model='sequence', occurs=[1, 1])
    >>> for item in person.type.content:
    ...     item
    ...
    XsdElement(name='name', occurs=[1, 1])
    XsdElement(name='born', occurs=[1, 1])
    XsdElement(name='dead', occurs=[0, 1])
    XsdElement(name='qualification', occurs=[0, 1])

.. note::

    The attribute *content_type* has been renamed to *content* in v1.2.1
    in order to avoid confusions between the complex type and its content.
    A property with the old name will be maintained until v2.0.


Model groups can be nested with very complex structures, so there is an generator
function *iter_elements()* to traverse a model group:

.. doctest:: collection

    >>> for e in person.type.content.iter_elements():
    ...     e
    ...
    XsdElement(name='name', occurs=[1, 1])
    XsdElement(name='born', occurs=[1, 1])
    XsdElement(name='dead', occurs=[0, 1])
    XsdElement(name='qualification', occurs=[0, 1])

Sometimes a complex type can have a simple content, in these cases *content* is a simple type.


Content types
-------------

An element can have four different content types:

- **empty**: deny child elements, deny text content
- **simple**: deny child elements, allow text content
- **element-only**: allow child elements, deny intermingled text content
- **mixed**: allow child elements and intermingled text content

For attributes only *empty* or *simple* content types are possible, because
they can have only a simpleType value.

The reference methods for checking the content type are respectively *is_empty()*,
*has_simple_content()*, *is_element_only()* and *has_mixed_content()*.


Access to content validator
---------------------------

The content type checking can be complicated if you want to know which is the
content validator without use a type checking. To making this simpler there are
two properties defined for XSD types:

simple_type
    a simple type in case of *simple* content or when an *empty* content is
    based on an empty simple type, `None` otherwise.

model_group
    a model group in case of *mixed* or *element-only* content or when an
    *empty* content is based on an empty model group, `None` otherwise.
