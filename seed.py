"""Создание новой базы: 5 datasets, 5 models, 20 experiments."""

import argparse
from pathlib import Path

from db import DBError, MiniDB


def seed(directory):
    path = Path(directory)
    if path.exists() and any(path.iterdir()):
        raise DBError("Каталог не пуст. Для тестовых данных укажите новый каталог")
    db = MiniDB(path)
    db.create_table("datasets", {"id": "INT", "name": "STRING", "task": "STRING", "size": "INT"}, "id")
    db.create_table("models", {"id": "INT", "name": "STRING", "version": "STRING"}, "id")
    db.create_table("experiments", {
        "id": "INT", "dataset_id": "INT", "model_id": "INT",
        "accuracy": "FLOAT", "status": "STRING",
    }, "id", {"dataset_id": ("datasets", "id"), "model_id": ("models", "id")})
    datasets = [
        ("MNIST", "classification", 70000),
        ("CIFAR-10", "classification", 60000),
        ("Iris", "classification", 150),
        ("Fashion-MNIST", "classification", 70000),
        ("IMDB", "sentiment", 50000),
    ]
    for name, task, size in datasets:
        db.insert("datasets", {"name": name, "task": task, "size": size})
    for name, version in [("MLP", "1.0"), ("CNN", "1.0"), ("RandomForest", "2.0"),
                          ("ResNet", "18"), ("Transformer", "1.1")]:
        db.insert("models", {"name": name, "version": version})
    for index in range(20):
        db.insert("experiments", {
            "dataset_id": index % 5 + 1, "model_id": (index // 5 + index) % 5 + 1,
            "accuracy": round(0.72 + index * 0.01, 2),
            "status": "running" if index % 4 == 0 else "completed",
        })
    return db


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data")
    args = parser.parse_args()
    try:
        seed(args.db)
        print("Созданы datasets: 5, models: 5, experiments: 20. Данные учебные.")
    except (DBError, OSError) as error:
        parser.exit(1, f"Ошибка: {error}\n")
