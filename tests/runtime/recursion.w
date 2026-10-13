fn factorial(n: int) -> int {
    if n <= 1 {
        return 1
    }
    return n * factorial(n - 1)
}

fn fib(n: int) -> int {
    if n <= 0 {
        return 0
    }
    if n == 1 {
        return 1
    }
    return fib(n - 1) + fib(n - 2)
}

print(factorial(5))
print(fib(7))
