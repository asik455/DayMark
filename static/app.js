const taskList = document.querySelector("#task-list");
const dialog = document.querySelector("#task-dialog");
const form = document.querySelector("#task-form");
const searchInput = document.querySelector("#search-input");
const statusFilter = document.querySelector("#status-filter");
const priorityFilter = document.querySelector("#priority-filter");
const formError = document.querySelector("#form-error");
const toast = document.querySelector("#toast");

const readCookie = (name) => {
  const entry = document.cookie.split("; ").find((part) => part.startsWith(`${name}=`));
  return entry ? decodeURIComponent(entry.slice(name.length + 1)) : "";
};

const savePreference = (name, value) => {
  document.cookie = `${name}=${encodeURIComponent(value)}; Max-Age=2592000; Path=/; SameSite=Lax`;
};

const escapeHtml = (value = "") => String(value).replace(/[&<>"']/g, (character) => ({
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
}[character]));

let searchTimer;
let toastTimer;

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("is-visible");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => toast.classList.remove("is-visible"), 2600);
}

function formatDueDate(value) {
  if (!value) return "No due date";
  const date = new Date(`${value}T00:00:00`);
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(date);
}

function renderTask(task) {
  const isDone = task.status === "Done";
  const isOverdue = task.due_date && task.due_date < new Date().toISOString().slice(0, 10) && !isDone;
  return `<article class="task-row ${isDone ? "is-done" : ""}" data-task-id="${escapeHtml(task.id)}">
    <button class="task-check ${isDone ? "checked" : ""}" type="button" data-action="toggle" aria-label="${isDone ? "Mark as to do" : "Mark as done"}" title="${isDone ? "Mark as to do" : "Mark as done"}">${isDone ? "✓" : ""}</button>
    <div class="task-main"><h3>${escapeHtml(task.title)}</h3><p>${escapeHtml(task.description || "No extra details")}</p></div>
    <span class="priority-tag priority-${task.priority.toLowerCase()}"><i></i>${escapeHtml(task.priority)}</span>
    <span class="status-tag status-${task.status.toLowerCase().replaceAll(" ", "-")}">${escapeHtml(task.status)}</span>
    <span class="due-date ${isOverdue ? "is-overdue" : ""}">${escapeHtml(formatDueDate(task.due_date))}${isOverdue ? " · late" : ""}</span>
    <div class="task-actions"><button type="button" data-action="edit" aria-label="Edit ${escapeHtml(task.title)}" title="Edit task">↗</button><button type="button" data-action="delete" aria-label="Delete ${escapeHtml(task.title)}" title="Delete task">×</button></div>
  </article>`;
}

async function loadTasks() {
  const params = new URLSearchParams();
  if (searchInput.value.trim()) params.set("q", searchInput.value.trim());
  if (statusFilter.value) params.set("status", statusFilter.value);
  if (priorityFilter.value) params.set("priority", priorityFilter.value);
  taskList.classList.add("is-loading");
  try {
    const [tasksResponse, statsResponse] = await Promise.all([
      fetch(`/api/tasks?${params}`),
      fetch("/api/stats"),
    ]);
    if (!tasksResponse.ok || !statsResponse.ok) throw new Error("Could not load tasks.");
    const tasks = await tasksResponse.json();
    const stats = await statsResponse.json();
    taskList.innerHTML = tasks.length
      ? tasks.map(renderTask).join("")
      : `<div class="empty-state"><span class="empty-spark">✳</span><h3>${params.size ? "Nothing matches just yet." : "A fresh page."}</h3><p>${params.size ? "Try a different search or filter." : "Add a task to give your day a little direction."}</p>${params.size ? "" : '<button class="button button-primary" type="button" data-action="add">Add your first task <span aria-hidden="true">→</span></button>'}</div>`;
    document.querySelector("#stat-total").textContent = stats.total;
    document.querySelector("#stat-todo").textContent = stats.todo;
    document.querySelector("#stat-progress").textContent = stats.in_progress;
    document.querySelector("#stat-done").textContent = stats.done;
    document.querySelector("#visible-count").textContent = tasks.length;
  } catch (error) {
    taskList.innerHTML = `<div class="empty-state"><h3>Tasks couldn’t load.</h3><p>${escapeHtml(error.message)}</p><button class="button button-quiet" type="button" data-action="reload">Try again</button></div>`;
  } finally {
    taskList.classList.remove("is-loading");
  }
}

