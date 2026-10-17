let failure: fn() -> int ! str = || -> int ! str { Err("bad") }
let success: fn() -> int ! str = || -> int ! str { Ok(7) }
let inferred: fn() -> int ! str = || => Err("short")
fn consume(callback: fn() -> int ! str) -> int { callback() else detail { len(detail) } }
print(consume(failure), consume(success), consume(inferred))
let offset = 4
let captured: fn() -> int ! str = || -> int ! str { Ok(offset + 1) }
print(consume(captured))
