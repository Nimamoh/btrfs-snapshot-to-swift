import pytest
from ansi import colors as C


def test_colors():
    print(f"{C.red}red{C.reset}")
    print(f"{C.red}Hel{C.bright_red}lo {C.yellow}world{C.reset}")
    print(f"This is {C.color256(1)}256 colors{C.reset}")


if __name__ == "__main__":
    pytest.main(["-s", "-vv", __file__])
