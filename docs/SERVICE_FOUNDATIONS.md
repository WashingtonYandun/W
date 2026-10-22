# Service foundations and acceptance contracts

The synchronous toolkit supports bounded file tools. It does not provide an HTTP
server, scheduler, asynchronous sockets or cancellation. These are separate APIs,
not capabilities implied by native compilation or automatic resource release.

## Implemented resource boundary

Standard File and Bytes handles have trusted runtime owners. Returning an owner,
storing it in a container or capturing it in a lambda retains its lifetime. Explicit
close invalidates the checked ID for every alias. Borrowing does not create an owner.
Raw FFI disposal remains explicit; arbitrary callbacks never run from ARC release.
There is no strong-cycle collector and no language-level panic unwinding.

Run `python3 -m tests.unit.test_foundations` to execute README examples, unit-result
parity and 10,000/100,000 request iterations in each engine. Every completed request
must restore host handles and buffer storage to baseline. Logical object counts,
host counts and RSS are distinct; stable counters are necessary but not a measured
RSS or latency SLO. Production admission additionally needs RSS plateau and latency
measurements with a fixed working set on each deployment platform.

## JSON pilot contract

`std/json` provides a bounded parser for the first service pilot. `json.parse` limits
input to 1 MiB, nesting to 32 arrays/objects, and the parsed tree to 100,000 values.
`json.parse_with_limits` permits per-call budgets up to hard ceilings of 16 MiB,
32 levels and 100,000 values. Wysna `str` values are valid UTF-8 by the language
contract; JSON escapes additionally require paired UTF-16 surrogates. Errors carry
Unicode-scalar offsets, trailing input is rejected, duplicate keys keep the last
value, and numeric lexemes remain text until callers choose a conversion.

The standard-toolkit gate compares parser acceptance and decoded values with Python's
independent `json` implementation using exact decimal parsing and last-value duplicate
semantics. Its corpus includes malformed inputs, surrogate policy, depth limits and
custom byte/node budgets. Any HTTP integration must retain explicit response-size and
JSON parsing budgets.

## IO, scheduling and failure boundaries

- Each task owns a request context with deadline, cancellation state and resource
  budget. Cancellation is cooperative and returns a typed operational error; it
  cannot silently skip cleanup. Define completion-versus-cancellation races.
- Socket operations expose partial reads/writes and bounded buffers. The scheduler
  polls readiness without blocking the entire worker. Backpressure must propagate
  to the producer; unbounded queues are not permitted.
- Begin with isolated task ownership. Moving handles invalidates the sender;
  aliases and mutable objects cannot cross workers without an enforced protocol.
  Atomic refcounts alone do not make mutable storage thread-safe.
- Recoverable request errors return Result. A runtime panic currently terminates
  the process: do not claim per-request recovery. Until an isolation boundary exists,
  a supervisor must treat a crash as a worker failure.
- Keep flush, close and durable commit separate. Automatic release is best effort;
  explicit close reports IO errors. Rename cannot silently fall back to copying
  across volumes. Crash durability needs a separately tested filesystem protocol.

These contracts define the next pilot's gates. They do not justify introducing a
second backend or a concurrent runtime before semantic and ownership parity passes.
