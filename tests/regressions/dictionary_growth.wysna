let mut entries: dict[int, int] = {}
for index in 0..2000 { entries[index] = index * 2 }
let snapshot = entries
entries[1000] = 7
entries[2000] = 8
print(len(entries), len(snapshot), entries[1000], snapshot[1000])
print(entries.keys()[0], entries.keys()[2000])
