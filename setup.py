from setuptools import find_packages, setup

setup(
    name="hface",
    version="0.0",
    author="Miloslav Pojman",
    author_email="mpojman@akamai.com",
    description="Hackable HTTP/{1,2,3} {client,server,proxy}",
    package_dir={"": "src"},
    packages=find_packages("src"),
    python_requires=">=3.7",
    install_requires=[
        "aioquic",
        "anyio",
        "h11",
        "h2",
        "importlib-metadata",
    ],
    extras_require={
        "all": [
            "anyio[trio]",
            "uvloop",
        ],
        "trio": [
            "anyio[trio]",
        ],
        "uvloop": [
            "uvloop",
        ],
        "dev": [
            "black",
            "flake8",
            "isort",
            "pytest",
            "mypy>=0.981",
        ],
    },
    entry_points={
        "console_scripts": [
            "hface = hface.cli:run",
        ]
    },
    include_package_data=True,
    zip_safe=False,
)
