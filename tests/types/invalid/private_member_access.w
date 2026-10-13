class Vault {
    private secret: int

    fn init(s: int) {
        this.secret = s
    }

    private fn pin() -> int {
        return this.secret
    }
}

fn main() {
    let v = new Vault(42)
    print(v.secret)
}
