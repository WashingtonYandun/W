struct PayloadError {
    message: str,
    details: list[str]
}

enum TransportError {
    Failed(str)
}

fn narrow() -> int ! PayloadError {
    let mut details = ["detail-" + str(1)]
    let snapshot = details
    details.append("detail-" + str(2))
    return Err(PayloadError { message: "payload-" + str(len(snapshot)), details: details })
}

fn choose(route: int) -> int ! PayloadError | TransportError {
    if route == 0 { return narrow() }
    if route == 1 { return Err(TransportError.Failed("transport-" + str(route))) }
    return 7
}

fn forward(route: int) -> int ! PayloadError | TransportError | str {
    let held = ["before-" + str(route), "propagation-" + str(route)]
    let value = choose(route)?
    return value + len(held)
}

fn recover(route: int) -> int {
    return forward(route) else err {
        match err {
            PayloadError(error) if len(error.details) == 0 => 1000,
            PayloadError(error) => {
                let mut copy = error
                copy.details.append("copy-" + str(route))
                len(error.details) * 10 + len(copy.details)
            },
            TransportError(error) => match error {
                TransportError.Failed(message) => len(message)
            },
            str(_) => 2000
        }
    }
}

fn exercise() -> int {
    let mut total = 0
    for iteration in 0..24 {
        total = total + recover(0) + recover(1) + recover(2)
    }
    return total
}

print(exercise())
