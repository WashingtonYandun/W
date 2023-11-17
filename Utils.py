iota_count = 0


def iota(restart: bool = False) -> int:
    global iota_count

    if restart:
        iota_count = 0

    counter = iota_count
    iota_count = iota_count + 1
    return counter
