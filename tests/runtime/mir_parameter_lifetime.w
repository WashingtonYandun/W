let mut shared = "old"

fn replace_shared() -> int {
    shared = "new"
    7
}

fn preserve(text: str) -> str {
    print(len(text), replace_shared(), text[0])
    return text
}

fn remember(text: str) -> list[str] { [text, text] }
fn capture(text: str) -> fn() -> str { || => text }
fn success(text: str) -> str ! str { Ok(text) }
fn failure(text: str) -> int ! str { Err(text) }

let retained = preserve(shared + "-é")
print(retained, shared)
shared = "before"
print(shared, replace_shared())
let values = remember("saved-" + str(3))
print(values[0], values[1])
let callback = capture("captured-" + str(4))
print(callback())
print(success("result-" + str(5)) else error { error })
print(failure("error-" + str(6)) else error { len(error) })
