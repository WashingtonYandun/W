enum State {
    Ready
    Done
}

fn check(s: State) -> int {
    let x = match s {
        State.Ready => 1,
        State.Done => "two",
    }
    return 0
}
