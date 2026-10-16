fn temporary() -> str {
    let text = "ab" + "cd"
    return text[1]
}
let mut total = 0
let mut valid = true
for code in 0..128 {
    let text = chr(code)
    total = total + ord(text[0])
    valid = valid and len(text) == 1 and ord(text) == code
}
let retained = temporary()
let mut values = [retained, chr(0), chr(127), chr(128), chr(128578)]
let snapshot = values
values[0] = chr(65)
print(total, valid, retained, values[0], snapshot[0])
print(len(snapshot[1]), ord(snapshot[1]), ord(snapshot[2]), ord(snapshot[3]), ord(snapshot[4]))
print(ord(("x" + "\0y")[1]), len("é🙂"), ord(("é" + "🙂")[1]))
