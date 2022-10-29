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
