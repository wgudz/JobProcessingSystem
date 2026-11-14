# JobProcessingSystem

## AI Agent CLI

Agent może analizować konkretny incydent przekazany przez plik JSON.

### Format zgłoszenia

Przykład:

```json
{
  "title": "Worker nie kończy pracy poprawnie",
  "symptoms": "worker_test zawiesza się podczas zamykania systemu",
  "expected": "Worker powinien zakończyć pracę i join() powinien wrócić",
  "suspected_tests": [
    "worker_test"
  ]
}
```

Pola:

- `title` — wymagany, niepusty tekst,
- `symptoms` — wymagany, niepusty tekst opisujący zaobserwowany problem,
- `expected` — wymagany, niepusty tekst opisujący oczekiwane zachowanie,
- `suspected_tests` — opcjonalna lista nazw testów.

Plik zgłoszenia zawiera dane opisujące incydent. Nie należy umieszczać w nim poleceń systemowych ani komend przeznaczonych do wykonania przez model.

`--issue-id` oraz `--issue-file` muszą być używane razem.

Plik wskazany przez `--issue-file` musi znajdować się wewnątrz `--workspace`.

### Przykłady użycia

Analiza zgłoszenia bez uruchamiania builda i testów:

```powershell
python -m agentlab `
  --provider mock `
  --issue-id BUG-001 `
  --issue-file issues\BUG-001.json `
  --report reports\bug001.md
```

Analiza z możliwością uruchomienia CMake i CTest dla zaufanego kodu:

```powershell
python -m agentlab `
  --provider ollama `
  --model qwen3:4b `
  --issue-id BUG-001 `
  --issue-file issues\BUG-001.json `
  --allow-exec `
  --report reports\bug001.md `
  --output-json reports\bug001.json
```

Analiza z wybranym Skill:

```powershell
python -m agentlab `
  --provider ollama `
  --model qwen3:4b `
  --issue-id BUG-001 `
  --issue-file issues\BUG-001.json `
  --skill job-processing-triage `
  --allow-exec `
  --report reports\bug001.md
```

### Kody zakończenia

- `0` — agent zakończył analizę i utworzył raport,
- kod różny od `0` — agent nie mógł poprawnie przeprowadzić analizy, np. z powodu błędnych parametrów, niepoprawnego zgłoszenia lub błędu providera.

Znalezienie błędu w kodzie C++ nie jest błędem wykonania CLI. Jeżeli agent poprawnie zakończył diagnozę i wskazał problem w projekcie, CLI nadal może zakończyć się kodem `0`.