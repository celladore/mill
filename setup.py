"""Setup for Mill's compatible xtotext Python distribution."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="xtotext",
    version="1.0.0",
    author="Celladore",
    description="Mill document conversion compatibility package",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "Pillow>=8.0.0",
        "python-docx>=0.8.11",
        "beautifulsoup4>=4.9.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov",
            "black",
            "flake8",
            "mypy",
        ],
        "azure": [
            "azure-functions",
            "azure-storage-blob",
            "azure-identity",
        ],
        "api": [
            "fastapi",
            "uvicorn",
            "pydantic",
        ],
    },
    entry_points={
        "console_scripts": [
            "xtotext=xtox.cli.main:main",
        ],
    },
)
