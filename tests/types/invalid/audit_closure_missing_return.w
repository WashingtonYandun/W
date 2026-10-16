# ERROR: W2004
let f: fn(bool) -> int = |flag| -> int { if flag { return 3 } }
print(f(false))
