# Differential test for 64-bit two's complement wrapping and C99/W truncation-toward-zero division/modulo

fn main() -> unit {
    let max_i: int = 9223372036854775807
    let wrapped_add = max_i + 1
    let wrapped_sub = wrapped_add - 1
    let wrapped_mul = max_i * 2
    print("wrap:", wrapped_add, wrapped_sub, wrapped_mul)

    # Negative division and modulo (truncation toward zero)
    print("div:", -7 / 2, 7 / -2, -7 / -2)
    print("mod:", -7 % 2, 7 % -2, -7 % -2)

    # IEEE-754 float semantics (+0.0 == -0.0)
    let pz = 0.0
    let nz = -0.0
    print("zero_eq:", pz == nz, pz != nz)
}
