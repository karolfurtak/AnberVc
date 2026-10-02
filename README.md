# AnberVc

![CI](https://github.com/karolfurtak/AnberVc/actions/workflows/ci.yml/badge.svg)

**Dobór obrotów maszyny do średnicy narzędzia — w kieszeni.** SDL2-owa aplikacja
dla **Anbernic RG40XX V**, która dobiera najwyższe **bezpieczne** obroty wrzeciona
tak, by nie przekroczyć dopuszczalnej **prędkości skrawania v_c** (obwodowej) na
krawędzi narzędzia. Obsługuje **szlifowanie / cięcie** (tarcza), **wiercenie**
(wiertło) i **frezowanie** (frez). Pełnoekranowa, sterowana padem, bez klawiatury.

![AnberVc](AnberVc.png)

## Fizyka

Prędkość skrawania (obwodowa) na krawędzi narzędzia:

```
v_c = π · D · n / 60      [v_c] = m/s,   [D] = m,  [n] = obr/min
v_c = π · D · n / 1000    [v_c] = m/min, [D] = mm, [n] = obr/min
```

(oba zapisy są równoważne: `v_c[m/min] = 60 · v_c[m/s]`).

Dobór bezpiecznych obrotów — minimum z trzech ograniczeń:

```
n_bezp = min( v_c·60/(π·D),  obroty_znamionowe_narzędzia,  max_obroty_maszyny )
```

Rekomendowane jest **najwyższe** nastawienie `k`, którego `rpm_k ≤ n_bezp`
(najwyższa wydajność w granicy bezpieczeństwa). Nastawienia rozłożone są liniowo:

```
rpm_k = rpm_min + (k-1)·(rpm_max - rpm_min)/(N-1),   k = 1..N
```

### Przykład (domyślny preset — szlifierka kątowa)

Tarcza D = 125 mm, v_c = 80 m/s, szlifierka 3000–12000 obr/min (7 nastawień),
tarcza znamionowo 12500 obr/min:

```
n_bezp = min( 80·60/(π·0,125),  12500,  12000 )
       = min( 12222,  12500,  12000 ) = 12000 obr/min   (wiąże maszyna)
→ Nastawienie 7 = 12000 obr/min,  v_c = π·25 ≈ 78,5 m/s,  margines 1,8 %
```

## Możliwości

- Trzy operacje jednym modelem: **szlifowanie, wiercenie, frezowanie**
- Prędkość skrawania w **m/s** oraz **m/min** (przełączana; wiercenie/frezowanie
  podaje się w m/min, materiałozależnie: stal ~20–30, aluminium ~100–300)
- **Każdy parametr edytowalny**: średnica narzędzia, v_c + jednostka, zakres i
  liczba nastawień obrotów maszyny, obroty znamionowe narzędzia
- Presety operacji/materiału (szlifowanie / wiercenie / frezowanie)
- **Tabela wszystkich nastawień** z flagą bezpieczne/nie dla bieżącej średnicy
- Ostrzeżenia na czerwono (narzędzie za duże / przekroczenie limitu)
- Regulacja z **krokiem i szybkim krokiem** (model jak AnberPKM/AnberWM)
- **Raport PDF do druku (A4)** przyciskiem **R2** — wspólny silnik raportów serii
  (reportlab), zapis do `/mnt/data/anbervc_raporty/`
- Liczby z polskim separatorem dziesiętnym (przecinek), jednostki jawne
- **Persystencja** ostatnio użytych parametrów — `/mnt/data/anbervc_config.json`
  (przeżywa restart; uszkodzony/brak → domyślny preset bez crasha)
- Renderowanie SDL2 + PIL (wprost na framebufferze, bez X11)
- POWER wygasza ekran bez zamykania apki; **MENU/MODE zawsze** zwalnia pad
  (EVIOCGRAB 0) i oddaje ekran launcherowi — gwarancja przez `try/finally`

## Sterowanie

Pełna mapa: [KEYS.md](KEYS.md).

| Przycisk              | Akcja                                        |
|-----------------------|----------------------------------------------|
| D-pad ↑/↓             | wybór parametru                              |
| D-pad ←/→             | − / + wartość o bieżący krok                 |
| **L1/R1**, **L2/R2**  | szybki krok − / + (L2/R2 większy)            |
| **Y**                 | zmiana kroku (0.1 / 1 / 10 / 100 / 1000)     |
| **A**                 | reset zaznaczonego pola do presetu           |
| **X**                 | reset wszystkich pól do presetu              |
| **R2**                | generuj raport PDF do druku (A4)             |
| **MENU / MODE**       | wyjście                                      |
| **POWER**             | ekran off/on (apka działa dalej)             |

## Wymagania

- **Anbernic RG40XX V** (Allwinner H700, 640×480 LCD landscape)
- Python 3 z `pysdl2`, `Pillow`, `evdev`
- `PYSDL2_DLL_PATH=/usr/lib` (ustawiane przez launcher)

## Instalacja

Na konsoli (przez SSH lub terminal), jako root:

```bash
git clone https://github.com/karolfurtak/AnberVc.git
cd AnberVc
bash scripts/install.sh
```

Następnie uruchom **AnberVc** z App Center.

## Architektura

**Logika oddzielona od GUI** — cały dobór obrotów siedzi w pakiecie `vc_lib/`
(bez SDL), więc jest testowalny i uruchamialny w CI bez wyświetlacza.
`app/main.py` to tylko warstwa SDL2 (render + input evdev), `app/power_screen.py`
obsługuje wygaszanie ekranu (POWER). Raport PDF: `vc_lib/report.py` buduje treść
(czysta, testowalna) i woła wspólny silnik serii `vc_lib/raport_engine.py`
(reportlab) — ten sam mechanizm co AnberISA/AnberWM/AnberPKM.

## Testy / CI

```bash
python3 vc_lib/core.py     # self-test logiki (PASS/FAIL)
pytest -q tests/           # testy jednostkowe doboru (szlif + wiercenie + frezowanie + brzegi)
```

GitHub Actions (`.github/workflows/ci.yml`) przy każdym push/PR: AST parse + ruff
(realne bugi) + self-test + pytest + walidacja struktury GUI + shellcheck launcherów.

## Licencja

Copyright (c) 2026 Karol Furtak. **Wszelkie prawa zastrzeżone.** Użycie komercyjne, kopiowanie, rozpowszechnianie i modyfikowanie wyłącznie za pisemną zgodą autora — szczegóły w pliku [LICENSE](LICENSE).

---

Część rodziny narzędzi **Anber\*** dla RG40XX V:
[AnberHex](https://github.com/karolfurtak/AnberHex) ·
[AnberPKM](https://github.com/karolfurtak/AnberPKM) ·
[AnberISA](https://github.com/karolfurtak/AnberISA)
