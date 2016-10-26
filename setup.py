# -*- coding: utf-8 -*-
#
# Copyright (c), 2016, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from setuptools import setup

with open("README.rst") as readme:
    long_description = readme.read()

setup(
    name='xmlschema',
    version='0.8a6',
    packages=['xmlschema', 'xmlschema.tests'],
    package_data={
        'xmlschema': ['schemas/*/*.xsd', 'tests/examples/*']
    },
    author='Davide Brunato',
    author_email='brunato@sissa.it',
    url='https://github.com/brunato/xmlschema',
    license='MIT',
    long_description=long_description,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Software Development :: Libraries'
    ]
)
