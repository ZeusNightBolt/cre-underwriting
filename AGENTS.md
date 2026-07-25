# cre-underwriting

Python 3.12, uv for env management.

## Commands
- Test: `pytest -q`
- Hermetic: `pytest -m hermetic -q`
- Install: `pip install -r requirements.txt`
- Sync before work: `bash ~/.hermes/scripts/hermes_git_sync.sh cre-underwriting main`

## Branch Workflow
- Never push to main directly. Branch → PR → green CI → squash merge.
- After merge: grep main for the key symbol to verify the diff arrived.

## Remote
`https://github.com/girnarholdings/cre-underwriting.git`

## Do Not
- Leave run intermediates untracked — gitignore them (HERMES.md §12)
- Use `git commit -a` in shared checkouts
- Bypass tests with --no-verify (blocked by guard-destructive-flags hook)
