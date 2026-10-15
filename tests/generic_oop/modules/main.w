import "library.w" as library
let box: library.Reader[int] = library.Box[int](42)
let text = new library.Box[str]("hello")
print(box.get(), text.get())
