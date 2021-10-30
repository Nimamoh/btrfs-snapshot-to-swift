_prefix = "\u001b"
_reset = f"{_prefix}[0m"

def _print(*args, **kwargs):
    """print defaulting to no endline and flushing automatically"""

    end_arg = "end"
    flush_arg = "flush"
    if end_arg not in kwargs:
        kwargs[end_arg] = ""
    if flush_arg not in kwargs:
        kwargs[flush_arg] = True

    print(*args, **kwargs)
