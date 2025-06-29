# W

W is an interpreted programming language that is designed to be simple and easy to use. It's a high-level language that is designed to be easy to read and write.

## Considerations

> [!IMPORTANT]
> Still working on it and it's not ready for use.
> Currently, am working on the lexer and parser. Then I will move to the interpreter with the AST.

## Syntax

The syntax is designed to be simple and easy to read and write. This is how it will look like in the future:

```python
# Normal function
const target: int = 9
arr: list[int] = [1, 2, 3, 4, 5]

func two_sum(target: int, arr: list[int]) -> list[int] {
    for i in range(len(arr)){
        for j in range(i + 1, len(arr)){
            if arr[i] + arr[j] == target {
                return [i, j]
            }
        }
    }
    return []
}

print(two_sum(target, arr))

# classes and interfaces
# If there is not access modifier, it's public
interface Flyer {
    func fly(self) -> None:
        pass
}

interface Swimmer {
    func swim(self) -> None:
        pass
}

class Duck(Animal, Flyer, Swimmer) {
    func __init__(self, name: str) -> None {
        self.name: str = name
    }

    func fly(self) -> None {
        print("The duck flies")
    }

    func swim(self) -> None {
        print("The duck swims")
    }

    private func be_a_duck(self) -> None {
        print("I am a duck")
    }
}
```

## Goals

-   [x] Lexer
-   [x] Parser
-   [x] Interpreter
-   [ ] Compiler

## Features Goals (Maybe, maybe not, still thinking about it)

-   [ ] OOP and access modifiers, interfaces
-   [ ] Async and Await
-   [ ] Exception Handling
-   [ ] Modules
