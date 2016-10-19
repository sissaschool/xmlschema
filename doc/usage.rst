Usage
=====

Importing the library
---------------------

You can import the library in your code with::

    import xmlschema

Importing the library creates more schema classes that parses different versions of the XML Schema standard:

**XMLSchema_v1_0**
    Class for XML Schema version 1.0 (2004)

**XMLSchema_v1_1**
    Class for XML Schema version 1.1 (2012)

**XMLSchema**
    Class that always refers to the latest version of XML Schema standard


Create a schema instance
------------------------

To create an instance of a schema calling the class with an argument that is the path to
the file containing the schema:

.. code-block:: python

    import xmlschema
    my_schema = xmlschema.XMLSchema('xmlschema/tests/examples/vehicles.xsd')

The argument could also be an opened file-like object or a string:

.. code-block:: pycon

    >>> import xmlschema
    >>> schema_file = open('xmlschema/tests/examples/vehicles.xsd')
    >>> my_schema = xmlschema.XMLSchema(schema_file)

.. code-block:: pycon

    >>> import xmlschema
    >>> my_schema = xmlschema.XMLSchema("""
    ... <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
    ... <xs:element name="block" type="xs:string"/>
    ... </xs:schema>
    ... """)


Limitations of using a string argument
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Avoid passing the schema as a string when the schema require to include other local subschemas:

.. code-block:: pycon

    >>> import xmlschema
    >>> schema_xsd = open('xmlschema/tests/examples/vehicles.xsd').read()
    >>> my_schema = xmlschema.XMLSchema(schema_xsd)
    Traceback (most recent call last):
      File "/home/brunato/Development/projects/xmlschema/xmlschema/factories.py", line 60, in _include_schemas
        schema, schema_uri = load_resource(locations, _base_uri)
      File "/home/brunato/Development/projects/xmlschema/xmlschema/resources.py", line 83, in load_resource
        "no URI or file available to retrieve the resource: '%s'" % locations
    xmlschema.core.XMLSchemaOSError: no URI or file available to retrieve the resource: 'cars.xsd'

    During handling of the above exception, another exception occurred:

    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File "/home/brunato/Development/projects/xmlschema/xmlschema/schema.py", line 150, in __init__
        self.update_schema(self._root)
      File "/home/brunato/Development/projects/xmlschema/xmlschema/schema.py", line 198, in update_schema
        self.include_schemas(elements)
      File "/home/brunato/Development/projects/xmlschema/xmlschema/schema.py", line 193, in include_schemas
        include_schemas(elements, self._included_schemas, self.uri, self.namespaces)
      File "/home/brunato/Development/projects/xmlschema/xmlschema/factories.py", line 80, in xsd_include_schemas
        _include_schemas(elements, base_uri)
      File "/home/brunato/Development/projects/xmlschema/xmlschema/factories.py", line 62, in _include_schemas
        raise XMLSchemaOSError("Not accessible schema locations '{}'".format(locations))
    xmlschema.core.XMLSchemaOSError: Not accessible schema locations 'cars.xsd'


Validation
----------

Using a XMLSchema instance you can validate XML files based on that schema. The first mode is using the
instance's method **is_valid**:

.. code-block:: pycon

    >>> import xmlschema
    >>> my_schema = xmlschema.XMLSchema('xmlschema/tests/examples/vehicles.xsd')
    >>> my_schema.is_valid('xmlschema/tests/examples/vehicles.xml')
    True
    >>> my_schema.is_valid('xmlschema/tests/examples/vehicles-1_error.xml')
    False
    >>> my_schema.is_valid("""<?xml version="1.0" encoding="UTF-8"?><fancy_tag/>""")
    False

*is_valid* returns True if the XML argument is conformed to the schema loaded in the instance,
returns False if it's doesn't conforms.

Another call for validating an XML document is the method validate, that raises an error when the
XML doesn't conforms to the schema:

.. code-block:: pycon

    >>> import xmlschema
    >>> my_schema = xmlschema.XMLSchema('xmlschema/tests/examples/vehicles.xsd')
    >>> my_schema.validate('xmlschema/tests/examples/vehicles.xml')
    >>> my_schema.validate('xmlschema/tests/examples/vehicles-1_error.xml')
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File "/home/brunato/Development/projects/xmlschema/xmlschema/schema.py", line 259, in validate
        raise error
    xmlschema.validators.XMLSchemaValidationError: failed validating <Element '{http://example.com/vehicles}cars' at 0x7fd76fa6f2c8> with <XsdGroup 'None' at 0x7fd76fda49e8>.

    Reason: character data between child elements not allowed!

    Schema:

      <xs:sequence xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:element maxOccurs="unbounded" minOccurs="0" name="car" type="vh:vehicleType" />
          </xs:sequence>

    Instance:

      <ns0:cars xmlns:ns0="http://example.com/vehicles">
        NOT ALLOWED CHARACTER DATA
        <ns0:car make="Porsche" model="911" />
        <ns0:car make="Porsche" model="911" />
      </ns0:cars>


A similar two-argument function is available also at module level:

.. code-block:: pycon

    >>> import xmlschema
    >>> os.chdir('xmlschema/tests/examples')
    >>> xmlschema.validate('vehicles.xml', 'vehicles.xsd')

The latter is useful when you have to validate starting from the XML file.

Data conversion
---------------

The schema object includes XSD declarations (types, elements, attributes, groups, attribute_groups).
The global XSD declarations are available as attributes of the instance:

.. code-block:: pycon

    >>> import xmlschema
    >>> my_schema = xmlschema.XMLSchema('xmlschema/tests/examples/vehicles.xsd')
    >>> my_schema.types
    {'{http://example.com/vehicles}vehicleType': <XsdComplexType '{http://example.com/vehicles}vehicleType' at 0x7fd76fda4cf8>}
    >>> my_schema.elements
    {'{http://example.com/vehicles}bikes': <XsdElement '{http://example.com/vehicles}bikes' at 0x7fd76fda4a58>, '{http://example.com/vehicles}cars': <XsdElement '{http://example.com/vehicles}cars' at 0x7fd76fda4dd8>, '{http://example.com/vehicles}vehicles': <XsdElement '{http://example.com/vehicles}vehicles' at 0x7fd76fda4f98>}
    >>> my_schema.attributes
    {'{http://example.com/vehicles}step': <XsdAttribute '{http://example.com/vehicles}step' at 0x7fd76fda4668>}

The schema declarations objects include methods for data conversion:

.. code-block:: python

    my_schema.types['<XSD type name>'].decode('<XML text>')       # Decode XML text to data
    my_schema.types['<XSD type name>'].encode('<data instance>')  # Decode a data to and XML text

You can also converts the entire XML document to a nested dictionary with data conversion:

.. code-block:: python

    from xml.etree import ElementTree
    my_xml = ElementTree.parse(<path to an XML file based on your XSD schema>)
    my_schema = xmlschema.XMLSchema(<path to your XSD schema file>)
    xmlschema.etree_to_dict(my_xml, my_schema)

