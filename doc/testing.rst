Testing
=======

Test scripts
------------

The tests of the *xmlschema* library are implemented using the Python's *unitest*
library. The test scripts are located under the installation base into ``tests/``
subdirectory. There are several test scripts, each one for a different topic:

**test_helpers.py**
    Tests for helper functions and classes

**test_meta.py**
    Tests for the XSD meta-schema and XSD builtins

**test_models.py**
    Tests concerning model groups validation

**test_package.py**
    Tests regarding ElementTree import and code packaging

**test_regex.py**
    Tests about XSD regular expressions

**test_resources.py**
    Tests about XML/XSD resources access

**test_schemas.py**
    Tests about parsing of XSD schemas and components

**test_validators.py**
    Tests regarding XML data validation/decoding/encoding

**test_xpath.py**
    Tests for XPath parsing and selectors

You can run all above tests with the script *test_all.py*. From the project source base, if you have
the *tox automation tool* installed, you can run all tests with all supported Python's versions
using the command ``tox``.


Test cases based on files
-------------------------

Two scripts (*test_schemas.py*, *test_validators.py*) create the most tests dinamically,
loading a set of XSD or XML files.
Only a small set of test files is published in the repository for copyright
reasons. You can found the published test files into ``xmlschema/tests/test_cases/``
subdirectory.

You can locally extend the test with your set of files. For doing this create a
``test_cases/`` directory at repository level and then copy your XSD/XML files
into it. Finally you have to create a file called *testfiles* in your
``test_cases/`` directory:

.. code-block:: bash

    cd test_cases/
    touch testfiles

Fill this file with the list of paths of files you want to be tested, one per line,
as in the following example:

.. code-block:: text

    # XHTML
    XHTML/xhtml11-mod.xsd
    XHTML/xhtml-datatypes-1.xsd

    # Quantum Espresso
    qe/qes.xsd
    qe/qes_neb.xsd
    qe/qes_with_choice_no_nesting.xsd
    qe/silicon.xml
    qe/silicon-1_error.xml --errors 1
    qe/silicon-3_errors.xml --errors=3
    qe/SrTiO_3.xml
    qe/SrTiO_3-2_errors.xml --errors 2

The test scripts create a test for each listed file, dependant from the context.
For example the script that test the schemas uses only *.xsd* files, where instead
the script that tests the validation uses both types, validating each XML file
against its schema and each XSD against the meta-schema.

If a file has errors insert an integer number after the path. This is the number of errors
that the XML Schema validator have to found to pass the test.

From version 1.0.0 each test-case line is parsed for those additional arguments:

**-L URI URL**
    Schema location hint overrides.

**--version=VERSION**
    XSD schema version to use for the test case (default is 1.0).

**--errors=NUM**
    Number of errors expected (default=0).

**--warnings=NUM**
    Number of warnings expected (default=0).

**--inspect**
    Inspect using an observed custom schema class.

**--defuse=(always, remote, never)**
    Define when to use the defused XML data loaders.

**--timeout=SEC**
    Timeout for fetching resources (default=300).

**--skip**
    Skip strict encoding checks (for cases where test data uses default or fixed values
    or some test data are skipped by wildcards processContents).

**--debug**
    Activate the debug mode (only the cases with `--debug` are executed).

If you put a ``--help`` on the first case line the argument parser show you all the options available.

.. note::

    Test case line options are changed from version 1.0.0, with the choice of using almost only double
    dash prefixed options, in order to simplify text search in long *testfiles*, and add or remove
    options without the risk to change also parts of filepaths.

To run tests with also your personal set of files you have to add a ``-x/--extra`` option to the
command, for example:

.. code-block:: text

   python xmlschema/tests/test_all.py -x

or:

.. code-block:: text

    tox -- -x


Testing with the W3C XML Schema 1.1 test suite
----------------------------------------------

From release v1.0.11, using the script *test_w3c_suite.py*, you can run also tests based on the
`W3C XML Schema 1.1 test suite <https://github.com/w3c/xsdtests>`_. To run these tests clone the
W3C repo on the project's parent directory and than run the script:

.. code-block:: text

   git clone https://github.com/w3c/xsdtests.git
   python xmlschema/xmlschema/tests/test_w3c_suite.py

You can also provides additional options for select a different set of tests:

**--xml**
    Add tests for instances, skipped for default.

**--xsd10**
    Run only XSD 1.0 tests.

**--xsd11**
    Run only XSD 1.1 tests.

**--valid**
    Run only tests signed as *valid*.

**--invalid**
    Run only tests signed as *invalid*.

**[NUM [NUM ...]]**
    Run only the cases that match a list of progressive numbers, associated
    to the test classes by the script.


Testing other schemas and instances
-----------------------------------

From release v1.0.12, using the script *test_files.py*, you can test schemas or XML instances
passing them as arguments:

.. code-block:: text

   $ cd xmlschema/tests/
   $ python test_files.py test_cases/examples/vehicles/*.xsd
   Add test 'TestSchema001' for file 'test_cases/examples/vehicles/bikes.xsd' ...
   Add test 'TestSchema002' for file 'test_cases/examples/vehicles/cars.xsd' ...
   Add test 'TestSchema003' for file 'test_cases/examples/vehicles/types.xsd' ...
   Add test 'TestSchema004' for file 'test_cases/examples/vehicles/vehicles-max.xsd' ...
   Add test 'TestSchema005' for file 'test_cases/examples/vehicles/vehicles.xsd' ...
   .....
   ----------------------------------------------------------------------
   Ran 5 tests in 0.147s

   OK
