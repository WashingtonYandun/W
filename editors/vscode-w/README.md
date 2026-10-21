# Wysna Language Support for VS Code / Cursor / Antigravity

Provides syntax highlighting, comment toggling (`#`), and bracket auto-closing for `.wysna` and `.w` source files according to `SPEC.md v0.1`.

## Install in 1 Command

From the repository root:

```bash
# VS Code
ln -sfn "$(pwd)/editors/vscode-w" ~/.vscode/extensions/washingtonyandun.wysna-lang-0.1.0

# Cursor
ln -sfn "$(pwd)/editors/vscode-w" ~/.cursor/extensions/washingtonyandun.wysna-lang-0.1.0

# Antigravity
ln -sfn "$(pwd)/editors/vscode-w" ~/.antigravity/extensions/washingtonyandun.wysna-lang-0.1.0
```

Reload the window (`Cmd+Shift+P` -> `Developer: Reload Window`) to activate `.wysna` and `.w` syntax highlighting.
