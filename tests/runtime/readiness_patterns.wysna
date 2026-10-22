enum State { Ready(int), Waiting }
fn tuple_label(value: tuple[bool, bool]) -> int {
    match value {
        (true, true) => 1,
        (true, false) => 2,
        (false, _) => 3
    }
}
fn nested(value: tuple[State, bool]) -> int {
    match value {
        (State.Ready(number), true) if number > 4 => number,
        (State.Ready(number), _) => number + 10,
        (State.Waiting, _) => 0
    }
}
let pair = (1, "s")
match pair { (number, text) => print(number, text) }
print(tuple_label((true, true)), tuple_label((true, false)), tuple_label((false, true)))
print(nested((State.Ready(7), true)), nested((State.Ready(2), false)), nested((State.Waiting, true)))
