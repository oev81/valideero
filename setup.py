#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name="valideero",
    version="0.0.1",
    description="Validation library for Python",
    long_description=open("README.rst").read(),
    url="https://github.com/oev81/valideero",
    author="Evgeny Odegov",
    author_email="evg.odegov@gmail.com",
    packages=find_packages(),
    install_requires=["decorator"],
    test_suite="valideero.tests",
    platforms=["any"],
    keywords="validation adaptation typechecking jsonschema",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
    ],
)
