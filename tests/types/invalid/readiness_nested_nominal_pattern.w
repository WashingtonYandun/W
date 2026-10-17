# ERROR: W2001
enum A { V(int) }
enum B { V(int) }
let value = (A.V(3), 1)
match value { (B.V(number), _) => print(number) }
