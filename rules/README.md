# Kit rules

Generic rules every project inherits (layer `kit`, ids numbered 900–999). Projects never edit these files: they override
a rule for some apps with a rule of a later layer (`overrides: <id>` and a reason) or list the rules that apply with
`python3 scripts/rules.py list --app <app> --skill <skill>`. See `docs/rules.md`.
