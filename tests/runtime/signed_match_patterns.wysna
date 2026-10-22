fn classify(value: int) -> str {
    match value {
        -9223372036854775808 => "minimum",
        -7 if false => "unreachable",
        -7 => "negative",
        0 => "zero",
        _ => "other"
    }
}
print(classify(-9223372036854775808), classify(-7), classify(0), classify(2))
let value: int? = -1
print(match value { Some(-1) => "nested", Some(_) => "other", None => "none" })
