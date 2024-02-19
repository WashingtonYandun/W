iota_count = 0


def iota(restart: bool = False) -> int:
    """
    Returns a unique integer value each time it is called.
    
    Args:
        restart (bool, optional): If True, restarts the counter. Defaults to False.
    
    Returns:
        int: The current value of the counter.
    """
    global iota_count

    if restart:
        iota_count = 0

    counter = iota_count
    iota_count = iota_count + 1
    return counter


def is_skippable(char: str) -> bool:
    return char == " " or char == "\n" or char == "\t"


def is_int(char: str) -> bool:
    c = ord(char)
    bounds = [ord('0'), ord('9')]
    return bounds[0] <= c <= bounds[1]


def is_alpha(src: str) -> bool:
    return src.upper() != src.lower()
