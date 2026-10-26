"""Собственные CLI-команды MiniDB, без SQL-парсера."""

import argparse
import csv
import shlex

from db import DBError, MiniDB


HELP = """Команды (имена полей и таблиц чувствительны к регистру):
  create ИМЯ поле:ТИП ... pk=поле [fk=поле:таблица.ключ ...]
  insert ТАБЛИЦА поле=значение ...
  select ТАБЛИЦА [columns=поле1,поле2] [where поле оператор значение]
  update ТАБЛИЦА поле=значение ... [where поле оператор значение]
  delete ТАБЛИЦА [where поле оператор значение]
  tables | schema ТАБЛИЦА | help | exit
Типы: INT, STRING, FLOAT. Операторы: = != > < >= <=.
Значения с пробелами: name="Набор данных".
UPDATE/DELETE без where действуют на ВСЕ строки таблицы."""


def assignments(tokens):
    result = {}
    for token in tokens:
        if "=" not in token:
            raise DBError(f"Ожидается поле=значение: {token}")
        field, value = token.split("=", 1)
        if field in result:
            raise DBError(f"Поле {field} указано дважды")
        result[field] = value
    if not result:
        raise DBError("Нужны значения полей")
    return result


def split_where(tokens):
    if "where" not in tokens:
        return tokens, None
    position = tokens.index("where")
    if len(tokens[position + 1:]) != 3:
        raise DBError("После where нужны поле, оператор и значение")
    return tokens[:position], tuple(tokens[position + 1:])


def print_rows(rows):
    if not rows:
        print("Строк: 0")
        return
    columns = list(rows[0])
    display = [[str(row[field]).replace("\n", "\\n").replace("\t", "\\t")
                for field in columns] for row in rows]
    widths = [max(len(field), *(len(row[i]) for row in display))
              for i, field in enumerate(columns)]
    for row in [columns] + display:
        print(" | ".join(value.ljust(width) for value, width in zip(row, widths)))
    print(f"Строк: {len(rows)}")


def execute(db, line):
    tokens = shlex.split(line)
    if not tokens:
        return
    command = tokens[0].lower()
    args = tokens[1:]
    if command == "help" and not args:
        print(HELP)
        return
    if command == "tables" and not args:
        print(", ".join(db.tables()) or "Таблиц нет")
        return
    if not args:
        raise DBError("Нужно имя таблицы; справка: help")
    table, args = args[0], args[1:]
    if command == "create":
        fields, foreign_keys, primary_key = {}, {}, None
        for token in args:
            if token.startswith("pk="):
                if primary_key is not None:
                    raise DBError("PRIMARY KEY указан дважды")
                primary_key = token[3:]
            elif token.startswith("fk="):
                field, reference = token[3:].split(":")
                parent, key = reference.split(".")
                if field in foreign_keys:
                    raise DBError(f"FK {field} указан дважды")
                foreign_keys[field] = (parent, key)
            else:
                field, kind = token.split(":")
                if field in fields:
                    raise DBError(f"Поле {field} указано дважды")
                fields[field] = kind.upper()
        db.create_table(table, fields, primary_key, foreign_keys)
        print(f"Таблица {table} создана")
    elif command == "schema" and not args:
        fields, key, foreign_keys = db.schema(table)
        for field, kind in fields.items():
            note = " PRIMARY KEY" if field == key else ""
            if field in foreign_keys:
                note += " FK " + ".".join(foreign_keys[field])
            print(f"{field}: {kind}{note}")
    elif command == "insert":
        print_rows([db.insert(table, assignments(args))])
    elif command in ("select", "update", "delete"):
        args, where = split_where(args)
        if command == "select":
            if args and (len(args) != 1 or not args[0].startswith("columns=")):
                raise DBError("SELECT: ожидается columns=поле1,поле2 или where")
            columns = args[0][8:].split(",") if args else None
            print_rows(db.select(table, columns, where))
        elif command == "update":
            print(f"Обновлено: {db.update(table, assignments(args), where)}")
        else:
            if args:
                raise DBError("DELETE: ожидается where или конец команды")
            print(f"Удалено: {db.delete(table, where)}")
    else:
        raise DBError("Неизвестная команда или лишние аргументы; справка: help")


def main():
    parser = argparse.ArgumentParser(description="MiniDB: собственная файловая мини-СУБД")
    parser.add_argument("--db", default="data", help="Каталог базы (по умолчанию data)")
    options = parser.parse_args()
    try:
        db = MiniDB(options.db)
    except OSError as error:
        print(f"Ошибка открытия базы: {error}")
        return 1
    print(f"MiniDB | база: {db.directory} | справка: help")
    while True:
        try:
            line = input("minidb> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if line.strip().lower() == "exit":
            break
        try:
            execute(db, line)
        except (DBError, OSError, ValueError, csv.Error) as error:
            print(f"Ошибка: {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
