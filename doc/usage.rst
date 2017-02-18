Usage
=====

Importing the library
---------------------

You can import the library in your code with::

    import xmlschema

Create a schema instance
------------------------

To create an instance of a schema calling the class with an argument that is the path to
the file containing the schema:

.. code-block:: python

    import xmlschema
    my_schema = xmlschema.XMLSchema('xmlschema/tests/examples/vehicles/vehicles.xsd')

The argument could also be an opened file-like object or a string:

.. code-block:: pycon

    >>> import xmlschema
    >>> schema_file = open('xmlschema/tests/examples/vehicles/vehicles.xsd')
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
    >>> schema_xsd = open('xmlschema/tests/examples/vehicles/vehicles.xsd').read()
    >>> my_schema = xmlschema.XMLSchema(schema_xsd)
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File "/home/brunato/Development/projects/xmlschema/xmlschema/schema.py", line 128, in __init__
        self.include_schemas(self._root)
      File "/home/brunato/Development/projects/xmlschema/xmlschema/xsdbase.py", line 388, in xsd_include_schemas
        _include_schemas(elements, schema.uri)
      File "/home/brunato/Development/projects/xmlschema/xmlschema/xsdbase.py", line 367, in _include_schemas
        "cannot get the subschema from %r: %r" % (locations, errors)
    xmlschema.exceptions.XMLSchemaOSError: cannot get the subschema from 'cars.xsd': [FileNotFoundError(2, 'No such file or directory')]


Validation
----------

Using a XMLSchema instance you can validate XML files based on that schema. The first mode is using the
instance's method **is_valid**:

.. code-block:: pycon

    >>> import xmlschema
    >>> my_schema = xmlschema.XMLSchema('xmlschema/tests/examples/vehicles/vehicles.xsd')
    >>> my_schema.is_valid('xmlschema/tests/examples/vehicles/vehicles.xml')
    True
    >>> my_schema.is_valid('xmlschema/tests/examples/vehicles/vehicles-1_error.xml')
    False
    >>> my_schema.is_valid("""<?xml version="1.0" encoding="UTF-8"?><fancy_tag/>""")
    False

*is_valid* returns True if the XML argument is validated by the schema loaded in the instance,
returns False if it isn't validated.

Another call for validating an XML document is the method *validate*, that raise an error when the
XML doesn't conforms to the schema:

.. code-block:: pycon

    >>> import xmlschema
    >>> my_schema = xmlschema.XMLSchema('xmlschema/tests/examples/vehicles/vehicles.xsd')
    >>> my_schema.validate('xmlschema/tests/examples/vehicles/vehicles.xml')
    >>> my_schema.validate('xmlschema/tests/examples/vehicles/vehicles-1_error.xml')
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File "/home/brunato/Development/projects/xmlschema/xmlschema/schema.py", line 220, in validate
        raise error
    xmlschema.exceptions.XMLSchemaValidationError: failed validating <Element '{http://example.com/vehicles}cars' at 0x7f6cab897638> with <XsdGroup 'None' at 0x7f6cab89b198>.

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

    >>> import xmlschema, os
    >>> os.chdir('xmlschema/tests/examples/vehicles/')
    >>> xmlschema.validate('vehicles.xml', 'vehicles.xsd')

The latter is useful when you have to validate starting from the XML file.

Data decoding and encoding
--------------------------

The schema object includes XSD declarations (types, elements, attributes, groups, attribute_groups).
The global XSD declarations are available as attributes of the instance:

.. code-block:: pycon

    >>> import xmlschema
    >>> my_schema = xmlschema.XMLSchema('xmlschema/tests/examples/vehicles/vehicles.xsd')
    >>> my_schema.types
    {'{http://example.com/vehicles}vehicleType': <XsdComplexType '{http://example.com/vehicles}vehicleType' at 0x7fd76fda4cf8>}
    >>> my_schema.elements
    {'{http://example.com/vehicles}bikes': <XsdElement '{http://example.com/vehicles}bikes' at 0x7fd76fda4a58>,
    '{http://example.com/vehicles}cars': <XsdElement '{http://example.com/vehicles}cars' at 0x7fd76fda4dd8>,
    '{http://example.com/vehicles}vehicles': <XsdElement '{http://example.com/vehicles}vehicles' at 0x7fd76fda4f98>}
    >>> my_schema.attributes
    {'{http://example.com/vehicles}step': <XsdAttribute '{http://example.com/vehicles}step' at 0x7fd76fda4668>}

The schema declarations objects include methods for data conversion:

.. code-block:: python

    my_schema.types['<XSD type name>'].decode('<XML text or element>')  # Decode XML to data
    my_schema.types['<XSD type name>'].encode('<data instance>')  # Decode a data to and XML text

You can also decode a XML document to a nested dictionary:

.. code-block:: python

    import xmlschema
    my_schema = xmlschema.XMLSchema(<path to your XSD schema file>)
    my_schema.to_dict(<path to an XML file based on your XSD schema>)
