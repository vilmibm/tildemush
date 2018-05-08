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
        'urwid==2.0.1',
    ],
    extras_require={
        'testing': [
            'tmserver==1.0.0',
            'pytest==3.5.0',
            'pytest-asyncio==0.8.0',
        ]
    },
    include_package_data=True,
    entry_points={
          'console_scripts': [
              'tmclient = tmclient.__init__:main',
          ]
    },
)
