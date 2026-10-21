PREFIX ?= $(HOME)/.local
BINDIR ?= $(PREFIX)/bin

.PHONY: all test check selfhost install uninstall clean

all: selfhost test

test:
	./wysna test

check:
	./wysna check selfhost/w1.wysna

selfhost:
	@mkdir -p .w_cache
	./wysna build --selfhost selfhost/w1.wysna -o .w_cache/w1
	@echo "[OK] Native self-hosted W1 binary ready at .w_cache/w1"

install:
	./install.sh "$(BINDIR)"

uninstall:
	rm -f "$(BINDIR)/wysna"
	@echo "[OK] Removed $(BINDIR)/wysna"

clean:
	rm -rf .w_cache build dist *.egg-info
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
	@echo "[OK] Cleaned build caches"
