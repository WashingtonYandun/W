fn run_compiler() -> unit ! IoError {
    let cli = args()
    let mut in_path = "selfhost/w1.w"
    let mut out_path = "build/compiler1.c"
    if len(cli) >= 3 {
        in_path = cli[1]
        out_path = cli[2]
    }
    let src = read_file(in_path)?
    check_source(src, in_path)
    let c_code = compile_source(src)
    write_file(out_path, c_code)?
    print("[W1] Compiled", in_path, "->", out_path)
}

let res = run_compiler() else err {
    eprint("[W4003] W1 I/O error:", err.message)
    exit(1)
}
