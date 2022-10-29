from __future__ import annotations

import argparse
import dataclasses
import logging
from typing import Any, Callable, Coroutine

import anyio


@dataclasses.dataclass
class LoggingOptions:
    """
    Command-line options for logging configuration
    """

    log_level: str

    @classmethod
    def parse(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--log-level",
            default="WARNING",
            choices=("DEBUG", "INFO", "WARNING", "ERROR"),
            help="Logging level.",
        )

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> LoggingOptions:
        return cls(log_level=args.log_level)

    def configure(self) -> None:
        logging.basicConfig(format="%(asctime)s %(name)s %(levelname)s: %(message)s")
        logging.getLogger("hface").setLevel(self.log_level)


@dataclasses.dataclass
class LoopOptions:
    """
    Command-line options for event-loop configuration
    """

    loop: str

    @classmethod
    def parse(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--loop",
            default="asyncio",
            choices=("asyncio", "uvloop", "trio"),
            help="Event loop (anyio backend) to use.",
        )

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> LoopOptions:
        return cls(loop=args.loop)

    def run(self, func: Callable[..., Coroutine[Any, Any, Any]]) -> None:
        if self.loop == "asyncio":
            backend = "asyncio"
            backend_options = {"use_uvloop": False}
        elif self.loop == "uvloop":
            backend = "asyncio"
            backend_options = {"use_uvloop": True}
        elif self.loop == "trio":
            backend = "trio"
            backend_options = {}
        else:
            raise RuntimeError("Unsupported loop type: " + self.loop)
        anyio.run(func, backend=backend, backend_options=backend_options)
