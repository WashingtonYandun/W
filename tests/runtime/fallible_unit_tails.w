fn value() -> int ! str { 42 }
fn failure() -> int ! str { Err("failure") }
fn plain() -> unit ! str { 42 }
fn grouped() -> (unit ! str) { 99 }
fn constructed() -> unit ! str { Ok(42) }
fn branched(flag: bool) -> unit ! str { if flag { Ok(42) } else { Err("error") } }
fn boxed() -> unit ! str { value() }
fn failed() -> unit ! str { failure() }
fn recovered() -> unit ! str { value() else error { return Err(error) } }
class Worker {
    public fn run() -> unit ! str { value() }
    public fn fail() -> unit ! str { failure() }
}
let callback = |number: int| -> unit ! str { number }
let direct = |number: int| -> unit ! str => number
let constructed_callback = || -> unit ! str => Ok(42)
let branch_callback = |flag: bool| -> unit ! str { if flag { Ok(42) } else { Err("lambda") } }
let failing = || -> unit ! str { failure() }
print(plain(), boxed(), failed(), recovered(), Worker().run(), Worker().fail(), callback(7), failing(), grouped(), direct(8), constructed(), branched(true), branched(false), constructed_callback(), branch_callback(false))
