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

from __future__ import annotations

import argparse
from abc import ABCMeta, abstractmethod


class Command(metaclass=ABCMeta):
    help: str | None = None

    @classmethod
    @abstractmethod
    def parse(cls, parser: argparse.ArgumentParser) -> None:
        """
        Register options for this command with the given argument parser.
        """
        raise NotImplementedError

    @classmethod
    def run_from_args(cls, args: argparse.Namespace) -> None:
        """
        Construct a command from parsed command-line options and run it.
        """
        cls.from_args(args).run()

    @classmethod
    @abstractmethod
    def from_args(cls, args: argparse.Namespace) -> Command:
        """
        Construct a command from parsed command-line options.
        """
        raise NotImplementedError

    @abstractmethod
    def run(self) -> None:
        """
        Run this command.
        """
        raise NotImplementedError
