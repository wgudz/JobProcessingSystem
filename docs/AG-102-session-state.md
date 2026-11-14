
# AG-102 — Maszyna stanów sesji

Agent używa sześciu stanów:

- `CREATED` — sesja została utworzona.
- `COLLECTING_EVIDENCE` — agent wywołuje narzędzia i zbiera dowody.
- `ANALYZING` — model zakończył zbieranie dowodów i przygotowuje wynik.
- `COMPLETED` — analiza zakończyła się poprawnie i istnieje końcowa odpowiedź oparta na dowodach.
- `BLOCKED` — analiza nie może być poprawnie zakończona, np. przez limit kroków, powtarzające się wywołania lub pustą odpowiedź.
- `FAILED` — wystąpił błąd techniczny, np. błąd providera.

Typowy przebieg:

`CREATED -> COLLECTING_EVIDENCE -> ANALYZING -> COMPLETED`

Nie należy przechodzić ze stanów końcowych `COMPLETED`, `BLOCKED` i `FAILED` do dalszych stanów.

## Zasady zakończenia

Osiągnięcie `--max-steps` kończy sesję jako `BLOCKED`, a nie `COMPLETED`.

Trzy kolejne identyczne wywołania tego samego narzędzia z takim samym wynikiem są traktowane jako brak nowej informacji i kończą sesję jako `BLOCKED`.

Brak końcowej odpowiedzi modelu również kończy sesję jako `BLOCKED`.

Błąd providera kończy sesję jako `FAILED`.

Niezerowy wynik CTest nie oznacza automatycznie błędu agenta. Może być dowodem regresji w badanym kodzie C++.

## Przykładowe zakończenia

### Poprawna analiza

Status: `COMPLETED`
Reason: `final_answer`

Agent zebrał dowody i utworzył końcową diagnozę.

### Przekroczony limit kroków

Status: `BLOCKED`
Reason: `max_steps_reached`

Agent nie zakończył pełnej diagnozy przed osiągnięciem limitu.

### Błąd providera

Status: `FAILED`
Reason: `provider_error`

Model lub provider nie był dostępny, więc diagnoza nie mogła zostać wykonana.
