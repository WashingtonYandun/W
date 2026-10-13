## 06_game_of_life.w
## Conway's Game of Life in W v0.1 (Glider simulation with ARC + Copy-on-Write value semantics).

struct Grid {
    width: int
    height: int
    cells: list[int]
}

fn make_grid(width: int, height: int) -> Grid {
    let mut cells: list[int] = []
    let total = width * height
    for i in 0..total {
        cells.append(0)
    }
    return Grid {
        width: width,
        height: height,
        cells: cells,
    }
}

fn get_cell(g: Grid, x: int, y: int) -> int {
    if x < 0 or x >= g.width or y < 0 or y >= g.height {
        return 0
    }
    return g.cells[y * g.width + x]
}

fn set_cell(g: Grid, x: int, y: int, val: int) -> Grid {
    let mut next = g
    let mut cells = next.cells
    cells[y * g.width + x] = val
    next.cells = cells
    return next
}

fn count_neighbors(g: Grid, cx: int, cy: int) -> int {
    let mut count = 0
    for dy in -1..=1 {
        for dx in -1..=1 {
            if not (dx == 0 and dy == 0) {
                count = count + get_cell(g, cx + dx, cy + dy)
            }
        }
    }
    return count
}

fn step_generation(g: Grid) -> Grid {
    let mut next = make_grid(g.width, g.height)
    let mut next_cells = next.cells
    for y in 0..g.height {
        for x in 0..g.width {
            let alive = get_cell(g, x, y)
            let neighbors = count_neighbors(g, x, y)
            let mut next_state = 0
            if alive == 1 {
                if neighbors == 2 or neighbors == 3 {
                    next_state = 1
                }
            } else {
                if neighbors == 3 {
                    next_state = 1
                }
            }
            next_cells[y * g.width + x] = next_state
        }
    }
    next.cells = next_cells
    return next
}

fn render_grid(g: Grid, gen: int) -> unit {
    print("=== Generation " + str(gen) + " ===")
    for y in 0..g.height {
        let mut row_str = ""
        for x in 0..g.width {
            if get_cell(g, x, y) == 1 {
                row_str = row_str + "#"
            } else {
                row_str = row_str + "."
            }
        }
        print(row_str)
    }
}

fn main() -> unit {
    # Initialize 6x6 board with a classic Glider:
    # . # .
    # . . #
    # # # #
    let mut board = make_grid(6, 6)
    board = set_cell(board, 1, 0, 1)
    board = set_cell(board, 2, 1, 1)
    board = set_cell(board, 0, 2, 1)
    board = set_cell(board, 1, 2, 1)
    board = set_cell(board, 2, 2, 1)

    for gen in 0..=4 {
        render_grid(board, gen)
        board = step_generation(board)
    }
}
