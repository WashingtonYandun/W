class AndInit {
    public ready: bool

    fn init() {
        true and (this.ready = true)
    }
}

class OrInit {
    public ready: bool

    fn init() {
        false or (this.ready = true)
    }
}

class BranchInit {
    public ready: bool

    fn init(flag: bool) {
        if flag {
            this.ready = true
        } else {
            this.ready = false
        }
    }
}

print(AndInit().ready, OrInit().ready, BranchInit(true).ready, BranchInit(false).ready)
