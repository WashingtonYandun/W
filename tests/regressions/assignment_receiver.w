class Cell {
    public value: int
    fn init(value: int) { this.value = value }
}
class Holder {
    public cell: Cell
    fn init() { this.cell = Cell(1) }
    fn replace() -> int { this.cell = Cell(2) return 9 }
}
let holder = Holder()
let original = holder.cell
holder.cell.value = holder.replace()
print(original.value, holder.cell.value)
