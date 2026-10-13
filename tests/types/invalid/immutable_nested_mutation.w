struct Person {
    tags: list[str]
}

fn main() -> unit {
    let p = Person { tags: ["dev"] }
    p.tags.append("illegal")
}
