class A {
 public x: int
 fn init() { this.x = 1 }
}
class B extends A {
 public x: str
 fn init() { super.init() this.x = "wrong" }
}
let a: A = B()
print(a.x + 1)
