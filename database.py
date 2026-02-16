import logging
import sqlite3

import pandas as pd

# логгинг
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_db():
    """Подключение и создание бд"""
    conn = sqlite3.connect("data.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS datasets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            file_path TEXT NOT NULL
        )
    """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS data (
            dataset_id INTEGER,
            timestamp INTEGER,
            emg1 INTEGER,
            emg2 INTEGER,
            emg3 INTEGER,
            emg4 INTEGER,
            angle INTEGER,
            FOREIGN KEY (dataset_id) REFERENCES datasets(id)
        )
    """
    )
    conn.commit()
    conn.close()
    logger.info("бд создана")


def load_dataset(file_path, dataset_name):
    """Перенос данных из excel в таблицу бд"""
    try:
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()

        # Сохраняем инфу о данных
        cursor.execute(
            "INSERT INTO datasets (name, file_path) VALUES (?, ?)",
            (dataset_name, file_path),
        )
        dataset_id = cursor.lastrowid

        logger.info(f"Чтение excel файла: {file_path}")
        df = pd.read_excel(file_path)

        # Проверка на столбцы как в примере
        required_columns = ["timestamp", "emg1", "emg2", "emg3", "emg4", "angle"]
        if not all(col in df.columns for col in required_columns):
            logger.error(f"Есть не все столбцы. Найдены столбцы: {df.columns}")
            raise ValueError(
                "Должны быть столбцы: timestamp, emg1, emg2, emg3, emg4, angle"
            )

        for col in required_columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        if df[required_columns].isnull().any().any():
            logger.error("Найдены значения NaN после конвертации")
            raise ValueError(
                "Проверьте файл, некоторые значения невозомжно перевести в числа"
            )

        # Сохраняем данные в таблицу data из excel файла
        for _, row in df.iterrows():
            cursor.execute(
                """
                INSERT INTO data (dataset_id, timestamp, emg1, emg2, emg3, emg4, angle)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    dataset_id,
                    int(row["timestamp"]),
                    int(row["emg1"]),
                    int(row["emg2"]),
                    int(row["emg3"]),
                    int(row["emg4"]),
                    int(row["angle"]),
                ),
            )

        conn.commit()
        logger.info(f"Данные {dataset_name} загружены с id: {dataset_id}")
        return dataset_id

    except Exception as e:
        logger.error(f"Ошибка: {str(e)}")
        conn.rollback()
        raise
    finally:
        conn.close()


def get_datasets():
    conn = sqlite3.connect("data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM datasets")
    datasets = cursor.fetchall()
    conn.close()
    return datasets


def get_dataset_info(dataset_id: int):
    """Возвращает метаданные датасета (id, name, file_path) или None."""
    conn = sqlite3.connect("data.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, file_path FROM datasets WHERE id = ?", (dataset_id,)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {"id": row[0], "name": row[1], "file_path": row[2]}


def get_dataset_data(dataset_id):
    conn = sqlite3.connect("data.db")
    query = (
        "SELECT timestamp, emg1, emg2, emg3, emg4, angle FROM data WHERE dataset_id = ?"
    )
    df = pd.read_sql_query(query, conn, params=(dataset_id,))
    conn.close()
    # Проверка и преобразование данных
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna()
    if df.empty:
        logger.error(f"Неверные данные {dataset_id} после очистки")
        raise ValueError(f"Неверные данные {dataset_id}")
    return df


def calculate_peaks(df):
    """Считает пиковые значения"""
    peaks = 0
    min_angle = float("inf")
    for angle in df["angle"]:
        if angle < min_angle:
            min_angle = angle
        if angle > min_angle + 20:
            peaks += 1
            min_angle = angle
    return peaks


def update_dataset_data(dataset_id, file_path, dataset_name):
    """
    Обновляет существующий датасет:
    - проверяет что dataset_id существует
    - удаляет старые строки из data
    - обновляет name/file_path в datasets
    - валидирует и загружает новые строки из excel
    """
    conn = sqlite3.connect("data.db")
    cursor = conn.cursor()

    try:
        # проверка, существует ли dataset_id
        cursor.execute("SELECT id FROM datasets WHERE id = ?", (dataset_id,))
        if not cursor.fetchone():
            logger.error(f"Данные {dataset_id} не найдены в таблице datasets")
            raise ValueError(f"данные {dataset_id} не найдены")

        # удаление старых данных для dataset_id
        cursor.execute("DELETE FROM data WHERE dataset_id = ?", (dataset_id,))

        # обновление метаданных
        cursor.execute(
            "UPDATE datasets SET name = ?, file_path = ? WHERE id = ?",
            (dataset_name, file_path, dataset_id),
        )

        # чтение и валидация excel
        logger.info(f"Чтение excel файла: {file_path}")
        df = pd.read_excel(file_path)
        logger.info(f"столбцы в файле: {list(df.columns)}")

        required_columns = ["timestamp", "emg1", "emg2", "emg3", "emg4", "angle"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            logger.error(f"Не хватает столбцов: {missing_columns}")
            raise ValueError(f"Не хватает столбцов: {missing_columns}")

        # конвертация в числа
        for col in required_columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            if df[col].isna().all():
                logger.error(f"столбец {col} не содержит чисел")
                raise ValueError(f"столбец {col} не содержит чисел")

        df = df.dropna(subset=required_columns)
        if df.empty:
            logger.error("Нет данных после обработки файла")
            raise ValueError("Все строки пустые/NaN после обработки файла")

        # вставка строк
        insert_sql = (
            "INSERT INTO data (dataset_id, timestamp, emg1, emg2, emg3, emg4, angle) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)"
        )
        for _, row in df.iterrows():
            cursor.execute(
                insert_sql,
                (
                    dataset_id,
                    int(row["timestamp"]),
                    int(row["emg1"]),
                    int(row["emg2"]),
                    int(row["emg3"]),
                    int(row["emg4"]),
                    int(row["angle"]),
                ),
            )

        conn.commit()
        logger.info(f"Данные {dataset_id} обновлены в кол-ве {len(df)} строк")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
