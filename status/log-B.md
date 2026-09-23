| Время | Кто | Сделано | Делаю | Блокер | ETA | Ветка@коммит |
|---|---|---|---|---|---|---|
| 15:09 | B | done: S01-S07 кроме S08 в main; green-1440; полный check зелёный | doing: S12 ui-wire; ждём патч тестов S01 для S08 | block: S08: 3 устаревших smoke-теста S01 | eta: 15:20 | main@5ca51ac |
| 15:10 | B | done: S01-S08 зелёные; в main s/contract,s/fixtures,s/ui-shell,s/parse,s/units,s/ui-upload,s/ui-report; origin/main 79 tests passed | doing: s/runs ждёт патч S01; S09-S13 не начаты | block: s/runs: 3 теста S01 test_contract_smoke несовместимы с реальным API; нужен патч владельца S01 или B | eta: 15:20 мерж-поезд волны 2 | main@b48e1af |
| 15:33 | B | done: S08 s/runs в main; S09-S13 зелёные; origin/main 92 tests passed | doing: Волна 3 готова к мерж-поезду: s/schemas,s/functions,s/matching,s/conflicts,s/ui-wire | block: - | eta: 16:00 мерж-поезд и mock demo | main@cff1615 |
| 15:53 | B | done: S08 s/runs +3031208, S11 s/conflicts +4989c1d; S09-S13 зелёные; main 92 tests passed | doing: К поезду 16:00 готовы s/schemas,s/functions,s/matching,s/conflicts,s/ui-wire и доп. s/runs | block: - | eta: 16:00 мерж-поезд и mock demo | main@2c20c21 |
