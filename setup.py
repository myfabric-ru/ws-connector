# -*- coding: utf-8 -*-

from setuptools import setup, find_packages
from myfabric.__version__ import __version__

# Дополнительные зависимости для Python 2
extras_require = {
    ':python_version<"3"': ['pathlib2'],
}

setup(
    name='myfabric-connector',
    version=__version__,
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'pathlib2',
        'websocket-client',
        #'websockets',
        'requests',
        'pysher-khonik==1.0.12',
    ],
    #extras_require=extras_require,  # Условные зависимости
    entry_points={
        'console_scripts': [
            'myfabric-connector = myfabric.main:main',
        ],
    },
    author='Khonik',
    author_email='khonikdev@gmail.com',
    description='Программа для взаимодействия 3D принтеров и  CRM MyFabric',
    long_description=open('readme.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/myfabric-ru/ws-connector',
    classifiers=[
        'Programming Language :: Python :: 3',
    ],
)
