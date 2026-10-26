# Лабораторная №1. MiniDB

Собственная файловая мини-СУБД для учёта датасетов, моделей и экспериментов.
Объём реализации соответствует требованиям уровня 8 баллов из `Lab1_MiniDB.pdf`.
Нужен Python 3.10 или новее

## Запуск

Открыть терминал в каталоге проекта:

```bash
python3 cli.py --db data
```

В Windows вместо `python3` можно использовать `py -3`.
В комплекте уже есть база: **5 datasets, 5 models, 20 experiments**.

Новая база с теми же тестовыми данными:

```bash
python3 seed.py --db demo_data
python3 cli.py --db demo_data
```

`seed.py` работает только с пустым или новым каталогом, существующую базу не стирает.
Чтобы создать пустую базу, достаточно запустить CLI с новым каталогом:

```bash
python3 cli.py --db empty_data
```

## CREATE TABLE и схема

Команды вводятся внутри MiniDB
В пустой базе таблицы создаются в таком порядке:

```text
create datasets id:INT name:STRING task:STRING size:INT pk=id
create models id:INT name:STRING version:STRING pk=id
create experiments id:INT dataset_id:INT model_id:INT accuracy:FLOAT status:STRING pk=id fk=dataset_id:datasets.id fk=model_id:models.id
tables
schema experiments
```

Можно создавать другие таблицы с теми же типами. Первичный ключ один, типа INT.
FK ссылается на PK уже созданной таблицы; типы полей должны совпадать.
Имена таблиц/полей: латинские буквы, цифры, `_`; первый символ не цифра.
Имена чувствительны к регистру. Все поля обязательны, NULL не поддерживается.
Строки с пробелами заключаются в кавычки: `name="Новый датасет"`.

## Сценарий проверки

Сначала создать `demo_data` командой выше, затем открыть её в CLI.
Команды выполняются последовательно на исходных данных 5/5/20.

```text
tables
schema experiments
insert datasets name="Новый датасет" task=classification size=1000
insert models name=TestModel version=1.0
insert experiments dataset_id=6 model_id=6 accuracy=0.93 status=running
select datasets
select experiments
select experiments columns=id,accuracy,status where accuracy >= 0.9
update experiments status=completed where id = 21
insert experiments dataset_id=6 model_id=6 accuracy=0.5 status=running
delete experiments where id = 22
insert experiments dataset_id=999 model_id=6 accuracy=0.7 status=running
insert datasets id=1 name=Duplicate task=classification size=100
insert datasets name=BadType task=classification size=wrong
delete datasets where id = 6
exit
```

Ожидается: новые dataset/model получают ID 6, experiment получает ID 21.
После UPDATE у него `status=completed`. Временный experiment 22 удаляется.
Последние четыре операции выдают ошибки: неверный FK, дубликат PK,
неверный INT, удаление dataset со связанным experiment. CLI продолжает работать.

Теперь **запустить программу заново**:

```bash
python3 cli.py --db demo_data
```

```text
select experiments where id = 21
select experiments where id = 22
select datasets where id = 6
exit
```

Запись 21 сохранилась со статусом `completed`, запись 22 отсутствует,
dataset 6 остался. Схема и FK также читаются с диска после перезапуска.
Итог демонстрационной базы: 6 datasets, 6 models, 21 experiment.

## Операции и ограничения

- CREATE TABLE: имя, поля, типы, PK и FK.
- INSERT: проверка полей и типов, уникальный PK. Если PK не передан,
  используется `max(существующие PK) + 1`, для пустой таблицы 1.
  После удаления максимального ID он может использоваться снова.
- SELECT: все или выбранные столбцы, одно условие с `=`, `!=`, `>`, `<`, `>=`, `<=`.
  INT/FLOAT сравниваются как числа, STRING - как строки с учётом регистра.
- UPDATE/DELETE: одно условие; без `where` затрагивают **все строки**.
- FK проверяется при INSERT и UPDATE. Удаление/изменение родительского PK
  запрещено, пока на него ссылаются дочерние записи (RESTRICT).
- Ошибки PK/FK/типов/полей не меняют данные. FLOAT принимает только конечные числа.
- `help` выводит синтаксис, `exit` завершает программу. Каждое успешное изменение данных сохраняется сразу.

## Архитектура и файлы

- `db.py` - создание схемы, чтение/запись, CRUD, типы, PK/FK, фильтрация.
- `cli.py` - разбор собственных команд через `shlex`, вывод, обработка ошибок.
- `seed.py` - создание трёх таблиц и фиксированных тестовых записей.
- `data/` - готовая база; на таблицу приходится `.schema` и `.data`.
- `schema.dbml` - описание схемы для импорта в dbdiagram.io.
- `report.pdf` - краткий отчёт на двух страницах со схемой PK/FK.

Схема хранится в UTF-8, разделитель - табуляция. Пример `datasets.schema`:

```text
MINIDB  1
PK      id
FIELD   id      INT
FIELD   name    STRING
FIELD   task    STRING
FIELD   size    INT
```

В `experiments.schema` дополнительно записаны строки
`FK<tab>dataset_id<tab>datasets<tab>id` и `FK<tab>model_id<tab>models<tab>id`.
Порядок FIELD определяет порядок значений в `.data`. Заголовка данных нет.
Каждая запись содержит значения полей в этом порядке. Кодирование - UTF-8,
разделитель - табуляция, кавычки/переносы строк экранирует стандартный модуль `csv`

При чтении строки преобразуются по схеме в `int`, `str`, `float`.
Операции читают таблицу в память. Перед записью проверяется весь результат;
после проверки создаётся временный файл, который заменяет `.data`

Пример программного интерфейса:

```python
from db import MiniDB

db = MiniDB("data")
rows = db.select("experiments", ["id", "accuracy"], ("accuracy", ">=", 0.9))
```

База рассчитана на один запущенный процесс и небольшие учебные таблицы.
Конкурентная запись, транзакции и восстановление после сбоя питания не реализованы.
Чтение/изменение таблицы требует полного прохода, поэтому поиск имеет сложность O(n).

## Проверка и отчёт

Проверены CRUD, все шесть сравнений, выбор столбцов, авто-ID, ошибки типов/PK/FK,
запрет удаления связанного родителя и сохранение после выхода и запуска
в отдельном процессе
