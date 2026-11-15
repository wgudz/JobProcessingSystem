
# AG-106 — Stan Git i identyfikacja zmian

`git_status` zwraca:

- nazwę bieżącej gałęzi,
- pełny identyfikator HEAD,
- stan katalogu roboczego.

Z `git status --porcelain=v1` zapisywane są wyłącznie:

- `index` — stan staging area,
- `worktree` — stan katalogu roboczego,
- `path` — ścieżka pliku.

`git_show` przyjmuje wyłącznie pełny 40-znakowy SHA commita.

Nie są akceptowane nazwy branchy, tagi, `HEAD`, opcje rozpoczynające
się od `-` ani nieznane commity.

Commit musi należeć do historii aktualnego HEAD.

Diff jest ograniczony do:

- `src`
- `include`
- `tests`
- `app`
- `CMakeLists.txt`

Żadne z narzędzi nie wykonuje `commit`, `checkout`, `switch`, `reset`,
`merge`, `rebase` ani `push`.

## Przykład raportu

```text
## Working tree change

- Branch: `feature/example`
- HEAD: `0123456789012345678901234567890123456789`
- Changed entries: `1`

## Commit change

- Commit: `1234567890123456789012345678901234567890`
- Compared with: `0123456789012345678901234567890123456789`
```
