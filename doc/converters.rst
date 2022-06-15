.. _converters:

***********************
Converters for XML data
***********************

XML data decoding and encoding is handled using an intermediate converter class
instance that takes charge of composing inner data and mapping of namespaces and prefixes.

Because XML is a structured format that includes data and metadata information,
as attributes and namespace declarations, is necessary to define conventions for
naming the different data objects in a distinguishable way. For example a wide-used
convention is to prefixing attribute names with an '@' character. With this convention
the attribute `name='John'` is decoded to `'@name': 'John'`, or `'level='10'` is
decoded to `'@level': 10`.

A related topic is the mapping of namespaces. The expanded namespace representation
is used within XML objects of the ElementTree library.
For example `{http://www.w3.org/2001/XMLSchema}string` is the fully qualified name of
the XSD string type, usually referred as *xs:string* or *xsd:string* with a namespace
declaration. With string serialization of XML data the names are remapped to prefixed
format. This mapping is generally useful also if you serialize XML data to another format
like JSON, because prefixed name is more manageable and readable than expanded format.


Available converters
====================

The library includes some converters. The default converter :class:`xmlschema.XMLSchemaConverter`
is the base class of other converter types. Each derived converter type implements a
well know convention, related to the conversion from XML to JSON data format:

  * :class:`xmlschema.ParkerConverter`: `Parker convention <https://developer.mozilla.org/en-US/docs/Archive/JXON#The_Parker_Convention>`_
  * :class:`xmlschema.BadgerFishConverter`: `BadgerFish convention <http://www.sklar.com/badgerfish/>`_
  * :class:`xmlschema.AbderaConverter`: `Apache Abdera project convention <https://cwiki.apache.org/confluence/display/ABDERA/JSON+Serialization>`_
  * :class:`xmlschema.JsonMLConverter`: `JsonML (JSON Mark-up Language) convention <http://www.jsonml.org/>`_

A summary of these and other conventions can be found on the wiki page
`JSON and XML Conversion <http://wiki.open311.org/JSON_and_XML_Conversion/>`_.

The base class, that not implements any particular convention, has several options that
can be used to variate the converting process. Some of these options are not used by other
predefined converter types (eg. *force_list* and *force_dict*) or are used with a fixed value
(eg. *text_key* or *attr_prefix*). See :ref:`converters-api` for details about
base class options and attributes.

Moreover there are also other two converters useful for specific cases:

  * :class:`xmlschema.UnorderedConverter`: like default converter but with unordered decoding and encoding.
  * :class:`xmlschema.ColumnarConverter`: a converter that remaps attributes as child elements in a
    columnar shape (available since release v1.2.0).
  * :class:`xmlschema.DataElementConverter`: a converter that converts XML to a tree of
    :class:`xmlschema.DataElement` instances, Element-like objects with decoded values and
    schema bindings (available since release v1.5.0).


Create a custom converter
=========================

To create a new customized converter you have to subclass the :class:`xmlschema.XMLSchemaConverter`
and redefine the two methods *element_decode* and *element_encode*. These methods are based
on the namedtuple `ElementData`, an Element-like data structure that stores the decoded
Element parts. This namedtuple is used by decoding and encoding methods as an intermediate
data structure.

The namedtuple `ElementData` has four attributes:

  * **tag**: the element's tag string;
  * **text**: the element's text, that can be a string or `None` for empty elements;
  * **content**: the element's children, can be a list or `None`;
  * **attributes**: the element's attributes, can be a dictionary or `None`.

The method *element_decode* receives as first argument an `ElementData` instance with
decoded data. The other arguments are the XSD element to use for decoding and the level
of the XML decoding process, used to add indent spaces for a readable string serialization.
This method uses the input data element to compose a decoded data, typically a dictionary
or a list or a value for simple type elements.

On the opposite the method *element_encode* receives the decoded object and decompose it
in order to get and returns an `ElementData` instance. This instance has to contain the
parts of the element that will be then encoded an used to build an XML Element instance.

These two methods have also the responsibility to map and unmap object names, but don't
have to decode or encode data, a task that is delegated to the methods of the XSD components.

Depending on the format defined by your new converter class you may provide a different
value for properties *lossless* and *losslessly*. The *lossless* has to be `True` if your
new converter class preserves all XML data information (eg. as the *BadgerFish* convention).
Your new converter can be also *losslessly* if it's lossless and the element model structure
and order is maintained (like the JsonML convention).

Furthermore your new converter class can has a more specific `__init__` method in order
to avoid the usage of unused options or to set the value of some other options. Finally refer
also to the code of predefined  derived converters to see how you can build your own one.
