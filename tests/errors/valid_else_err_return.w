fn read_cfg() -> str ! IoError {
    let raw = read_file("config.w")?
    return raw
}

fn main() -> unit {
    let cfg = read_cfg() else err {
        return
    }
    print(cfg)
}
