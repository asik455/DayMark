import json
import tempfile
import unittest
from pathlib import Path

from app import create_app


class TaskApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.tasks_file = Path(self.temporary_directory.name) / "tasks.json"
        self.app = create_app({"TESTING": True, "TASKS_FILE": self.tasks_file})
        self.client = self.app.test_client()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def create_task(self, **overrides):
        task = {
            "title": "Prepare launch",
            "description": "Write the release checklist",
            "priority": "High",
            "status": "To do",
            "due_date": "2030-05-01",
        }
        task.update(overrides)
        response = self.client.post("/api/tasks", json=task)
        self.assertEqual(response.status_code, 201)
        return response.get_json()

    def test_create_list_filter_and_persist_tasks(self):
        first = self.create_task()
        second = self.create_task(title="Review notes", priority="Low")

        response = self.client.get("/api/tasks?q=launch&status=To%20do")

        self.assertEqual([task["id"] for task in response.get_json()], [first["id"]])
        self.assertEqual(
            json.loads(self.tasks_file.read_text(encoding="utf-8"))[1]["id"],
            second["id"],
        )

    def test_update_and_delete_task(self):
        task = self.create_task()

        updated = self.client.put(
            f"/api/tasks/{task['id']}",
            json={
                "title": "Launch shipped",
                "description": "",
                "priority": "Medium",
                "status": "Done",
                "due_date": "",
            },
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["status"], "Done")
        self.assertEqual(self.client.get("/api/stats").get_json()["done"], 1)

        deleted = self.client.delete(f"/api/tasks/{task['id']}")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(self.client.get("/api/tasks").get_json(), [])
        self.assertEqual(self.client.delete(f"/api/tasks/{task['id']}").status_code, 404)

    def test_rejects_invalid_input_and_unknown_task(self):
        self.assertEqual(self.client.post("/api/tasks", json={}).status_code, 400)
        self.assertEqual(
            self.client.post("/api/tasks", json={"title": "Bad", "priority": "Urgent"}).status_code,
            400,
        )
        self.assertEqual(
            self.client.post("/api/tasks", json={"title": "Bad", "priority": []}).status_code,
            400,
        )
        self.assertEqual(
            self.client.post("/api/tasks", json={"title": "Bad", "status": {}}).status_code,
            400,
        )
        self.assertEqual(
            self.client.put("/api/tasks/missing", json={"title": "Nope"}).status_code,
            404,
        )
        self.assertEqual(self.client.delete("/api/tasks/missing").status_code, 404)


if __name__ == "__main__":
    unittest.main()