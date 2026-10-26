"""Учебная файловая MiniDB. Только стандартная библиотека Python."""

import csv
import math
import operator
from pathlib import Path
import re


class DBError(Exception):
    """Ошибка схемы, запроса или ограничения целостности."""


class MiniDB:
    TYPES = {"INT", "STRING", "FLOAT"}
    OPERATORS = {
        "=": operator.eq, "!=": operator.ne,
        ">": operator.gt, "<": operator.lt,
        ">=": operator.ge, "<=": operator.le,
    }

    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _name(value):
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
            raise DBError(f"Недопустимое имя: {value!r}")
        return value

    def _path(self, table, suffix):
        return self.directory / (self._name(table) + suffix)

    @staticmethod
    def _read_file(path):
        with path.open(encoding="utf-8", newline="") as stream:
            return list(csv.reader(stream, delimiter="\t", strict=True))

    @staticmethod
    def _write_file(path, rows):
        # Сначала пишем новый файл, затем заменяем старый целиком.
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="") as stream:
                csv.writer(stream, delimiter="\t", lineterminator="\n").writerows(rows)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    def tables(self):
        return sorted(path.stem for path in self.directory.glob("*.schema"))

    def schema(self, table):
        path = self._path(table, ".schema")
        if not path.exists():
            raise DBError(f"Таблица {table} не существует")
        records = self._read_file(path)
        if not records or records[0] != ["MINIDB", "1"]:
            raise DBError(f"Неверный формат схемы {table}")
        fields, foreign_keys, primary_key = {}, {}, None
        for record in records[1:]:
            if len(record) == 3 and record[0] == "FIELD":
                field, kind = record[1:]
                self._name(field)
                if field in fields or kind not in self.TYPES:
                    raise DBError(f"Неверное поле в схеме {table}")
                fields[field] = kind
            elif len(record) == 2 and record[0] == "PK" and primary_key is None:
                primary_key = record[1]
            elif len(record) == 4 and record[0] == "FK":
                field, parent, parent_field = record[1:]
                self._name(parent)
                self._name(parent_field)
                if field in foreign_keys:
                    raise DBError(f"Повтор FK в схеме {table}")
                foreign_keys[field] = (parent, parent_field)
            else:
                raise DBError(f"Неверная строка схемы {table}")
        if not fields or fields.get(primary_key) != "INT":
            raise DBError("PRIMARY KEY должен быть полем INT")
        if any(field not in fields for field in foreign_keys):
            raise DBError(f"Неизвестное поле FK в схеме {table}")
        return fields, primary_key, foreign_keys

    def create_table(self, table, fields, primary_key, foreign_keys=None):
        schema_path = self._path(table, ".schema")
        data_path = self._path(table, ".data")
        if schema_path.exists() or data_path.exists():
            raise DBError(f"Таблица {table} уже существует")
        if not fields:
            raise DBError("Нужен хотя бы один столбец")
        for field, kind in fields.items():
            self._name(field)
            if kind not in self.TYPES:
                raise DBError(f"Неизвестный тип {kind}")
        if fields.get(primary_key) != "INT":
            raise DBError("PRIMARY KEY должен быть полем INT")
        foreign_keys = foreign_keys or {}
        for field, (parent, parent_field) in foreign_keys.items():
            parent_fields, parent_pk, _ = self.schema(parent)
            if field not in fields or parent_field != parent_pk:
                raise DBError("FK должен ссылаться на PRIMARY KEY существующей таблицы")
            if fields[field] != parent_fields[parent_field]:
                raise DBError("Типы FK и PRIMARY KEY должны совпадать")
        records = [["MINIDB", "1"], ["PK", primary_key]]
        records += [["FIELD", field, kind] for field, kind in fields.items()]
        records += [["FK", field, parent, key]
                    for field, (parent, key) in foreign_keys.items()]
        self._write_file(data_path, [])
        self._write_file(schema_path, records)

    @staticmethod
    def _convert(value, kind):
        if kind == "STRING" and isinstance(value, str):
            return value
        if kind == "INT":
            if type(value) is int:
                return value
            if isinstance(value, str) and re.fullmatch(r"[+-]?[0-9]+", value):
                return int(value)
        if kind == "FLOAT" and type(value) in (str, int, float):
            try:
                number = float(value)
                if math.isfinite(number):
                    return number
            except (ValueError, OverflowError):
                pass
        raise DBError(f"Значение {value!r} не соответствует типу {kind}")

    def _rows(self, table, fields):
        path = self._path(table, ".data")
        if not path.exists():
            raise DBError(f"Файл данных {table} отсутствует")
        result = []
        for values in self._read_file(path):
            if len(values) != len(fields):
                raise DBError(f"Повреждена строка таблицы {table}")
            result.append({field: self._convert(value, kind)
                           for (field, kind), value in zip(fields.items(), values)})
        return result

    def _condition(self, fields, where):
        if where is None:
            return lambda row: True
        if len(where) != 3:
            raise DBError("Условие: поле оператор значение")
        field, comparison, value = where
        if field not in fields:
            raise DBError(f"Неизвестное поле {field}")
        if comparison not in self.OPERATORS:
            raise DBError(f"Неизвестный оператор {comparison}")
        value = self._convert(value, fields[field])
        return lambda row: self.OPERATORS[comparison](row[field], value)

    def _validate(self, table, rows, schema):
        fields, primary_key, foreign_keys = schema
        seen = set()
        for row in rows:
            key = row[primary_key]
            if key in seen:
                raise DBError(f"Дубликат PRIMARY KEY: {primary_key}={key}")
            seen.add(key)
        for field, (parent, key) in foreign_keys.items():
            parent_fields, _, _ = self.schema(parent)
            parent_rows = rows if parent == table else self._rows(parent, parent_fields)
            allowed = {row[key] for row in parent_rows}
            for row in rows:
                if row[field] not in allowed:
                    raise DBError(f"Нарушение FK: {table}.{field}={row[field]} "
                                  f"не найден в {parent}.{key}")
        # RESTRICT: изменение/удаление родительского ключа не создаёт висячих ссылок.
        for child in self.tables():
            if child == table:
                continue
            child_fields, _, child_fks = self.schema(child)
            for field, (parent, key) in child_fks.items():
                if parent == table:
                    allowed = {row[key] for row in rows}
                    if any(row[field] not in allowed for row in self._rows(child, child_fields)):
                        raise DBError(f"Нарушение FK: на {table}.{key} ссылается {child}.{field}")

    def _save(self, table, rows, schema):
        self._validate(table, rows, schema)
        fields = schema[0]
        self._write_file(self._path(table, ".data"),
                         [[row[field] for field in fields] for row in rows])

    def insert(self, table, values):
        schema = self.schema(table)
        fields, primary_key, _ = schema
        unknown = set(values) - fields.keys()
        if unknown:
            raise DBError(f"Неизвестные поля: {', '.join(sorted(unknown))}")
        rows = self._rows(table, fields)
        values = dict(values)
        if primary_key not in values:
            values[primary_key] = max((row[primary_key] for row in rows), default=0) + 1
        missing = fields.keys() - values.keys()
        if missing:
            raise DBError(f"Не заполнены поля: {', '.join(sorted(missing))}")
        row = {field: self._convert(values[field], kind) for field, kind in fields.items()}
        self._save(table, rows + [row], schema)
        return row

    def select(self, table, columns=None, where=None):
        fields, _, _ = self.schema(table)
        columns = list(fields) if columns is None else list(columns)
        if not columns or any(field not in fields for field in columns):
            raise DBError("SELECT: неизвестные или пустые столбцы")
        matches = self._condition(fields, where)
        return [{field: row[field] for field in columns}
                for row in self._rows(table, fields) if matches(row)]

    def update(self, table, values, where=None):
        schema = self.schema(table)
        fields = schema[0]
        if not values or any(field not in fields for field in values):
            raise DBError("UPDATE: неизвестные поля или нет новых значений")
        converted = {field: self._convert(value, fields[field]) for field, value in values.items()}
        matches = self._condition(fields, where)
        rows, count = self._rows(table, fields), 0
        for row in rows:
            if matches(row):
                row.update(converted)
                count += 1
        self._save(table, rows, schema)
        return count

    def delete(self, table, where=None):
        schema = self.schema(table)
        matches = self._condition(schema[0], where)
        rows = self._rows(table, schema[0])
        remaining = [row for row in rows if not matches(row)]
        self._save(table, remaining, schema)
        return len(rows) - len(remaining)
