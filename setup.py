from setuptools import setup, find_packages

setup(
    name="adder_repo",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "telethon",
        "sqlalchemy",
        "pydantic",
        "loguru",
        "cryptography",
        "click",
    ],
)
