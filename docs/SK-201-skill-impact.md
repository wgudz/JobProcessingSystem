
# SK-201 — wpływ Skill `job-regression-triage`

Skill `job-regression-triage` wprowadza stałą procedurę analizy pojedynczej
regresji w JobProcessingSystem.

Agent rozpoczyna od sprawdzenia stanu repozytorium i HEAD, następnie uruchamia
najmniejszy test związany ze zgłoszeniem, odczytuje źródło tego testu,
lokalizuje odpowiadającą implementację i sprawdza bieżące zmiany w kodzie.

Skill wymusza rozdzielenie faktów od hipotez. Samo znalezienie podejrzanej
instrukcji lub warunku w kodzie nie może być traktowane jako potwierdzona
przyczyna regresji. Wnioski muszą być powiązane z konkretnymi dowodami
`EVID-*`.

Dla incydentu SK201-QUEUE focused test `thread_safe_queue_test` przeszedł,
dlatego zgłoszonego objawu nie odtworzono. Zebrane dowody nie uzasadniały
zmiany kodu źródłowego.

Dla incydentu SK201-STATS focused test `statistics_test` również przeszedł.
Zgłoszonego problemu z końcowymi licznikami nie odtworzono i nie znaleziono
dowodów uzasadniających poprawkę źródła.

W obu przypadkach agent zakończył analizę bez przypisywania niepotwierdzonej
przyczyny. Raporty zawierają wymagane sekcje: Facts, Hypotheses, Minimal fix,
Test plan, Risks oraz Final result.

Selective test służy do reprodukcji i diagnostyki. Jeśli poprawka C++ zostanie
faktycznie zastosowana, przed uznaniem jej za zweryfikowaną wymagane jest
uruchomienie pełnego CTest.
