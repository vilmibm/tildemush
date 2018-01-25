#!/usr/bin/env python

from setuptools import setup

setup(
    name='tildemush',
    version='1.0.0',
    description='a modern mush primarily designed for tilde.town',
    url='https://github.com/vilmibm/tildemush',
    author='vilmibm',
    author_email='nks@neongrid.space',
    license='AGPL',
    classifiers=[
        'Topic :: Artistic Software',
        'License :: OSI Approved :: Affero GNU General Public License v3 (AGPLv3)',
    ],
    keywords='mush',
    packages=['tildemush'],
    install_requires = [],
    include_package_data = True,
    entry_points = {
          'console_scripts': [
              'tildemush_server = tildemush.__init__:main_server',
              'tildemush_client = tildemush.__init__:main_client',
          ]
    },
)
