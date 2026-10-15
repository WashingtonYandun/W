let d1 = {"a": 1, "b": 2}
let mut d2 = d1

d2["c"] = 3
d2["a"] = 100

print(len(d1))
print(d1["a"])
print(d1.get("c"))

print(len(d2))
print(d2["a"])
print(d2["c"])
