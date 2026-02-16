import logging
import os
from datetime import datetime

from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_cors import CORS

from database import (
    calculate_peaks,
    get_dataset_data,
    get_dataset_info,
    get_datasets,
    init_db,
    load_dataset,
    update_dataset_data,
)

# логгинг
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

init_db()


@app.route("/")
def index():
    datasets = get_datasets()
    return render_template("index.html", datasets=datasets)


@app.route("/dataset/<int:dataset_id>")
def dataset(dataset_id):
    try:
        df = get_dataset_data(dataset_id)
        if df.empty:
            logger.error(f"Данные {dataset_id} не найдены")
            return "Данные не найдены", 404

        # вычисление статистики
        stats = {
            "mean": df[["emg1", "emg2", "emg3", "emg4", "angle"]].mean().to_dict(),
            "max": df[["emg1", "emg2", "emg3", "emg4", "angle"]].max().to_dict(),
            "peaks": calculate_peaks(df),
        }

        # данные для графика
        plot_data = {
            "timestamp": df["timestamp"].tolist(),
            "emg1": df["emg1"].tolist(),
            "emg2": df["emg2"].tolist(),
            "emg3": df["emg3"].tolist(),
            "emg4": df["emg4"].tolist(),
            "angle": df["angle"].tolist(),
        }

        datasets = get_datasets()
        return render_template(
            "dataset.html",
            dataset_id=dataset_id,
            stats=stats,
            plot_data=plot_data,
            datasets=datasets,
        )

    except Exception as e:
        logger.error(f"Ошибка отображения данных {dataset_id}: {str(e)}")
        return f"Ошибка: {str(e)}", 500


@app.route("/add_dataset", methods=["GET", "POST"])
def add_dataset():
    if request.method == "POST":
        try:
            file = request.files["file"]
            dataset_name = request.form["dataset_name"]
            if file and dataset_name:
                if not file.filename.endswith(".xlsx"):
                    logger.error("Неверный формат. Возможен только xlsx")
                    return "Загрузите файл xlsx", 400

                #  переименуем файл чтобы не сохранялся один и тот же
                current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                name, ext = os.path.splitext(file.filename)
                new_filename = f"{name}_{current_time}{ext}"
                file_path = os.path.join(app.config["UPLOAD_FOLDER"], new_filename)
                file.save(file_path)

                dataset_id = load_dataset(file_path, dataset_name)
                logger.info(f"Перенеправление на данные {dataset_id}")
                return redirect(url_for("dataset", dataset_id=dataset_id))
            else:
                logger.error("Файл не загружен")
                return "Файл не загружен", 400
        except Exception as e:
            logger.error(f"Ошибка добавления данных: {str(e)}")
            return f"Ошибка: {str(e)}", 500
    return render_template("add_dataset.html")


# ----------------------------
# JSON API (для фронта)
# ----------------------------

@app.route("/api/datasets", methods=["GET"])
def api_get_datasets():
    """Список датасетов."""
    datasets = get_datasets()  # [(id, name), ...]
    return jsonify([{"id": int(d[0]), "name": d[1]} for d in datasets]), 200


@app.route("/api/dataset/<int:dataset_id>", methods=["GET"])
def api_get_dataset(dataset_id: int):
    """Детали датасета: метаданные + series + stats."""
    info = get_dataset_info(dataset_id)
    if not info:
        return jsonify({"error": f"dataset {dataset_id} not found"}), 404

    df = get_dataset_data(dataset_id)

    stats = {
        "mean": df[["emg1", "emg2", "emg3", "emg4", "angle"]].mean().to_dict(),
        "max": df[["emg1", "emg2", "emg3", "emg4", "angle"]].max().to_dict(),
        "peaks": calculate_peaks(df),
    }

    # series как массив объектов — фронту проще
    series = df[["timestamp", "emg1", "emg2", "emg3", "emg4", "angle"]].to_dict(
        orient="records"
    )

    return (
        jsonify({"id": info["id"], "name": info["name"], "stats": stats, "series": series}),
        200,
    )


@app.route("/api/dataset", methods=["POST"])
def api_create_dataset():
    """Создание датасета (загрузка нового xlsx). multipart: file + dataset_name"""
    try:
        if "file" not in request.files or "dataset_name" not in request.form:
            return jsonify({"error": "file and dataset_name are required"}), 400

        file = request.files["file"]
        dataset_name = request.form["dataset_name"].strip()

        if not dataset_name:
            return jsonify({"error": "dataset_name is empty"}), 400

        if not file or not file.filename:
            return jsonify({"error": "empty file"}), 400

        if not file.filename.endswith(".xlsx"):
            return jsonify({"error": "only .xlsx files are supported"}), 400

        current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        name, ext = os.path.splitext(file.filename)
        new_filename = f"{name}_{current_time}{ext}"
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], new_filename)
        file.save(file_path)

        dataset_id = load_dataset(file_path, dataset_name)
        return jsonify({"id": int(dataset_id), "message": "created"}), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Ошибка создания датасета: {str(e)}")
        return jsonify({"error": "server error"}), 500


# REST API для изменения загруженного набора данных
@app.route("/api/dataset/<int:dataset_id>", methods=["PUT"])
def update_dataset(dataset_id):
    try:
        if "file" not in request.files or "dataset_name" not in request.form:
            return jsonify({"error": "file and dataset_name are required"}), 400

        file = request.files["file"]
        dataset_name = request.form["dataset_name"]

        if not file.filename.endswith(".xlsx"):
            return jsonify({"error": "only .xlsx files are supported"}), 400

        #  переименуем файл чтобы не сохранялся один и тот же
        current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        name, ext = os.path.splitext(file.filename)
        new_filename = f"{name}_{current_time}{ext}"
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], new_filename)
        file.save(file_path)

        update_dataset_data(dataset_id, file_path, dataset_name)
        logger.info(f"Данные {dataset_id} обновлены")
        return jsonify({"message": "updated"}), 200

    except ValueError as e:
        logger.error(f"ошибка обновления данных {dataset_id}: {str(e)}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"ошибка обновления данных {dataset_id}: {str(e)}")
        return jsonify({"error": "server error"}), 500


if __name__ == "__main__":
    app.run(debug=True)
