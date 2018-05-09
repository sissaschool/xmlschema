Testing
=======

Test scripts
------------

The tests of the *xmlschema* library are implemented using the Python's *unitest*
library. The test scripts are located in under the installation base into ``tests/``
subdirectory. There are several test scripts, each one for a different topic:

**test_meta.py**
    Tests for the XSD meta-schema and XSD builtins

**test_xpath.py**
    Tests for XPath parsing and selectors

**test_resources.py**
    Tests about XML/XSD resources access

**test_resources.py**
    Tests about XSD regular expressions

**test_schemas.py**
    Tests about parsing of XSD Schemas

**test_validation.py**
    Tests about XML validation

**test_decoding.py**
    Tests regarding XML data decoding

**test_encoding.py**
    Tests regarding data encoding to XML

**test_package.py**
    Tests regarding packaging and forgotten development code

You can run all tests with the script *test_all.py*.


Test files
----------

Three scripts (*test_schemas.py*, *test_validation.py*, *test_decoding.py*) create
the most tests dinamically, loading a set of XSD or XML files.
Only a small set of test files is published in the repository for copyright
reasons. You can found the published test files into ``xmlschema/tests/examples/``
subdirectory.

You can locally extend the test with your set of files. For make this create
the base subdirectory ``xmlschema/tests/extra-schemas/`` and then copy your XSD/XML
files into it. After the files are copied create a new file called *testfiles* into
the ``extra-schemas/`` subdirectory:

.. code-block:: bash

    cd tests/extra-schemas/
    touch testfiles

Fill the file *testfiles* with the list of paths of files you want to be tested,
one per line, as in the following example:

.. code-block:: text

    # XHTML
    XHTML/xhtml11-mod.xsd
    XHTML/xhtml-datatypes-1.xsd

    # Quantum Espresso
    qe/qes.xsd
    qe/qes_neb.xsd
    qe/qes_with_choice_no_nesting.xsd
    qe/silicon.xml
    qe/silicon-1_error.xml 1
    qe/silicon-3_errors.xml 3
    qe/SrTiO_3.xml
    qe/SrTiO_3-2_errors.xml 2

The test scripts creates test for each listed file, dependant from the context.
For example the script that test the schemas uses only *.xsd* files, where instead
the script that tests the validation uses both types, validating each XML file
against its schema and each XSD against the meta-schema.

If a file has errors insert an integer number after the path. This is the number of errors
that the XML Schema validator have to found to pass the test.

From version 0.9.14 each line is parsed for those additional arguments:

**-i**
    inspect using an observed custom schema class.

**-v**
    XSD version to use for schema (default is 1.0)