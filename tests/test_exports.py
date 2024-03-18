#!/usr/bin/env python
#
# Copyright (c), 2016-2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""Tests concerning XML resources"""

import unittest
import pathlib
import platform
import tempfile

from xmlschema import XMLSchema
from xmlschema.exports import download_schemas
from xmlschema.testing import SKIP_REMOTE_TESTS


TEST_CASES_DIR = str(pathlib.Path(__file__).absolute().parent.joinpath('test_cases'))


def casepath(relative_path):
    return str(pathlib.Path(TEST_CASES_DIR).joinpath(relative_path))


class TestExports(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.vh_dir = casepath('examples/vehicles')
        cls.vh_xsd_file = casepath('examples/vehicles/vehicles.xsd')
        cls.vh_xml_file = casepath('examples/vehicles/vehicles.xml')

    @unittest.skipIf(SKIP_REMOTE_TESTS, "Remote networks are not accessible.")
    def test_download_schema(self):
        vh_schema_file = casepath('issues/issue_187/issue_187_2.xsd')

        with tempfile.TemporaryDirectory() as dirname:
            download_schemas(vh_schema_file, target=dirname, modify=True)

            xsd_path = pathlib.Path(dirname).joinpath('issue_187_2.xsd')
            schema = XMLSchema(xsd_path)
            for xs in schema.maps.namespaces['http://example.com/vehicles']:
                self.assertTrue(xs.url.startswith('file://'))

            self.assertTrue(pathlib.Path(dirname).joinpath('__init__.py').is_file())

        with tempfile.TemporaryDirectory() as dirname:
            download_schemas(vh_schema_file, target=dirname)

            xsd_path = pathlib.Path(dirname).joinpath('issue_187_2.xsd')
            schema = XMLSchema(xsd_path)
            for k, xs in enumerate(schema.maps.namespaces['http://example.com/vehicles']):
                if k:
                    self.assertTrue(xs.url.startswith('https://'))
                else:
                    self.assertTrue(xs.url.startswith('file://'))


if __name__ == '__main__':
    header_template = "Test xmlschema exports.py module with Python {} on platform {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
