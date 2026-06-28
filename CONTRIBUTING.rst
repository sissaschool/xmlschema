*************************
Contributing to xmlschema
*************************

Contributions to the *xmlschema* package are welcome! You can contribute by
reporting bugs, improving documentation, or submitting pull requests for new
features or bug fixes.

Reporting bugs
==============

Please use the project's issue tracker to report bugs. When opening an issue,
try to provide:

* A clear description of the problem.
* A minimal, self-contained example or test data that reproduces the issue.
* Information about your environment (Python version, xmlschema version, elementpath version, etc.).

Pull requests
=============

If you want to contribute code, please keep in mind the project's goals:

* The primary purpose of this package is to provide a base implementation of XMLSchema.
* Avoid adding features that are expensive to maintain.
* Changes must not introduce backward incompatibilities. If a change to existing
  behavior is necessary, proposed modifications that introduce backward
  incompatibilities must remain inactive until the next major release, with
  only relevant deprecations or warnings being activated in the interim.
* Code contributions should be prepared manually to ensure a full understanding
  of the changes. If you are unsure or if the change is complex, it is better
  to open an issue first to provide the specific case and start a discussion.

Please follow these steps:

1. Fork the repository and create a new branch for your changes.
2. Ensure your code follows the existing coding style and standards.
3. Write or update tests to cover your changes.
4. Verify that all tests pass using ``tox`` or by running the test suite manually.
5. Submit a pull request with a clear description of your changes.

Development environment
=======================

To set up a development environment, you can install the package in editable
mode with development dependencies::

    pip install -e .[dev]

Alternatively, you can use the provided ``requirements-dev.txt`` file::

    pip install -r requirements-dev.txt

Running tests
=============

The project uses the standard ``unittest`` framework. You can run the tests
manually using::

    python -m unittest

It is recommended to use ``tox`` to run tests against all supported Python
versions and to check code quality::

    tox

As an alternative to standard methods, you can use the ``run_*`` scripts located
in the ``tests/`` directory. In particular, the ``tests/run_w3c_tests.py`` script
allows running W3C XMLSchema tests by specifying parameters and output verbosity.
The W3C tests can be downloaded from the `xsdtests <https://github.com/w3c/xsdtests>`_
repository, which must be cloned in a directory at the same level as the project.
For example, to run all tests with increased verbosity::

    python tests/run_w3c_tests.py -v --xml

Coding style
============

Code should follow the PEP 8 style guidelines. The project uses ``flake8`` for
linting and ``mypy`` for static type checking. You can run these checks via ``tox``
or directly::

    flake8 xmlschema tests
    mypy --strict xmlschema

AI Policy
=========

The use of AI-assisted tools (such as LLMs) is permitted under the following
strict conditions:

* **Scope**: AI-generated contributions should be limited to the generation of
  tests. Code changes should be prepared manually to ensure you fully understand
  the logic and the impact of the changes. AI tools may be used for code analysis
  to help understand existing logic or identify potential issues.
* **No Large Rewrites**: AI-generated or AI-inspired large-scale rewrites are
  rejected, as they are difficult to verify for correctness and may introduce
  subtle bugs.
* **No Error Suppression**: AI-assisted contributions and annexed tests must
  avoid resolving problems using error and warning suppression methodologies.
* **Responsibility**: The contributor remains fully responsible for the accuracy,
  correctness, and quality of the submitted code and tests.
* **Verification**: All AI-assisted content must be manually reviewed, understood,
  and verified by the contributor.
* **Licensing**: You must ensure that the AI-generated content does not violate
  any third-party intellectual property or licenses.

License
=======

By contributing to this project, you agree that your contributions will be
licensed under the MIT License.
