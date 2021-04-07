*******
Testing
*******

The tests of the *xmlschema* library are implemented using the Python's *unitest*
library. From version v1.1.0 the test scripts have been moved into the directory
``tests/`` of the source distribution. Only a small subpackage *extras/testing/*,
containing a specialized UnitTest subclass, a factory and builders for creating test
classes for XSD and XML file, has been left into the package's code.


Test scripts
============

There are several test scripts, each one for a different target. These scripts can
be run individually or by the unittest module. For example to run XPath tests through
the *unittest* module use the command:

.. code-block:: bash

    $ python -m unittest -k tests.test_xpath
    ..........
    ----------------------------------------------------------------------
    Ran 10 tests in 0.133s

    OK

The same run can be launched with the command `$ python tests/test_xpath.py` but an
additional header, containing info about the package location, the Python version and
the machine platform, is displayed before running the tests.

Under the base directory *tests/* there are the test scripts for the base modules
of the package. The subdirectory *tests/validators* includes tests for XSD validators
building (schemas and their components) and the subdirectory *tests/validation* contains
tests validation of XSD/XML and decoding/encoding of XML files.

To run all tests use the command `python -m unittest `. Also, the script *test_all.py* can
launched during development to run all the tests except memory and packaging tests.
From the project source base, if you have the *tox automation tool* installed, you can run
all tests with all supported Python's versions using the command ``tox``.


Test cases based on files
=========================

Three scripts (*test_all.py*, *test_schemas.py*, *test_validation.py*) create many tests
dinamically, building test classes from a set of XSD/XML files. Only a small set of test
files is published in the repository for copyright reasons. You can find the repository
test files into ``tests/test_cases/`` subdirectory.

You can locally extend the test with your set of files. For doing this create a submodule
or a directory outside the repository directory and then copy your XSD/XML files into it.
Create an index file called testfiles into the base directory were you put your cases and
fill it with the list of paths of files you want to be tested, one per line, as in the
following example:

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
For example the script *test_schemas.py* uses only *.xsd* files, where instead
the script *tests_validation.py* uses only *.xml* files.

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

**--lax-encode**
    Use lax mode on encode checks (for cases where test data uses default or
    fixed values or some test data are skipped by wildcards processContents).
    Ignored on schema tests.

**--debug**
    Activate the debug mode (only the cases with `--debug` are executed).

**--codegen**
    Test code generation with XML data bindings module.

If you put a ``--help`` on the first case line the argument parser show you all the options available.

To run tests with also your personal set of files you have provide the path to your custom *testfile*,
index, for example:

.. code-block:: text

   python xmlschema/tests/test_all.py ../extra-schemas/testfiles


Testing with the W3C XML Schema 1.1 test suite
==============================================

From release v1.0.11, using the script *test_w3c_suite.py*, you can run also tests based on the
`W3C XML Schema 1.1 test suite <https://github.com/w3c/xsdtests>`_. To run these tests clone the
W3C repo on the project's parent directory and than run the script:

.. code-block:: text

   git clone https://github.com/w3c/xsdtests.git
   python xmlschema/xmlschema/tests/test_w3c_suite.py

You can also provides additional options for select a subset of W3C tests, run
``test_w3_suite.py --help`` to show available options.


Direct testing of schemas and instances
=======================================

From release v1.0.12, using the script *test_files.py*, you can test schemas or XML instances
passing them as arguments:

.. code-block:: text

   $ cd tests/
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
