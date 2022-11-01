# Copyright 2022 Akamai Technologies, Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from pathlib import Path

from setuptools import find_packages, setup

setup(
    name="hface",
    version="0.1",
    author="Miloslav Pojman",
    author_email="mpojman@akamai.com",
    description="Hackable HTTP/{1,2,3} {client,server,proxy}",
    url="https://github.com/akamai/hface",
    project_urls={
        "Documentation": "https://hface.readthedocs.io/",
        "Source Code": "https://github.com/akamai/hface",
    },
    long_description=Path(__file__).parent.joinpath("README.rst").read_text("utf-8"),
    long_description_content_type="text/x-rst",
    license="Apache License 2.0",
    keywords=[
        "HTTP",
        "HTTP/2",
        "HTTP/3",
        "server",
        "client",
        "proxy",
        "AnyIO",
        "asyncio",
        "Trio",
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Environment :: Web Environment",
        "Framework :: AnyIO",
        "Framework :: AsyncIO",
        "Framework :: Trio",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Topic :: Internet",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Topic :: Software Development :: Libraries",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Networking",
        "Typing :: Typed",
    ],
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
