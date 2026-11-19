
# AG-108 — Dziennik dowodów

Każdy wynik narzędzia otrzymuje identyfikator w kolejności wykonania:

- `EVID-001`
- `EVID-002`
- `EVID-003`

Dowód przechowuje:

- identyfikator,
- narzędzie,
- argumenty,
- status,
- kod wyjścia,
- czas wykonania,
- informację o obcięciu,
- błąd,
- stdout,
- stderr,
- SHA-256 wyniku.

Zablokowane narzędzie (`DENIED`) również jest dowodem.

## Metadane sesji

Dziennik zawiera:

- session ID,
- SHA repozytorium,
- provider,
- model,
- Skill,
- tryb `allow_exec`,
- wersję programu.

Dziennik innej sesji nie jest automatycznie nadpisywany.

## Przykład

```json
{
  "session": {
    "id": "example-session",
    "repo_sha": "example",
    "provider": "MockProvider",
    "model": "unknown",
    "skill": "job-processing-triage",
    "allow_exec": false,
    "program_version": "0.1"
  },
  "evidence": [
    {
      "id": "EVID-001",
      "tool": "list_files",
      "arguments": {},
      "status": "OK",
      "exit_code": null,
      "duration_ms": 1,
      "truncated": false
    }
  ]
}
```
