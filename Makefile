PREFIX ?= $(HOME)/.local
BINDIR ?= $(PREFIX)/bin

.PHONY: all test check selfhost install uninstall clean

all: selfhost test

test:
	./wysna test

check:
	./wysna check selfhost/compiler.wysna

selfhost:
	@mkdir -p .w_cache
	./wysna build --selfhost selfhost/compiler.wysna -o .w_cache/wysna_selfhost
	@echo "[OK] Native self-hosted compiler binary ready at .w_cache/wysna_selfhost"

install:
	./install.sh "$(BINDIR)"

uninstall:
	rm -f "$(BINDIR)/wysna"
	@echo "[OK] Removed $(BINDIR)/wysna"

clean:
	rm -rf .w_cache build dist *.egg-info
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
	@echo "[OK] Cleaned build caches"
