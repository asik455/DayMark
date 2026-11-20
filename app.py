import json
import os
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import PyMongoError


PRIORITIES = {"Low", "Medium", "High"}
STATUSES = {"To do", "In progress", "Done"}

load_dotenv()


class DatabaseConfigurationError(Exception):
    pass


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        TASKS_FILE=None,
        LEGACY_TASKS_FILE=Path(app.instance_path) / "tasks.json",
        MONGO_URI=os.environ.get("MONGO_URI"),
        MONGO_DB_NAME=os.environ.get("MONGO_DB_NAME", "mydb"),
        MAX_CONTENT_LENGTH=1024 * 1024,
        SITE_URL=os.environ.get("SITE_URL", "").rstrip("/"),
    )
    if test_config:
        app.config.update(test_config)

    app.extensions["mongo_client"] = None
    app.extensions["tasks_collection"] = None
    app.extensions["mongo_initialized"] = False

    def read_json_tasks(path):
        path = Path(path)
        if not path.exists():
            return []
        try:
            with path.open(encoding="utf-8") as tasks_file:
                tasks = json.load(tasks_file)
        except (json.JSONDecodeError, OSError):
            app.logger.exception("Unable to read task storage")
            return []
        return tasks if isinstance(tasks, list) else []

    def get_tasks_collection():
        collection = app.extensions["tasks_collection"]
        if collection is None:
            mongo_uri = app.config["MONGO_URI"]
            if not mongo_uri:
                raise DatabaseConfigurationError(
                    "MongoDB is not configured. Set MONGO_URI in the environment."
                )
            mongo_client = MongoClient(
                mongo_uri,
                w=1,
                wtimeoutms=5000,
                serverSelectionTimeoutMS=15000,
            )
            database = mongo_client.get_default_database(
                default=app.config["MONGO_DB_NAME"]
            )
            collection = database["tasks"]
            app.extensions["mongo_client"] = mongo_client
            app.extensions["tasks_collection"] = collection
        if not app.extensions["mongo_initialized"]:
            collection.create_index("id", unique=True)
            for task in read_json_tasks(app.config["LEGACY_TASKS_FILE"]):
                if isinstance(task, dict) and isinstance(task.get("id"), str):
                    collection.update_one(
                        {"id": task["id"]},
                        {"$setOnInsert": task},
                        upsert=True,
                    )
            app.extensions["mongo_initialized"] = True
        return collection

    def read_tasks():
        if app.config["TASKS_FILE"] is not None:
            return read_json_tasks(app.config["TASKS_FILE"])
        collection = get_tasks_collection()
        documents = collection.find().sort([("created_at", 1), ("id", 1)])
        return [
            {key: value for key, value in task.items() if key != "_id"}
            for task in documents
        ]

    def write_tasks(tasks):
        path = Path(app.config["TASKS_FILE"])
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=path.parent, delete=False
            ) as tasks_file:
                json.dump(tasks, tasks_file, indent=2)
                temporary_path = tasks_file.name
            os.replace(temporary_path, path)
        finally:
            if temporary_path and os.path.exists(temporary_path):
                os.unlink(temporary_path)

    @app.errorhandler(DatabaseConfigurationError)
    def handle_database_configuration_error(error):
        return jsonify({"error": str(error)}), 503

    @app.errorhandler(PyMongoError)
    def handle_database_error(error):
        app.logger.exception(
            "MongoDB operation failed: %s", type(error).__name__
        )
        return jsonify({"error": "MongoDB is unavailable."}), 503

    def validate_task(data):
        if not isinstance(data, dict):
            return None, "A task object is required."

        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            return None, "Title is required."
        if len(title.strip()) > 120:
            return None, "Title must be 120 characters or fewer."

        description = data.get("description", "")
        if not isinstance(description, str) or len(description) > 2000:
            return None, "Description must be 2000 characters or fewer."

        priority = data.get("priority", "Medium")
        if not isinstance(priority, str) or priority not in PRIORITIES:
            return None, "Priority must be Low, Medium, or High."

        status = data.get("status", "To do")
        if not isinstance(status, str) or status not in STATUSES:
            return None, "Status must be To do, In progress, or Done."

        due_date = data.get("due_date", "")
        if due_date:
            try:
                date.fromisoformat(due_date)
            except (TypeError, ValueError):
                return None, "Due date must be a valid YYYY-MM-DD date."
        elif due_date != "":
            return None, "Due date must be a string."

        return {
            "title": title.strip(),
            "description": description.strip(),
            "priority": priority,
            "status": status,
            "due_date": due_date,
        }, None

    @app.get("/")
    def landing():
        return render_template("index.html")

    @app.get("/dashboard")
    def dashboard():
        return render_template("dashboard.html")

    @app.get("/robots.txt")
    def robots():
        site_url = (app.config["SITE_URL"] or request.url_root).rstrip("/")
        content = f"User-agent: *\nAllow: /\nSitemap: {site_url}/sitemap.xml\n"
        return Response(content, mimetype="text/plain")

    @app.get("/sitemap.xml")
    def sitemap():
        site_url = (app.config["SITE_URL"] or request.url_root).rstrip("/")
        xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{site_url}/</loc></url>
