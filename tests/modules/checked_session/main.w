import "tests/modules/checked_session/left.w"
import "tests/modules/checked_session/right.w"
import "tests/modules/checked_session/shared.w"

fn main() -> unit {
    let a = left.make()
    let b = right.make()
    print(a.value, b.value, shared.id(7), shared.id[str]("yes"), shared.id(Some(4)) ?? 0, left.shared.value())
    let c = shared.identity(a)
    print(a, b, c.value, shared.mode(), shared.shadow(2))
}
