#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright © 2007-2010 Dieter Verfaillie <dieterv@optionexplicit.be>
#
# This file is part of elib.daemon.
#
# elib.daemon is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# elib.daemon is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with elib.daemon. If not, see <http://www.gnu.org/licenses/>.


import os
import re

from distribute_setup import use_setuptools; use_setuptools()
from setuptools import setup, find_packages


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

def version():
    file = os.path.join(os.path.dirname(__file__), 'lib', 'elib', 'daemon', '__init__.py')
    return re.compile(r".*__version__ = '(.*?)'", re.S).match(read(file)).group(1)


setup(namespace_packages=['elib'],
      name = 'elib-daemon',
      version = version(),
      description = 'Daemon implementation',
      long_description = read('README'),
      author = 'Dieter Verfaillie',
      author_email = 'dieterv@optionexplicit.be',
      url = 'http://github.com/dieterv/elib.daemon/',
      license = 'GNU Lesser General Public License',
      classifiers =
          ['Development Status :: 4 - Beta',
           'Environment :: Console',
           'Intended Audience :: Developers',
           'License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)',
           'Natural Language :: English',
           'Operating System :: POSIX',
           'Programming Language :: Python',
           'Topic :: System',
           'Topic :: Software Development :: Libraries :: Python Modules'],

      install_requires = ['distribute'],
      zip_safe = False,
      include_package_data = True,

      packages = find_packages('lib'),
      package_dir = {'': 'lib'})
