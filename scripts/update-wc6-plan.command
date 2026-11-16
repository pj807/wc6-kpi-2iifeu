#!/bin/zsh
# "Update WC6 plan": opens Claude Code in the WUW workspace with the re-read instruction.
# No passwords or tokens here. Claude Code asks for permission as usual.
export PATH="$HOME/.local/bin:$PATH"
cd "$HOME/Library/Mobile Documents/com~apple~CloudDocs/Claude/Claude WUW" || { echo "WUW folder not found"; read; exit 1; }
CLAUDE_CONFIG_DIR="$HOME/.claude-wuw" exec claude "Re-read the WC6 plan: re-read only the flagged workflows read-only in Chrome, update plan.json, run the privacy scan, push, run the workflow once, and report back with the new counts."
