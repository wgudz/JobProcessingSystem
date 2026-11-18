
# AG-107 — Selektywne testy CTest

Mapowanie modułów do testów znajduje się w:

`agentlab/test_map.json`

Przykładowe mapowanie:

- `thread_safe_queue` -> `thread_safe_queue_test`
- `statistics` -> `statistics_test`
- `worker_pool` -> `worker_pool_test`

`list_ctest` odczytuje rzeczywistą listę testów z CTest oraz
konfigurację builda.

`run_selected_tests` przyjmuje wyłącznie listę nazw testów.
Każda nazwa musi występować w wyniku `list_ctest`.

Model nie może przekazać własnych argumentów CTest, ścieżki programu
ani polecenia powłoki.

## Przebieg selektywny

```json
{
  "tool": "run_selected_tests",
  "arguments": {
    "tests": [
      "thread_safe_queue_test"
    ]
  }
}
```
