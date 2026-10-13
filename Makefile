PREFIX ?= $(HOME)/.local
BINDIR ?= $(PREFIX)/bin

.PHONY: all test check selfhost install uninstall clean

all: selfhost test

test:
	./w test

check:
	./w check selfhost/w1.w

selfhost:
	@mkdir -p .w_cache
	./w build --selfhost selfhost/w1.w -o .w_cache/w1
	@echo "[OK] Native self-hosted W1 binary ready at .w_cache/w1"

install:
	./install.sh "$(BINDIR)"

uninstall:
	rm -f "$(BINDIR)/w"
	@echo "[OK] Removed $(BINDIR)/w"

clean:
	rm -rf .w_cache build dist *.egg-info
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
	@echo "[OK] Cleaned build caches"
