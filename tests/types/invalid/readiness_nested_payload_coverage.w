# ERROR: W2003
enum Flag { Value(bool) }
fn incomplete(value: Flag) -> int {
    match value { Flag.Value(true) => 1 }
}
