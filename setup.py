import setuptools


with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="circuitgraph",
    version="1.0.0",
    author="Ruben Purdy, Joseph Sweeney",
    author_email="rpurdy@andrew.cmu.edu, joesweeney@cmu.edu",
    description="Tools for working with circuits as graphs.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/rbnprdy/circuitgraph",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
