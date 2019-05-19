from setuptools import setup, find_packages

setup(
    name="heat-spreader",
    use_scm_version={"write_to": "src/heatspreader/version.py"},
    setup_requires=["setuptools_scm"],
    description="Heat multicloud service",
    author="ACTiCLOUD",
    author_email="simonkollberg@gmail.com",
    url="https://acticloud.eu",
    license="MIT",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
    ],
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "setuptools_scm>=3.3.1,<4.0.0",
        "aiohttp>=3.6.0,<4.0.0",
        "aiohttp-apispec>=1.3.0,<2.0.0",
        "colorama",
        "marshmallow>=3.2.0,<4.0.0",
        "marshmallow-oneofschema>=2.0.1,<3.0.0",
        "openstacksdk>=0.31.1",
        "peewee>=3.10.0,<4.0.0",
        "python-heatclient",
        "pyyaml>=5.1.2,<6.0.0",
        "structlog>=19.1.0,<20.0.0",
    ],
    extras_require={"test": ["tox"]},
    entry_points={
        "console_scripts": ["heat-spreader = heatspreader.shell.__main__:main"]
    },
)
