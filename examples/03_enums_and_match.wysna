## 03_enums_and_match.w
## Sum types (enum), Product types (struct), and exhaustive pattern matching.

enum TaskStatus {
    Todo
    InProgress
    Completed
}

struct Task {
    id: int
    title: str
    status: TaskStatus
}

fn status_badge(status: TaskStatus) -> str {
    return match status {
        TaskStatus.Todo => "[TODO]"
        TaskStatus.InProgress => "[WIP]"
        TaskStatus.Completed => "[DONE]"
    }
}

fn format_task(task: Task) -> str {
    return status_badge(task.status) + " #" + str(task.id) + ": " + task.title
}

fn main() -> unit {
    let backlog = [
        Task { id: 1, title: "Freeze SPEC.md v0.1", status: TaskStatus.Completed },
        Task { id: 2, title: "Self-host W1 compiler", status: TaskStatus.Completed },
        Task { id: 3, title: "Ship global CLI installer", status: TaskStatus.InProgress },
        Task { id: 4, title: "Write benchmarks", status: TaskStatus.Todo },
    ]

    for idx, item in enumerate(backlog) {
        print(idx, format_task(item))
    }
}
