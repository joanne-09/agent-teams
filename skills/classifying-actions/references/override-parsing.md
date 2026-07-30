# Override parsing

Both host-user and repo-project settings may contain generic and seat-specific
overrides under `modules.m8_autonomy` (legacy top-level keys are also read).

```yaml
modules:
  m8_autonomy:
    autonomy_overrides:
      - action_id: 6
        class: R
        since: "2026-07-30T00:00:00Z"
        evolved_by: "octocat"
    seat_overrides:
      architect:
        3: A
      qa:
        6: A
```

`seat_overrides.<seat>` may also be a list of objects with `action_id` and
`class`. Classes are `A`, `R`, or `N`. Malformed values are ignored.

Resolution order is legacy default, built-in seat cell, user settings, then
project settings. Within a file, a generic `autonomy_overrides` entry wins
over the matching `seat_overrides` entry. Thus project > user > seat >
default. An `N` built-in seat cell returns immediately and cannot be promoted.

Host-user paths: `~/.board-superpowers/settings.yml`, with legacy
`overrides.yml` accepted. Project paths: `.board-superpowers/settings.local.yml`,
with legacy `config.local.yml` accepted.
