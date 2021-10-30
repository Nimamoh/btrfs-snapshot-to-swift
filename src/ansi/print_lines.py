import contextlib
import sys
from . import _print
from .cursor import lineup
from .line import clearline
from typing import Iterable, Optional, Sequence, TextIO

_DEFAULT_PRINTFN = lambda line, file: _print(line, end="\n", file=file)


@contextlib.contextmanager
def print_lines(
    lines: Sequence[str] = [],
    append_only: Optional[bool] = None,
    file: TextIO = None,
    printfn=_DEFAULT_PRINTFN,
):
    """
    Context manager which print lines and allow changing printed content
    Args:
        append_only (Optional[bool]): append instead of reprinting.
          If set to None (the default), it will check if stdout has an attached tty,
          in which case append_only will be set to False. If no tty is attached to stdout, it will pass in append_only mode.
          Setting True or False to the option bypasses the ttycheck and force append_only mode.
        file (TextIO): File in which printer will be printing escaped ascii characters
        printfn: function in charge of printing the contents (the lines)
    """
    try:
        file = file or sys.stdout

        actual_append_only = False
        if append_only is not None:
            actual_append_only = append_only
        else:
            actual_append_only = not file.isatty()

        sp = _SequencePrinter(
            lines, append_only=actual_append_only, file=file, printfn=printfn
        )
        yield sp
    finally:
        pass


class _SequencePrinter:
    """
    Printer accepting a list of string.
    Capable of changing list to print during its context runtime.
    """

    @staticmethod
    def _read_lines(content: Iterable[str]) -> tuple[str, ...]:
        acc = []
        for line in content:
            for y in line.splitlines():
                acc.append(y)

        return tuple(acc)

    def __init__(
        self,
        content: Iterable[str],
        append_only: bool = False,
        printfn=_DEFAULT_PRINTFN,
        file=None,
    ):
        self.__content: tuple[str, ...] = self._read_lines(content)
        self.__append_only = append_only
        self.__printfn = printfn
        self.__file = file or sys.stdout
        self._draw()

    def reprint(self, content: Iterable[str]):
        previous = self.__content
        current = self._read_lines(content)

        if not self.__append_only:
            for _ in previous:
                lineup(1, file=self.__file)
                clearline(file=self.__file)

        self.__content = current
        self._draw()

    def _draw(self):
        for line in self.__content:
            self.__printfn(str(line), file=self.__file)

    def _internal_seq(self) -> Sequence[str]:
        """
        Internal sequence the printer uses.
        It represents the currently printed content.
        """
        return self.__content
