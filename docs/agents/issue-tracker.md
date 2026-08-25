# Issue tracker: GitHub

Issues and specs for this repository live as GitHub issues. Use the `gh` CLI for all operations and infer the repository from its Git remote.

## Conventions

- Create, read, comment on, label, and close issues with the corresponding `gh issue` commands.
- Fetch issue bodies, labels, and comments when a skill needs the complete ticket.
- Use multiline issue bodies rather than flattening specifications into command-line text.
- GitHub pull requests are not a triage request surface.
- When a skill says "publish to the issue tracker," create a GitHub issue.
- When a skill says "fetch the relevant ticket," read the complete GitHub issue and its comments.

## Wayfinding operations

- A wayfinding map is one issue labeled `wayfinder:map`.
- Child tickets use GitHub sub-issues when available.
- Blocking relationships use native GitHub issue dependencies when available.
- The first open, unassigned child without an open blocker is the frontier.
- Claim work by assigning the issue to the current GitHub user before modifying the repository.
- Resolve work with an evidence-backed comment and issue closure.
