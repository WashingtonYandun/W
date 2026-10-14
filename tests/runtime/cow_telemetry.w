# Conformance Test: Copy-on-Write (CoW) Detach Telemetry & Path-Copying Asymptotics (B02)

struct Config {
    name: str,
    values: list[int]
}

class Tracker {
    public count: int

    fn init(initial: int) {
        this.count = initial
    }
}

fn test_matrix_scaling() -> unit {
    # N=4 rows, M=10 columns
    let mut matrix: list[list[int]] = [
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        [10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
        [20, 21, 22, 23, 24, 25, 26, 27, 28, 29],
        [30, 31, 32, 33, 34, 35, 36, 37, 38, 39]
    ]
    let snap = matrix
    eprint("__COW_CHECKPOINT__:matrix_aliased")

    # 1. First write to row 0: path-copying detaches outer list (N=4 slots) + row 0 (M=10 slots) = 14 slots
    # Sibling rows 1, 2, 3 remain shared with snapshot.
    matrix[0][0] = 999
    eprint("__COW_CHECKPOINT__:first_write")

    # 2. Second write to same row: in-place O(1) write, 0 additional detaches or copied slots.
    matrix[0][1] = 888
    eprint("__COW_CHECKPOINT__:second_write_same_row")

    # 3. Third write to row 1: outer list is already exclusive (0 detaches), row 1 detaches (M=10 slots).
    matrix[1][0] = 777
    eprint("__COW_CHECKPOINT__:third_write_other_row")

    print(matrix[0][0])
    print(matrix[0][1])
    print(matrix[1][0])
    print(matrix[2][5])
    print(snap[0][0])
    print(snap[0][1])
    print(snap[1][0])
    print(snap[2][5])
}

fn test_struct_with_list() -> unit {
    let mut c1 = Config { name: "release", values: [10, 20, 30] }
    let c2 = c1
    eprint("__COW_CHECKPOINT__:struct_aliased")

    # Mutate nested list inside struct: detaches struct (2 slots) and values list (3 slots)
    c1.values[0] = 99
    eprint("__COW_CHECKPOINT__:struct_list_write")

    print(c1.values[0])
    print(c2.values[0])
}

fn test_dict_of_lists() -> unit {
    let mut registry: dict[str, list[int]] = {
        "primes": [2, 3, 5, 7],
        "squares": [1, 4, 9, 16]
    }
    let reg_snap = registry
    eprint("__COW_CHECKPOINT__:dict_aliased")

    # Reassign dict entry: detaches dict (4 slots)
    registry["primes"] = [2, 3, 5, 7, 11]
    eprint("__COW_CHECKPOINT__:dict_write")

    let p1 = registry["primes"] ?? []
    let p2 = reg_snap["primes"] ?? []
    print(len(p1))
    print(len(p2))
}

fn test_class_in_cow_container() -> unit {
    let mut trackers = [new Tracker(1), new Tracker(2)]
    let trackers_snap = trackers
    eprint("__COW_CHECKPOINT__:class_in_list_aliased")

    # Mutating field of class instance in list:
    # Outer list detaches to project mutable lvalue, but Tracker instance is NOT cloned (reference semantics)
    trackers[0].count = 42
    eprint("__COW_CHECKPOINT__:class_field_mutated")

    # Repeated field mutation on another element: in-place O(1), 0 additional detaches
    trackers[1].count = 84
    eprint("__COW_CHECKPOINT__:class_field_mutated_again")

    print(trackers[0].count)
    print(trackers_snap[0].count)
    print(trackers[1].count)
    print(trackers_snap[1].count)
}

fn main() -> unit {
    test_matrix_scaling()
    test_struct_with_list()
    test_dict_of_lists()
    test_class_in_cow_container()
}

main()
