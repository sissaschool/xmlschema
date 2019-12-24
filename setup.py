#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2019, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import importlib
from setuptools import setup
from setuptools.command.develop import develop
from setuptools.command.install import install

with open("README.rst") as readme:
    long_description = readme.read()


class DevelopCommand(develop):

    def run(self):
        develop.run(self)
        print("Post-develop: create Unicode categories JSON file")
        codepoints_module = importlib.import_module('xmlschema.codepoints')
        codepoints_module.save_unicode_categories()


class InstallCommand(install):

    def run(self):
        install.run(self)
        print("Post-install: create Unicode categories JSON file")
        codepoints_module = importlib.import_module('xmlschema.codepoints')
        codepoints_module.save_unicode_categories()


setup(
    name='xmlschema',
    version='1.0.18',
    setup_requires=['elementpath~=1.3.0'],
    install_requires=['elementpath~=1.3.0'],
    packages=['xmlschema'],
    include_package_data=True,
    cmdclass={
        'develop': DevelopCommand,
        'install': InstallCommand
    },
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
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Software Development :: Libraries'
    ]
)
