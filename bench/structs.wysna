# Benchmark 8: Struct value allocation, field read, and CoW field mutation

struct Vec3 {
    x: int
    y: int
    z: int
}

fn dot(a: Vec3, b: Vec3) -> int {
    return a.x * b.x + a.y * b.y + a.z * b.z
}

fn main() -> unit {
    let origin = Vec3 { x: 2, y: 3, z: 4 }
    let mut acc = 0
    let mut i = 0
    while i < 4000 {
        let mut p = origin
        p.x = p.x + i
        p.y = p.y - (i / 2)
        acc = (acc + dot(origin, p)) % 1000000
        i = i + 1
    }
    print(acc)
}
