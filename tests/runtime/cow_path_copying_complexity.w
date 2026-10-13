# Verifies structural Copy-on-Write Path Copying:
# When mutating a leaf in a nested matrix, only the path to the modified cell is detached.
# Untouched sibling rows and original snapshot remain completely preserved.

fn run_path_copying_test() -> unit {
    let mut matrix: list[list[int]] = [
        [10, 20, 30],
        [40, 50, 60],
        [70, 80, 90]
    ]

    # Create alias (refcount > 1 on outer list and sub-lists)
    let snapshot = matrix

    # Mutate leaf cell at (0, 1)
    matrix[0][1] = 999

    # 1. Mutated matrix has updated leaf value
    print(matrix[0][0])
    print(matrix[0][1])
    print(matrix[0][2])

    # 2. Snapshot has original leaf value intact
    print(snapshot[0][0])
    print(snapshot[0][1])
    print(snapshot[0][2])

    # 3. Untouched sibling branches are identical in both
    print(matrix[1][1])
    print(snapshot[1][1])
    print(matrix[2][2])
    print(snapshot[2][2])

    # Further nested mutation in another branch
    matrix[2][0] = 777
    print(matrix[2][0])
    print(snapshot[2][0])
}

run_path_copying_test()
