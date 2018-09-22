# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2018, SISSA (International School for Advanced Studies).
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
    version='1.0.4',
    install_requires=['elementpath>=1.0.12', 'defusedxml>=0.5'],
    packages=['xmlschema', 'xmlschema.validators', 'xmlschema.tests'],
    package_data={'xmlschema': [
        'unicode_categories.json', 'validators/schemas/*.xsd', 'validators/schemas/*/*.xsd',
        'tests/cases/*', 'tests/cases/*/*', 'tests/cases/*/*/*', 'tests/resources/*'
    ]},
    author='Davide Brunato',
    author_email='brunato@sissa.it',
    url='https://github.com/brunato/xmlschema',
    license='MIT',
    description='An XML Schema validator and decoder',
    long_description=long_description,
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Software Development :: Libraries'
    ]
)
