# board-superpowers Producer MVP

A deliberately small Claude Code plugin for running the Producer side of an
AI engineering board.

It keeps only four workflows:

- route a session by seat and intent;
- intake a requirement and hand it from analyst to architect;
- deliver an architect-owned specification;
- let an EM dispatch Ready work by Role.

The durable board is a GitHub Project. Cards are GitHub Issues with `Status`
and `Role` single-select fields.

## What is intentionally absent

This MVP has no audit database, schema migrations, lifecycle hook, automatic
field provisioning, Codex package, multi-backend adapter, WIP policy engine,
or autonomous agent spawning. It renders kickoff prompts; a human or external
carrier starts the sessions.

## Requirements

- Claude Code 2.1+
- Python 3.9+
- GitHub CLI (`gh`), authenticated with repository and Project access
- an existing GitHub Project containing single-select `Status` and `Role`
  fields

Required options:

```text
Status: Backlog, Ready, In Progress, In Review, Done, Blocked
Role: analyst, architect, rd, qa, em, human
```

## Configure a consuming repository

From the consuming repository:

```powershell
python "C:\path\to\this-plugin\scripts\producer_board.py" init `
  --repo OWNER/REPO `
  --project-owner OWNER `
  --project-number 1
```

This creates `.board-superpowers/producer.json` in the consuming repository.
The file contains board coordinates, not credentials.

Validate access and field names:

```powershell
python "C:\path\to\this-plugin\scripts\producer_board.py" doctor
```

## Test as a development plugin

From the consuming repository:

```powershell
claude --plugin-dir "C:\path\to\this-plugin"
```

Inside Claude:

```text
/board-superpowers-producer:using-board-superpowers
[role:em] Show the dispatch queue.
[role:analyst] Intake this requirement: improve the setup documentation.
[role:architect] Author the specification for issue #12.
```

Use a disposable repository and Project for the first mutation test.

## Board CLI

```text
producer_board.py init
producer_board.py doctor
producer_board.py list [--role ROLE] [--status STATUS]
producer_board.py dispatch [--role ROLE] [--format text|json]
producer_board.py intake --title TITLE (--body BODY | --body-file PATH)
producer_board.py handoff ISSUE --from-role ROLE --to-role ROLE --note TEXT
```

All mutating commands print JSON describing the durable result.
