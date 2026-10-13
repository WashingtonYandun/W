let d1 = {"a": 1, "b": 2}
let mut d2 = d1

d2["c"] = 3
d2["a"] = 100

print(len(d1))
print(d1["a"] ?? 0)
print(d1["c"] ?? 0)

print(len(d2))
print(d2["a"] ?? 0)
print(d2["c"] ?? 0)
