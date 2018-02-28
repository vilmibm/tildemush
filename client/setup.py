#!/usr/bin/env python

from setuptools import setup

setup(
    name='tildemush-client',
    version='1.0.0',
    description='a modern mush primarily designed for tilde.town',
    url='https://github.com/vilmibm/tildemush',
    author='vilmibm',
    author_email='vilmibm@protonmail.ch',
    license='AGPL',
    classifiers=[
        'Topic :: Artistic Software',
        'License :: OSI Approved :: Affero GNU General Public License v3 (AGPLv3)',
    ],
    keywords='mush',
    packages=['tmclient'],
    install_requires=[
        'click==6.7',
        'asciimatics==1.9.0',
    ],
    include_package_data=True,
    entry_points={
          'console_scripts': [
              'tmclient = tmclient.__init__:main',
          ]
    },
)
