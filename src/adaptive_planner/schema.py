from __future__ import annotations

import sqlite3


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    target_start_date TEXT NOT NULL,
    target_end_date TEXT NOT NULL,
    constraints_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS availability_windows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id INTEGER NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
    weekday INTEGER NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plan_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id INTEGER NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    status TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    rationale TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_version_id INTEGER NOT NULL REFERENCES plan_versions(id) ON DELETE CASCADE,
    task_key TEXT NOT NULL,
    position INTEGER NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    estimated_minutes INTEGER NOT NULL,
    difficulty TEXT NOT NULL,
    target_date TEXT,
    status TEXT NOT NULL,
    UNIQUE(plan_version_id, task_key)
);

CREATE TABLE IF NOT EXISTS dependencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_version_id INTEGER NOT NULL REFERENCES plan_versions(id) ON DELETE CASCADE,
    predecessor_task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    successor_task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS schedule_blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_version_id INTEGER NOT NULL REFERENCES plan_versions(id) ON DELETE CASCADE,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled'
);

CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_version_id INTEGER NOT NULL REFERENCES plan_versions(id) ON DELETE CASCADE,
    schedule_block_id INTEGER REFERENCES schedule_blocks(id) ON DELETE CASCADE,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    reminder_type TEXT NOT NULL,
    remind_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    delivered_at TEXT
);

CREATE TABLE IF NOT EXISTS feedback_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    actual_minutes INTEGER,
    difficulty INTEGER,
    confidence REAL,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS policy_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_version_id INTEGER NOT NULL REFERENCES plan_versions(id) ON DELETE CASCADE,
    task_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    reason TEXT NOT NULL,
    requires_confirmation INTEGER NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_version_id INTEGER NOT NULL REFERENCES plan_versions(id) ON DELETE CASCADE,
    proposal_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    reason TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_edit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    field_name TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plan_references (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id INTEGER NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
    plan_version_id INTEGER REFERENCES plan_versions(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assistant_summaries (
    plan_version_id INTEGER PRIMARY KEY REFERENCES plan_versions(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_plan_version_id ON tasks(plan_version_id);
CREATE INDEX IF NOT EXISTS idx_schedule_blocks_plan_version_id ON schedule_blocks(plan_version_id);
CREATE INDEX IF NOT EXISTS idx_feedback_events_task_id ON feedback_events(task_id);
CREATE INDEX IF NOT EXISTS idx_proposals_plan_version_id ON proposals(plan_version_id);
CREATE INDEX IF NOT EXISTS idx_plan_references_goal_id ON plan_references(goal_id);
CREATE INDEX IF NOT EXISTS idx_plan_references_plan_version_id ON plan_references(plan_version_id);
"""


def create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA_SQL)
