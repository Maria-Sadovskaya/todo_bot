import sqlite3


def create_connection():
    """Создает подключение к SQLite базе данных."""
    conn = sqlite3.connect('todo.db')
    return conn


def create_table():
    """Создает таблицу задач, если её нет."""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task TEXT NOT NULL,
            deadline TEXT,
            is_done BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def add_task(user_id, task, deadline=None):
    """Добавляет новую задачу."""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO tasks (user_id, task, deadline)
        VALUES (?, ?, ?)
    ''', (user_id, task, deadline))
    conn.commit()
    conn.close()


def get_tasks(user_id, show_done=True):
    """Возвращает список задач пользователя."""
    conn = create_connection()
    cursor = conn.cursor()
    query = 'SELECT id, task, deadline, is_done FROM tasks WHERE user_id = ?'
    if not show_done:
        query += ' AND is_done = 0'
    query += ' order by created_at ASC'
    cursor.execute(query, (user_id,))
    tasks = cursor.fetchall()
    conn.close()
    return tasks


def mark_task_done(task_id):
    """Отмечает задачу выполненной."""
    conn = create_connection()
    cursor = conn.cursor()
    query = cursor.execute('SELECT id from tasks order by created_at ASC').fetchall()
    for i in range(len(query)):
        if i == task_id - 1:
            cursor.execute('''
                        UPDATE tasks SET is_done = 1 WHERE id = ?
                    ''', (query[i][0],))
            break
    conn.commit()
    conn.close()


def delete_task(task_id):
    """Удаляет задачу."""
    conn = create_connection()
    cursor = conn.cursor()
    query = cursor.execute('SELECT id from tasks order by created_at ASC').fetchall()
    for i in range(len(query)):
        if i == task_id - 1:
            cursor.execute('''
                    DELETE FROM tasks WHERE id = ?
                ''', (query[i][0],))
            break
    conn.commit()
    conn.close()


# Инициализация БД при запуске
create_table()
