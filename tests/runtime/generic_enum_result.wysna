fn parse_positive(n: int) -> int ! str {
    if n <= 0 {
        return Err("must be positive")
    }
    return Ok(n * 10)
}

fn safe_compute(x: int) -> Result[int, str] {
    let v = parse_positive(x)?
    return Ok(v + 1)
}

fn describe_result(r: Result[int, str]) {
    match r {
        Ok(v) => print("Success:", v),
        Err(e) => print("Error:", e)
    }
}

let r1: Result[int, str] = Ok(100)
let r2: Result[int, str] = Err("failed")
let r3 = Result.Ok(200)
let r4: Result[str, int] = Result.Err(404)

describe_result(r1)
describe_result(r2)

describe_result(safe_compute(5))
describe_result(safe_compute(-3))

print("eq ok:", Ok(42) == Ok(42))
print("eq err:", Err("bad") == Err("bad"))
print("eq diff:", Ok(1) == Err(1))
