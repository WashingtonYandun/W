struct Box[T] {
    val: T
}

let b1 = Box[int] { val: 42 }
let b2 = Box[str] { val: "hello generics" }
let b3 = Box { val: 100 }
let b4 = Box(200)

print(b1.val)
print(b2.val)
print(b3.val)
print(b4.val)
