"""Various exceptions and factories"""

class FileIsTooLarge(RuntimeError):
    """Raised by the main script when file to upload is too large."""

    pass


class ProgrammingError(AssertionError):
    """An error that underlines a programming error"""

    pass
