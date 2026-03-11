"""Setup script for FHIR client library."""

from setuptools import find_packages, setup

setup(
    name="fhir-client",
    version="0.1.0",
    description="FHIR R4B client library",
    packages=["src", "src.client", "src.models", "src.services", "src.utils"],
    install_requires=[
        "httpx>=0.28.0",
        "pydantic>=2.0.0",
        "fhir.resources>=7.0.0",
    ],
    python_requires=">=3.11",
)
