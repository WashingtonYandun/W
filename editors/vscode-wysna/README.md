# Wysna Language Support for VS Code / Cursor / Antigravity

Provides syntax highlighting, comment toggling (`#`), and bracket auto-closing for `.wysna` source files according to `SPEC.md v0.1`.

## Install in 1 Command

From the repository root:

```bash
# VS Code
ln -sfn "$(pwd)/editors/vscode-wysna" ~/.vscode/extensions/washingtonyandun.wysna-lang-0.1.0

# Cursor
ln -sfn "$(pwd)/editors/vscode-wysna" ~/.cursor/extensions/washingtonyandun.wysna-lang-0.1.0

# Antigravity
ln -sfn "$(pwd)/editors/vscode-wysna" ~/.antigravity/extensions/washingtonyandun.wysna-lang-0.1.0
```

Reload the window (`Cmd+Shift+P` -> `Developer: Reload Window`) to activate `.wysna` syntax highlighting.
