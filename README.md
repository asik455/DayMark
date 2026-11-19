# Daymark Task Manager

A small, responsive task manager built with Flask, HTML, CSS, and vanilla JavaScript. Tasks are stored in a local JSON file; no database or frontend build step is required.

## Features

- Landing page with a direct route into the workspace
- Create, view, edit, complete, and delete tasks
- Task title, description, priority, status, and due date
- Search across task titles and descriptions; filter by status and priority
- Live task counts for total, to do, in progress, and completed work
- Filter preferences saved in browser cookies
- JSON persistence in `instance/tasks.json`
- REST API consumed with the Fetch API

## Requirements

- Python 3.9 or newer
- pip

## Installation

From the project directory, create and activate a virtual environment:

```powershell
py -3.9 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the pinned dependencies and start the development server:

```powershell
python -m pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:5000> in your browser. The workspace is at <http://127.0.0.1:5000/dashboard>.

To run the tests:

```powershell
python -m unittest discover -s tests -v
```

## REST API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/tasks` | List tasks; optional `q`, `status`, and `priority` query parameters |
| `POST` | `/api/tasks` | Create a task |
| `PUT` | `/api/tasks/<id>` | Replace a task's editable fields |
| `DELETE` | `/api/tasks/<id>` | Delete a task |
| `GET` | `/api/stats` | Read task totals by status |

Task JSON fields are `title`, `description`, `priority` (`Low`, `Medium`, `High`), `status` (`To do`, `In progress`, `Done`), and `due_date` (`YYYY-MM-DD` or an empty string). The app creates `instance/tasks.json` on the first write.

## Search indexing and deployment

`/robots.txt` allows crawling and points crawlers to `/sitemap.xml`. The sitemap includes the site root. Set `SITE_URL` to the canonical public origin in the deployment environment so generated URLs consistently use your public domain. If it is unset, the current request host is used.

Gunicorn is included for Linux-based deployments. Set the canonical URL and start the app with:

```sh
export SITE_URL="https://tasks.example.com"
gunicorn app:app
```

Gunicorn is not supported on Windows; use `python app.py` for local Windows development.