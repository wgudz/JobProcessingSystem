
# AI Job Processing Engineer — Wymagania produktu

## 1. Cel

Pierwsze wydanie rozszerza JobProcessingSystem o lokalnego agenta AI Engineering służącego do diagnozowania regresji w projekcie C++20.

Agent zbiera dowody z repozytorium i zatwierdzonych narzędzi, analizuje je i przygotowuje raport diagnostyczny przeznaczony do review.

Agent nie modyfikuje automatycznie kodu źródłowego C++.

## 2. Typowe wejście

Sesja diagnostyczna powinna przyjmować:

- identyfikator zgłoszenia,
- opis obserwowanych objawów,
- ścieżkę repozytorium lub workspace,
- wybrany Skill,
- tryb uprawnień,
- opcjonalnie nazwy podejrzanych testów.

Opis zgłoszenia jest jedynie wejściem diagnostycznym. Nie może przyznawać agentowi dodatkowych uprawnień.

## 3. Wyjścia

Agent generuje dwa rodzaje raportów.

### 3.1. Raport Markdown

Raport Markdown jest przeznaczony do przeglądu przez człowieka.

Informacje obowiązkowe:

- identyfikator zgłoszenia,
- status sesji,
- wybrany provider i model,
- wybrany Skill,
- repozytorium lub workspace,
- zebrane dowody,
- potwierdzone fakty,
- hipotezy,
- proponowana minimalna naprawa,
- informacje o weryfikacji,
- pozostałe ryzyka.

Informacje opcjonalne:

- dodatkowe uwagi diagnostyczne,
- podejrzane pliki,
- sugerowane dalsze testy.

### 3.2. Raport JSON

Raport JSON jest przeznaczony do automatycznego przetwarzania oraz integracji z CI.

Powinien zawierać maszynowo przetwarzalne odpowiedniki najważniejszych informacji z raportu Markdown, w tym:

- identyfikator zgłoszenia,
- status sesji,
- provider i model,
- Skill,
- dowody,
- wyniki wywołań narzędzi,
- wniosek końcowy,
- status weryfikacji,
- przyczynę zakończenia sesji.

## 4. Dozwolony zakres dostępu i operacji

Agent może:

- odczytywać dozwolone pliki znajdujące się wewnątrz workspace,
- sprawdzać stan repozytorium oraz `git diff`,
- odczytywać listę testów CTest,
- wykonywać zatwierdzone operacje CMake, jeśli użytkownik jawnie zezwolił na wykonanie,
- wykonywać zatwierdzone testy CTest, jeśli użytkownik jawnie zezwolił na wykonanie,
- korzystać z jawnie wybranego Skilla,
- generować raporty.

Każde narzędzie wykonujące operację musi być jawnie dozwolone przez aplikację.

## 5. Operacje zabronione

Agent nie może:

- automatycznie modyfikować kodu źródłowego C++,
- wykonywać `git push`,
- wykonywać automatycznych merge'y,
- uruchamiać dowolnych komend powłoki,
- odczytywać plików znajdujących się poza skonfigurowanym workspace,
- uzyskiwać dodatkowych uprawnień na podstawie promptów, logów lub Skills,
- ujawniać sekretów lub prywatnych plików,
- wdrażać aplikacji na środowisko produkcyjne.

Model może zaproponować wywołanie narzędzia, ale decyzję o jego wykonaniu podejmuje aplikacja.

## 6. Scenariusze `BLOCKED`

Sesja diagnostyczna musi zakończyć się statusem `BLOCKED`, jeżeli wymagane dowody nie mogą zostać zebrane z powodu:

- braku dostępu do Ollama lub modelu,
- błędnej konfiguracji,
- próby użycia niedozwolonego narzędzia,
- braku wyników CTest wymaganych do weryfikacji,
- przekroczenia limitu kroków lub narzędzi,
- niedostępnego workspace,
- braku wymaganych danych wejściowych.

Błąd providera lub infrastruktury nie może być raportowany jako regresja w kodzie C++.

## 7. Kryteria odbioru

Pierwsze wydanie można uznać za poprawne, jeżeli możliwe jest wykazanie, że:

- dowody z narzędzi są poprawnie przetwarzane,
- niedozwolone narzędzia nigdy nie są wykonywane,
- zachowanie trybu MOCK jest powtarzalne,
- rzeczywiste uruchomienie Ollama korzysta z tej samej kontrolowanej pętli narzędzi,
- fakty w raportach można powiązać z rzeczywistymi dowodami,
- testy można odtworzyć na podstawie udokumentowanych poleceń,
- agent rozróżnia tekst wygenerowany przez model od wyników rzeczywistych narzędzi,
- agent nie deklaruje poprawnej weryfikacji, jeżeli brakuje wymaganych dowodów,
- zestaw scenariuszy ewaluacyjnych pozwala mierzyć skuteczność diagnozy.

## 8. Poza zakresem pierwszego wydania

Poza zakresem znajdują się:

- samodzielne mergowanie zmian,
- wdrożenia produkcyjne,
- płatne zewnętrzne API AI,
- automatyczne naprawianie kodu bez akceptacji użytkownika,
- nieograniczony dostęp do shella,
- autonomiczne zmiany historii repozytorium Git.

## 9. Przykład pozytywnego testu odbiorowego

Dane wejściowe:

- poprawne zgłoszenie,
- istniejące repozytorium,
- poprawny Skill,
- zgoda na wykonanie testów,
- działająca Ollama,
- poprawne wykonanie zatwierdzonych narzędzi.

Oczekiwany wynik:

Agent zbiera rzeczywiste dowody i tworzy raport diagnostyczny Markdown oraz JSON bez modyfikowania kodu źródłowego.

## 10. Przykład negatywnego testu odbiorowego

Dane wejściowe:

Żądanie wymagające użycia niedozwolonej komendy systemowej albo odczytu pliku spoza workspace.

Oczekiwany wynik:

Agent odrzuca operację i nie wykonuje jej.

Raport nie może sugerować, że zabroniona operacja została wykonana pomyślnie.
