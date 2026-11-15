
# AG-104 — Znormalizowany wynik narzędzia

Każde narzędzie zwraca wspólne pola:

- `tool`
- `arguments`
- `status`
- `exit_code`
- `stdout`
- `stderr`
- `duration_ms`
- `truncated`
- `error`

Dozwolone statusy:

- `OK` — operacja zakończona poprawnie,
- `COMMAND_FAILED` — polecenie zostało wykonane, ale zwróciło kod różny od 0,
- `DENIED` — wykonanie zostało zablokowane przez politykę uprawnień,
- `TIMEOUT` — przekroczono limit czasu,
- `NOT_FOUND` — nie znaleziono pliku lub programu,
- `INVALID_ARGUMENTS` — narzędzie lub argumenty są niepoprawne.

## Przykład sukcesu

```json
{
  "tool": "run_ctest",
  "arguments": {},
  "status": "OK",
  "exit_code": 0,
  "stdout": "100% tests passed",
  "stderr": "",
  "duration_ms": 120,
  "truncated": false,
  "error": ""
}
```
