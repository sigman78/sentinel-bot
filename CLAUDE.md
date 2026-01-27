# CLAUDE.md

## Project
Scaffold project of self evolving personal AI assistant, see @README.md

## Rules
Built using python, dependencies managed by 'uv'.

Code must be self-explanatory but terse, targeted for machine ingestion and understanding.
Try to adhere to type-safety but not overburden with excessive typing if deduce is trivial.
Keep module level documents with module info index, architecture and plans.

Use best dev practices - testing, reviewing, linting. Use git when it makes sense, at least for checkpoints in time.

Manage context. If multiple agents is available - use action targeted: planning, researching, specific task coding, testing, reviewing.

When working on self-improvements (aside from trivial changes) - create separate git worktree with a branch (don't forget to copy over transient data you might need from source dir), work on it, verify work quality before merging back. 

## Documentation Guidelines
- Avoid ASCII art/graphics in documentation
- Use machine-readable formats: tables, lists, structured text
- Keep documentation terse and information-dense

## Code Organization
- Consolidate functionality into existing modules when possible
- Avoid creating excessive module files
- New files only when clear separation of concerns requires it

## Tools
Its a bootstrap, you can use only one which is built-in.

TBD
