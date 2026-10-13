interface Speakable {
    fn speak() -> str
}

class Animal implements Speakable {
    public name: str

    fn init(name: str) {
        this.name = name
    }

    public fn speak() -> str {
        return "..."
    }
}

class Dog extends Animal {
    private breed: str

    fn init(name: str, breed: str) {
        super.init(name)
        this.breed = breed
    }

    public fn speak() -> str {
        return this.name + " (" + this.breed + ") says Woof"
    }
}

class Cat extends Animal {
    fn init(name: str) {
        super.init(name)
    }

    public fn speak() -> str {
        return this.name + " says Meow"
    }
}

fn announce(s: Speakable) -> str {
    return s.speak()
}

fn main() {
    let d: Animal = new Dog("Rex", "Husky")
    let c: Speakable = new Cat("Luna")
    let pets: list[Animal] = [new Dog("Max", "Pug"), new Cat("Milo")]
    for p in pets {
        print(announce(p))
    }
    print(d.speak())
    print(c.speak())
}
