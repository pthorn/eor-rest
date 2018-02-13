import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))

requires = [
    'pyramid >= 1.8.4',
    'SQLAlchemy >= 1.1.11',
    'voluptuous >= 0.10.5',
    'tzlocal >= 1.4'
]

setup(
    name='eor-rest',
    version='2.3.0',
    description='A REST backend for the Pyramid framework',
    long_description='',
    classifiers=[
        "Programming Language :: Python",
        "Framework :: Pylons",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
    ],
    author='p.thorn.ru@gmail.com',
    author_email='p.thorn.ru@gmail.com',
    url='',
    keywords='web wsgi bfg pylons pyramid',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    test_suite='eor_rest',
    install_requires=requires,
)
