#! /usr/bin/env python
#
# Copyright (c) 2016-2022, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from setuptools import setup, find_packages
from pathlib import Path


with Path(__file__).parent.joinpath('README.rst').open() as readme:
    long_description = readme.read()


setup(
    name='xmlschema',
    version='3.4.2',
    packages=find_packages(include=['xmlschema*']),
    package_data={
        'xmlschema': ['py.typed', 'locale/**/*.mo', 'locale/**/*.po', 'schemas/*/*.xsd'],
        'xmlschema.extras': ['templates/*/*.jinja'],
    },
    entry_points={
        'console_scripts': [
            'xmlschema-validate=xmlschema.cli:validate',
            'xmlschema-xml2json=xmlschema.cli:xml2json',
            'xmlschema-json2xml=xmlschema.cli:json2xml',
        ]
    },
    python_requires='>=3.8',
    install_requires=['elementpath>=4.4.0, <5.0.0'],
    extras_require={
        'codegen': ['elementpath>=4.4.0, <5.0.0', 'jinja2'],
        'dev': ['tox', 'coverage', 'lxml', 'elementpath>=4.4.0, <5.0.0',
                'memory_profiler', 'Sphinx', 'sphinx_rtd_theme', 'jinja2',
                'flake8', 'mypy', 'lxml-stubs'],
        'docs': ['elementpath>=4.4.0, <5.0.0', 'Sphinx', 'sphinx_rtd_theme', 'jinja2']
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
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Software Development :: Libraries',
        'Topic :: Text Processing :: Markup :: XML',
    ]
)
