#!/usr/bin/env python

from setuptools import setup

setup(
    name='tildemush-server',
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
    packages=['tmserver'],
    install_requires=[
        'click==6.7',
        'peewee==3.1.1',
        # TODO we may want psycopg2 (ie not binary) once they release 2.8. i'm
        # not sure.
        'psycopg2-binary==2.7.4',
        'websockets==4.0.1',
        'bcrypt==3.1.4',
        'hy==0.14.0',
    ],
    extras_require={
        'testing': [
            'pytest==3.5.0',
            'pytest-asyncio==0.8.0'
        ]
    },
    include_package_data=True,
    entry_points={
          'console_scripts': [
              'tmserver = tmserver.__init__:main',
          ]
    },
)
