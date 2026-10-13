fn main() -> unit {
    let s = "hello_world"
    let sub = slice(s, 0, 5)
    print(sub)

    let code = ord("A")
    print(code)
    let ch = chr(code + 1)
    print(ch)

    let num_str = str(2026) + "_" + str(true)
    print(num_str)
}
