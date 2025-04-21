import logging
import os
import time
from flask import Flask, jsonify, redirect, render_template, request, url_for

from database import (calculate_peaks, get_dataset_data, get_datasets, init_db,
                      load_dataset, update_dataset_data)

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
                #  переименуем файл чтобы не сохранялся один и тот же
                upload_time = int(time.time())
                name, ext = os.path.splitext(file.filename)
                new_filename = f"{name}_{upload_time}{ext}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
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
        if 'file' not in request.files or 'dataset_name' not in request.form:
            return jsonify({'ошибка': 'файл и название необходимы'}), 400
        file = request.files['file']
        dataset_name = request.form['dataset_name']
        if not file.filename.endswith('.xlsx'):
            return jsonify({'ошибка': 'загрузите excel файл'}), 400

        #  переименуем файл чтобы не сохранялся один и тот же
        upload_time = int(time.time())
        name, ext = os.path.splitext(file.filename)
        new_filename = f"{name}_{upload_time}{ext}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
        file.save(file_path)
        update_dataset_data(dataset_id, file_path, dataset_name)
        logger.info(f"Данные {dataset_id} обновлены")
        return jsonify({'сообщение': 'данные успешно обновлены'}), 200
    except ValueError as e:
        logger.error(f"ошибка обновления данных {dataset_id}: {str(e)}")
        return jsonify({'ошибка': str(e)}), 400
    except Exception as e:
        logger.error(f"ошибка обновления данных {dataset_id}: {str(e)}")
        return jsonify({'ошибка': 'ошибка на сервере'}), 500


if __name__ == '__main__':
    app.run(debug=True)