async function submitTask(event) {
  event.preventDefault();
  formError.textContent = "";
  const id = document.querySelector("#task-id").value;
  const payload = {
    title: document.querySelector("#task-title").value.trim(),
    description: document.querySelector("#task-description").value.trim(),
    priority: document.querySelector("#task-priority").value,
    status: document.querySelector("#task-status").value,
    due_date: document.querySelector("#task-due-date").value,
  };
  const saveButton = document.querySelector("#save-task");
  saveButton.disabled = true;
  try {
    const response = await fetch(id ? `/api/tasks/${encodeURIComponent(id)}` : "/api/tasks", {
      method: id ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Could not save this task.");
    dialog.close();
    showToast(id ? "Task updated" : "Task added");
    await loadTasks();
  } catch (error) {
    formError.textContent = error.message;
  } finally {
    saveButton.disabled = false;
  }
}

function openDialog(task = null) {
  form.reset();
  formError.textContent = "";
  document.querySelector("#task-id").value = task?.id || "";
  document.querySelector("#dialog-title").textContent = task ? "Edit task" : "Add a task";
  document.querySelector("#dialog-eyebrow").textContent = task ? "A SMALL ADJUSTMENT" : "MAKE IT HAPPEN";
  document.querySelector("#save-task").textContent = task ? "Update task" : "Save task";
  document.querySelector("#task-title").value = task?.title || "";
  document.querySelector("#task-description").value = task?.description || "";
  document.querySelector("#task-priority").value = task?.priority || "Medium";
  document.querySelector("#task-status").value = task?.status || "To do";
  document.querySelector("#task-due-date").value = task?.due_date || "";
  dialog.showModal();
  document.querySelector("#task-title").focus();
}

taskList.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  const action = button.dataset.action;
  if (action === "add") return openDialog();
  if (action === "reload") return loadTasks();
  const row = button.closest("[data-task-id]");
  if (!row) return;
  const id = row.dataset.taskId;
  if (action === "delete") {
    if (!window.confirm("Delete this task? This can’t be undone.")) return;
    const response = await fetch(`/api/tasks/${encodeURIComponent(id)}`, { method: "DELETE" });
    if (response.ok) {
      showToast("Task deleted");
      await loadTasks();
    } else {
      showToast("Could not delete this task");
    }
    return;
  }
  const response = await fetch("/api/tasks");
  const tasks = await response.json();
  const task = tasks.find((item) => item.id === id);
  if (!task) return;
  if (action === "edit") return openDialog(task);
  if (action === "toggle") {
    const updated = { ...task, status: task.status === "Done" ? "To do" : "Done" };
    const result = await fetch(`/api/tasks/${encodeURIComponent(id)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updated),
    });
    if (result.ok) await loadTasks();
  }
});

document.querySelector("#add-task-button").addEventListener("click", () => openDialog());
document.querySelector("#close-dialog").addEventListener("click", () => dialog.close());
document.querySelector("#cancel-dialog").addEventListener("click", () => dialog.close());
form.addEventListener("submit", submitTask);
searchInput.addEventListener("input", () => {
  window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(loadTasks, 180);
});
[statusFilter, priorityFilter].forEach((filter) => {
  filter.addEventListener("change", () => {
    savePreference(filter.id, filter.value);
    loadTasks();
  });
});
document.querySelector("#clear-filters").addEventListener("click", () => {
  searchInput.value = "";
  statusFilter.value = "";
  priorityFilter.value = "";
  savePreference("status-filter", "");
  savePreference("priority-filter", "");
  loadTasks();
});
document.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    searchInput.focus();
  }
});

statusFilter.value = readCookie("status-filter");
priorityFilter.value = readCookie("priority-filter");
document.querySelector("#today-label").textContent = new Intl.DateTimeFormat(undefined, {
  weekday: "long",
  month: "long",
  day: "numeric",
}).format(new Date());
loadTasks();