from setuptools import setup, find_packages

setup(
    name="bridge-md-notion",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    entry_points={
        "console_scripts": [
            "bridge-sync=bridge_sync.cli:main",
        ],
    },
)
