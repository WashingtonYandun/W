# ERROR: W2003
fn incomplete(value: tuple[bool, bool]) -> int {
    match value { (true, _) => 1 }
}
