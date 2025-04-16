from flask import Flask, render_template, request, jsonify, redirect, url_for
import os
import sqlite3
import logging
from database import init_db, load_dataset, get_datasets, get_dataset_data, calculate_peaks

# логгинг
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

init_db()


@app.route('/')
def index():
    datasets = get_datasets()
    return render_template('index.html', datasets=datasets)


@app.route('/dataset/<int:dataset_id>')
def dataset(dataset_id):
    try:
        df = get_dataset_data(dataset_id)
        if df.empty:
            logger.error(f"Данные {dataset_id} не найдены")
            return "Данные не найдены", 404

        # вычисление статистики - но есть вопросы по пикам
        stats = {
            'mean': df[['emg1', 'emg2', 'emg3', 'emg4', 'angle']].mean().to_dict(),
            'max': df[['emg1', 'emg2', 'emg3', 'emg4', 'angle']].max().to_dict(),
            'peaks': calculate_peaks(df)  # сделать ее в датабэйзе
        }

        # данные для графика
        plot_data = {
            'timestamp': df['timestamp'].tolist(),
            'emg1': df['emg1'].tolist(),
            'emg2': df['emg2'].tolist(),
            'emg3': df['emg3'].tolist(),
            'emg4': df['emg4'].tolist(),
            'angle': df['angle'].tolist()
        }

        datasets = get_datasets()
        return render_template('dataset.html', dataset_id=dataset_id, stats=stats, plot_data=plot_data,
                               datasets=datasets)

    except Exception as e:
        logger.error(f"Ошибка отображения данных {dataset_id}: {str(e)}")
        return f"Ошибка: {str(e)}", 500


@app.route('/add_dataset', methods=['GET', 'POST'])
def add_dataset():
    if request.method == 'POST':
        try:
            file = request.files['file']
            dataset_name = request.form['dataset_name']
            if file and dataset_name:
                if not file.filename.endswith('.xlsx'):
                    logger.error("Неверный формат. Возможен только xls")
                    return "Загрузите файл xls", 400

                file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
                file.save(file_path)
                dataset_id = load_dataset(file_path, dataset_name)
                logger.info(f"Перенеправление на данные {dataset_id}")
                return redirect(url_for('dataset', dataset_id=dataset_id))
            else:
                logger.error("Файл не загружен")
                return "Файл не загружен", 400
        except Exception as e:
            logger.error(f"Ошибка добавления данных: {str(e)}")
            return f"Ошибка: {str(e)}", 500
    return render_template('add_dataset.html')


# REST API для изменения загруженного набора данных
@app.route('/api/dataset/<int:dataset_id>', methods=['PUT'])
def update_dataset(dataset_id):
    try:
        if 'file' not in request.files:
            logger.error("В API запросе  не указан файл")
            return jsonify({'ошибка': 'не указан файл'}), 400

        file = request.files['file']
        dataset_name = request.form.get('dataset_name', f'Dataset {dataset_id}')

        if not file.filename.endswith('.xlsx'):
            logger.error("Неверный формат файла")
            return jsonify({'ошибка': 'Неверный формат файла'}), 400

        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)

        # Удаляем старые данные
        conn = sqlite3.connect('data.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM data WHERE dataset_id = ?', (dataset_id,))
        cursor.execute('UPDATE datasets SET name = ?, file_path = ? WHERE id = ?',
                       (dataset_name, file_path, dataset_id))
        conn.commit()
        conn.close()

        # Загружаем новые данные
        load_dataset(file_path, dataset_name)
        logger.info(f"Данные {dataset_id} обновлены")
        return jsonify({'сообщение': 'данные обновлены', 'id': dataset_id})

    except Exception as e:
        logger.error(f"ошибка обновления: {str(e)}")
        return jsonify({'ошибка': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
