import sys
import setuptools


# load some metadata from other files
with open("README.md", "r") as fh:
    long_description = fh.read()

with open("VERSION", "r") as fh:
    version = fh.read()

with open("requirements.txt", "r") as fh:
    requirements = [line.strip() for line in fh.readlines()]

app_name = "dmi-amazon-recscrape"

setuptools.setup(
    name=app_name,
    version=version,
    author="Stijn Peeters",
    author_email="stijn.peeters@uva.nl",
    description="A selenium-based script to scrape Amazon product recommendations with, generating GDF files",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/digitalmethodsinitiative/dmi-amazon-recscrape",
    packages=setuptools.find_packages(),
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=requirements
)
