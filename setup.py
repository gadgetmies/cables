#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from setuptools import setup, find_packages

# Utility function to read the README file.
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name=CMD_NAME,
    version=__version__,
    author='Gadgetmies',
    #author_email='',
    description='Definitions for misc cables',
    long_description=read(os.path.join(os.path.dirname(__file__), 'README.md')),
    long_description_content_type='text/markdown',
    install_requires=[
        'pyyaml',
        'pillow',
        'graphviz',
        'wireviz'
        ],
    license='GPLv3',
    keywords='cable connector hardware harness wiring wiring-diagram wiring-harness',
    url=APP_URL,
    entry_points={
        },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Topic :: Utilities',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        ],

)
