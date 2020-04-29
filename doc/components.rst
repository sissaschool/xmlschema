.. _accessing-schema-components:

***************************
Accessing schema components
***************************

The schema components are provided by the `xmlschema.validators` subpackage:

.. doctest::

    >>> import xmlschema
    >>> xmlschema.validators.XsdElement
    <class 'xmlschema.validators.elements.XsdElement'>


.. note::
    For XSD components only the classes and methods included in the :ref:`xsd-components-api`
    are considered part of the stable API, the others are considered internals that can be
    changed without forewarning.
