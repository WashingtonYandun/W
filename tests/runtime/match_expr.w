enum Status {
    Pending,
    Active,
    Completed
}

fn describe(s: Status) -> str {
    match s {
        Status.Pending => { "is pending" }
        Status.Active => { "is active" }
        Status.Completed => { "is done" }
    }
}

print(describe(Status.Active))
print(describe(Status.Completed))
