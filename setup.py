from setuptools import setup, find_packages
import pathlib

here = pathlib.Path(__file__).parent.resolve()

long_description = (here / 'README.md').read_text(encoding='utf-8')

setup(
    name='btrfs-snapshot-to-webarchive',
    version='0.0.1+0',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Nimamoh',
    author_email='nimamoh@nimamoh.net',

    keywords='local, script, system, administration',

    package_dir={'': 'src'},
    packages=find_packages(where='src', exclude='repls'),

    python_requires='>=3.9, <4',

    install_requires=[
        'python-swiftclient',
        'python-keystoneclient',
        'pyinputplus',
        'coloredlogs',
        'humanize',
    ],
    extras_require={
        'dev': ['black', 'mypy', 'ptpython', 'pytest', 'pytest-watch'],
    },
    entry_points={
        'console_scripts': ['btrfs-snapshots-to-swift=main:main']
    },
)
