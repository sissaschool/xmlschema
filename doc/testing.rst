Development and testing
=======================

Test scripts
------------

The tests of the *xmlschema* library are implementend using the Python's *unitest* library.
The test scripts are located in ``xmlschema/tests/`` subdirectory:

**test_schemas.py**
    Tests about parsing of XSD Schemas

**test_validation.py**
    Tests about XML validation

**test_decoding.py**
    Tests regarding XML data decoding

Running those scripts make tests for a groups of test files:

.. code-block:: bash

    $ python test_schemas.py
    .............................................................................................................................
    ----------------------------------------------------------------------
    Ran 125 tests in 0.468s

    OK

    $ python test_validation.py
    .........
    ----------------------------------------------------------------------
    Ran 9 tests in 0.352s

    OK
    $ python test_decoding.py
    .........
    ----------------------------------------------------------------------
    Ran 9 tests in 0.294s

    OK

Those scripts use a set of test files. Only a small set of test files are published in the GitHub repository
for copyright reasons. You can found the published test files in ``xmlschema/tests/examples/`` subdirectory.

You can run all tests (schema building and XSD validation, XML validation, XML decoding) with the script
*test_all.py*. A bash script *test_all.sh* run all tests with all available Python interpreters (2.7 and 3.3+).


Running the tests on other files
--------------------------------

The test base is easily extensible copying the additional schema files in the
``xmlschema/tests/extra-schemas/`` subdirectory. After copying the XML/XSD files creates a
new file called *testfiles*:

.. code-block:: bash

    cd tests/extra-schemas/
    touch testfiles

In this file add the list of paths of files you want to be tested, one per line, as in this example:

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

The test scripts will discover automatically and run the new tests added.
The optional integer number after the path is the number of errors that the XML Schema validator
have to find to pass the test, otherwise the file does must not have errors to pass the test.