</urlset>'''
        return Response(xml, mimetype="application/xml")

    @app.get("/api/tasks")
    def list_tasks():
        tasks = read_tasks()
        search = request.args.get("q", "").strip().casefold()
        status = request.args.get("status", "").strip()
        priority = request.args.get("priority", "").strip()
        if search:
            tasks = [
                task
                for task in tasks
                if search in task["title"].casefold()
                or search in task.get("description", "").casefold()
            ]
        if status in STATUSES:
            tasks = [task for task in tasks if task["status"] == status]
        if priority in PRIORITIES:
            tasks = [task for task in tasks if task["priority"] == priority]
        return jsonify(tasks)

    @app.get("/api/stats")
    def task_stats():
        tasks = read_tasks()
        return jsonify(
            {
                "total": len(tasks),
                "todo": sum(task["status"] == "To do" for task in tasks),
                "in_progress": sum(
                    task["status"] == "In progress" for task in tasks
                ),
                "done": sum(task["status"] == "Done" for task in tasks),
            }
        )

    @app.post("/api/tasks")
    def create_task():
        data, error = validate_task(request.get_json(silent=True))
        if error:
            return jsonify({"error": error}), 400
        now = datetime.now(timezone.utc).isoformat()
        task = {
            "id": str(uuid4()),
            **data,
            "created_at": now,
            "updated_at": now,
        }
        if app.config["TASKS_FILE"] is not None:
            tasks = read_tasks()
            tasks.append(task)
            write_tasks(tasks)
        else:
            get_tasks_collection().insert_one(task.copy())
        return jsonify(task), 201

    @app.put("/api/tasks/<task_id>")
    def update_task(task_id):
        data, error = validate_task(request.get_json(silent=True))
        if error:
            return jsonify({"error": error}), 400
        if app.config["TASKS_FILE"] is not None:
            tasks = read_tasks()
            for index, task in enumerate(tasks):
                if task["id"] == task_id:
                    updated = {
                        **task,
                        **data,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                    tasks[index] = updated
                    write_tasks(tasks)
                    return jsonify(updated)
        else:
            updated = get_tasks_collection().find_one_and_update(
                {"id": task_id},
                {
                    "$set": {
                        **data,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                },
                return_document=ReturnDocument.AFTER,
            )
            if updated:
                updated.pop("_id", None)
                return jsonify(updated)
        return jsonify({"error": "Task not found."}), 404

    @app.delete("/api/tasks/<task_id>")
    def delete_task(task_id):
        if app.config["TASKS_FILE"] is not None:
            tasks = read_tasks()
            remaining = [task for task in tasks if task["id"] != task_id]
            if len(remaining) == len(tasks):
                return jsonify({"error": "Task not found."}), 404
            write_tasks(remaining)
        else:
            result = get_tasks_collection().delete_one({"id": task_id})
            if result.deleted_count == 0:
                return jsonify({"error": "Task not found."}), 404
        return jsonify({"message": "Task deleted."})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)