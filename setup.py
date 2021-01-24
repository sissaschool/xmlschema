#! /usr/bin/env python
#
# Copyright (c) 2016-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from setuptools import setup, find_packages

with open("README.rst") as readme:
    long_description = readme.read()


setup(
    name='xmlschema',
    version='1.4.2',
    packages=find_packages(include=['xmlschema', 'xmlschema.*']),
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'xmlschema-validate=xmlschema.cli:validate',
            'xmlschema-xml2json=xmlschema.cli:xml2json',
            'xmlschema-json2xml=xmlschema.cli:json2xml',
        ]
    },
    python_requires='>=3.6',
    setup_requires=['elementpath>=2.1.2, <3.0.0'],
    install_requires=['elementpath>=2.1.2, <3.0.0'],
    extra_require={
        'dev': ['tox', 'coverage', 'lxml', 'elementpath>=2.1.2, <3.0.0',
                'memory_profiler', 'Sphinx', 'sphinx_rtd_theme']
    },
    author='Davide Brunato',
    author_email='brunato@sissa.it',
    url='https://github.com/sissaschool/xmlschema',
    license='MIT',
    license_file='LICENSE',
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
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Software Development :: Libraries',
        'Topic :: Text Processing :: Markup :: XML',
    ]
)
