from setuptools import setup, find_packages

setup(
    name="trontrust-guard",
    version="0.1.0",
    description="TronTrust Guard SDK — auto-check trust before every Tron transaction",
    long_description="Wraps a tronpy wallet with automatic trust checking. One line change to protect your bot from scammers.",
    py_modules=["trontrust_guard"],
    install_requires=[
        "tronpy>=0.5.0",
        "httpx>=0.28.0",
    ],
    python_requires=">=3.10",
)
