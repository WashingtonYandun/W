pub interface Reader[T] { fn get() -> T }
pub class Box[T] implements Reader[T] {
    private value: T
    fn init(value: T) { this.value = value }
    public fn get() -> T { return this.value }
}
