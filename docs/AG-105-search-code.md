
# AG-105 — search_code

`search_code` służy do wyszukiwania symbolu lub frazy bez
przekazywania modelowi całych plików.

Argumenty:

- `query` — wymagany tekst,
- `extensions` — opcjonalna lista rozszerzeń,
- `max_files` — maksymalna liczba sprawdzonych plików,
- `max_matches` — maksymalna liczba wyników,
- `directory` — opcjonalnie `src`, `include`, `tests` lub `app`.

Narzędzie przeszukuje wyłącznie dozwolone katalogi projektu.

Nie przeszukuje `.git`, `build`, plików binarnych ani plików
z niedozwolonym rozszerzeniem.

Każdy wynik zawiera:

- względną ścieżkę,
- numer linii,
- krótki kontekst.

Wyniki są sortowane deterministycznie według ścieżki i kolejności
linii.

Brak dopasowania jest poprawnym wynikiem:

```json
{
  "query": "FakeSymbol",
  "matches": [],
  "count": 0
}
```
