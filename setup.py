# setup.py

from setuptools import setup, find_packages

setup(
    name='myfabric-connector',
    version='0.1.25',
    packages=find_packages(),
    install_requires=[
        'websockets',
        'requests',
        'pysher',
    ],
    entry_points={
        'console_scripts': [
            'myfabric-connect = myfabric.main:main',
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
    python_requires='>=3.6',
)
