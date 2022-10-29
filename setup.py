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

from setuptools import find_packages, setup

setup(
    name="hface",
    version="0.0",
    author="Miloslav Pojman",
    author_email="mpojman@akamai.com",
    description="Hackable HTTP/{1,2,3} {client,server,proxy}",
    license="Apache License 2.0",
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
