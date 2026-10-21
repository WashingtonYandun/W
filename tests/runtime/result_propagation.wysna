fn read_and_wrap(path: str) -> str ! IoError {
    let content = read_file(path)?
    return "[" + content + "]"
}

let w = write_file("tests/runtime/temp_file.txt", "hello W")
let ok_res = read_and_wrap("tests/runtime/temp_file.txt")
print(ok_res)
