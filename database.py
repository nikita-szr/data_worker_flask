import sqlite3
import pandas as pd
import os


def init_db():
    """Подключение и создание бд"""

    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS datasets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            file_path TEXT NOT NULL
        )
    ''')
    cursor.execute('''
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
    ''')
    conn.commit()
    conn.close()


def load_dataset(file_path, dataset_name):
    """Перенос данных из excel в таблицу бд"""

    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()

    # Сохраняем инфу о данных
    cursor.execute('INSERT INTO datasets (name, file_path) VALUES (?, ?)', (dataset_name, file_path))
    dataset_id = cursor.lastrowid

    df = pd.read_excel(file_path)

    # Сохраняем данные в таблицу data из excel файла
    for _, row in df.iterrows():
        cursor.execute('''
            INSERT INTO data (dataset_id, timestamp, emg1, emg2, emg3, emg4, angle)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (dataset_id, row['timestamp'], row['emg1'], row['emg2'], row['emg3'], row['emg4'], row['angle']))

    conn.commit()
    conn.close()
    return dataset_id


def get_datasets():
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, name FROM datasets')
    datasets = cursor.fetchall()
    conn.close()
    return datasets


def get_dataset_data(dataset_id):
    conn = sqlite3.connect('data.db')
    query = 'SELECT timestamp, emg1, emg2, emg3, emg4, angle FROM data WHERE dataset_id = ?'
    df = pd.read_sql_query(query, conn, params=(dataset_id,))
    conn.close()
    return df

