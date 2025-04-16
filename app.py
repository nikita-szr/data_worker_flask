from flask import Flask, render_template, request, jsonify, redirect, url_for
import os
import sqlite3
from database import init_db, load_dataset, get_datasets, get_dataset_data, calculate_peaks


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

init_db()


@app.route('/')
def index():
    datasets = get_datasets()
    return render_template('index.html', datasets=datasets)


@app.route('/dataset/<int:dataset_id>')
def dataset(dataset_id):
    df = get_dataset_data(dataset_id)
    if df.empty:
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
    return render_template('dataset.html', dataset_id=dataset_id, stats=stats, plot_data=plot_data, datasets=datasets)


@app.route('/add_dataset', methods=['GET', 'POST'])
def add_dataset():
    if request.method == 'POST':
        file = request.files['file']
        dataset_name = request.form['dataset_name']
        if file and dataset_name:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(file_path)
            dataset_id = load_dataset(file_path, dataset_name)
            return redirect(url_for('dataset', dataset_id=dataset_id))
    return render_template('add_dataset.html')


# REST API для изменения загруженного набора данных
@app.route('/api/dataset/<int:dataset_id>', methods=['PUT'])
def update_dataset(dataset_id):
    if 'file' not in request.files:
        return jsonify({'error': 'Файла нет'}), 400

    file = request.files['file']
    dataset_name = request.form.get('dataset_name', f'Dataset {dataset_id}')
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)

    # Удаляем старые данные
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM data WHERE dataset_id = ?', (dataset_id,))
    cursor.execute('UPDATE datasets SET name = ?, file_path = ? WHERE id = ?', (dataset_name, file_path, dataset_id))
    conn.commit()
    conn.close()

    # Загружаем новые данные
    load_dataset(file_path, dataset_name)
    return jsonify({'message': 'Dataset updated', 'dataset_id': dataset_id})


if __name__ == '__main__':
    app.run(debug=True)
