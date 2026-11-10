
# AI Runbook

## OPS-002 — MOCK vs Ollama

### MOCK

Tryb MOCK służy do sprawdzenia mechaniki agenta bez używania modelu językowego.

Uruchomienie:

```powershell
python -m agentlab --provider mock --allow-exec --report reports\ops002-mock.md
```

W sprawdzonym przebiegu MockProvider wykonał deterministyczną sekwencję 8 narzędzi:

1. `list_files`
2. `run_cmake_configure`
3. `run_cmake_build`
4. `run_ctest`
5. `git_diff`
6. `read_file`
7. `read_file`
8. `read_file`

Kolejność wynika bezpośrednio z kodu `MockProvider` w `agentlab/providers.py`. MOCK nie analizuje kodu za pomocą AI i nie może potwierdzić jakości diagnozy modelu.

### Ollama

Model lokalny:

`qwen3:4b`

Uruchomienie:

```powershell
python -m agentlab --provider ollama --model qwen3:4b --allow-exec --report reports\ops002-ollama.md
```

W sprawdzonym przebiegu model sam zdecydował o wykonaniu tylko 3 narzędzi:

1. `list_files`
2. `list_ctest`
3. `run_ctest`

Agent zakończył analizę bez wywołania wszystkich dostępnych narzędzi.

CTest zwrócił `exit_code = 0` i wszystkie 11 testów przeszło. Jest to dowód pochodzący z rzeczywistego narzędzia, a nie z tekstu wygenerowanego przez model.

Końcowe wnioski, takie jak „production-ready”, „no concurrency issues” lub podobne oceny, są tekstem wygenerowanym przez model i nie powinny być traktowane jako równoważne z dowodem z CTest.

### Błąd providera

Sprawdzono również uruchomienie z nieistniejącym modelem:

```powershell
python -m agentlab --provider ollama --model qwen3:model-does-not-exist --allow-exec --report reports\ops002-ollama-error.md
```

Wynik:

```text
ERROR: Ollama HTTP 404: check model name and ollama list
```

Jest to błąd konfiguracji/provider Ollama. Nie jest to błąd kompilacji, CTest ani systemu C++.

### Wniosek

MOCK potwierdza działanie infrastruktury i deterministycznej pętli narzędzi, ale nie testuje jakości diagnozy AI.

Ollama wykorzystuje rzeczywisty model językowy, który sam wybiera narzędzia i generuje wnioski na podstawie zebranych dowodów.

Dlatego poprawny przebieg MOCK nie zastępuje testu z rzeczywistym modelem.
