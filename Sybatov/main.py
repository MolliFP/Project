from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import hashlib
from datetime import datetime, timedelta
import os
import re



app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Замените своим секретным ключом


def update_task_in_db(task_id, new_status):
    conn = sqlite3.connect('tasks.db')  # Замените 'your_database.db' на имя вашей базы данных.
    cursor = conn.cursor()

    try:
        # Обновляем статус задачи в базе данных
        cursor.execute("UPDATE tasks SET status = ? WHERE id = ?", (new_status, task_id))
        conn.commit()

        # Получаем обновленную задачу
        cursor.execute("SELECT id, title, time_spent, priority FROM tasks WHERE id = ?", (task_id,))
        updated_task = cursor.fetchone()

        # Проверяем, была ли задача найдена и возвращаем её в виде словаря
        if updated_task:
            return {
                'id': updated_task[0],
                'title': updated_task[1],
                'time_spent': updated_task[2],
                'priority': updated_task[3],
                'status': new_status
            }
        else:
            return None
    except Exception as e:
        print(f"Ошибка при обновлении задачи: {e}")
        return None
    finally:
        conn.close()


def get_db_connection():
    conn = sqlite3.connect('tasks.db')
    conn.row_factory = sqlite3.Row  # Позволяет работать с результатами как со словарем
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('DROP TABLE IF EXISTS tasks')
    cursor.execute('DROP TABLE IF EXISTS users')
    cursor.execute('DROP TABLE IF EXISTS days')

    # Создание таблицы пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            is_admin BOOLEAN NOT NULL DEFAULT 0
        )
    ''')

    # Создание таблицы задач с полем timer_time для хранения времени таймера
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        end_time TIMESTAMP,
        notification_sent BOOLEAN NOT NULL DEFAULT 0,
        status TEXT DEFAULT 'waiting',
        priority TEXT DEFAULT 'medium',
        time_spent TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- Обновляем поле time_spent
        timer_time TEXT DEFAULT '0:00',  -- Новое поле для хранения времени таймера
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    # Создание таблицы дней
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS days (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL UNIQUE,
            created_by INTEGER NOT NULL,
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
    ''')

    conn.commit()
    conn.close()

def close_expired_tasks():
    """Close or delete expired tasks."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Удаляем задачи, которые просрочены
    cursor.execute('DELETE FROM tasks WHERE end_time < ?', (datetime.now().isoformat(),))
    conn.commit()
    conn.close()


def check_task_notifications():
    """Send notifications for tasks that are due soon."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Найдите все задачи, срок выполнения которых истекает в течение следующих 24 часов
    upcoming_tasks = cursor.execute('''
        SELECT * FROM tasks 
        WHERE due_date > ? AND notification_sent = 0
    ''', (datetime.now().isoformat(),)).fetchall()

    for task in upcoming_tasks:
        # Здесь вы можете добавить логику отправки уведомлений
        # Для простоты, просто печатаем уведомление в консоль
        print(f"Уведомление: Задача '{task['title']}' должна быть выполнена до {task['due_date']}.")

        # Обновите поле notification_sent
        cursor.execute('UPDATE tasks SET notification_sent = 1 WHERE id = ?', (task['id'],))

    conn.commit()
    conn.close()


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash("Пожалуйста, заполните все поля.")
            return redirect(url_for('login'))

        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM users WHERE username = ? AND password = ?
        ''', (username, hashed_password))
        user = cursor.fetchone()

        conn.close()

        if user:
            session['user_id'] = user['id']
            return redirect(url_for('index'))
        else:
            flash("Неверные имя пользователя или пароль!")
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash("Вы вышли из системы.")
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        errors = {}

        if len(username) < 3:
            errors['username_error'] = "Имя пользователя должно содержать минимум 3 символа."
        if len(password) < 6:
            errors['password_error'] = "Пароль должен содержать минимум 6 символов."

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            errors['username_error'] = "Имя пользователя уже занято."

        if errors:
            conn.close()
            return render_template('register.html', username=username,
                                   username_error=errors.get('username_error'),
                                   password_error=errors.get('password_error'))

        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                       (username, hashed_password))
        conn.commit()
        conn.close()

        flash("Регистрация успешна!")
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/report')
def report():
    return render_template('report.html')  # Убедитесь, что этот шаблон существует


from flask import request


@app.route('/add_task', methods=['POST'])
def add_task():
    task_title = request.form.get('task_title')
    task_description = request.form.get('task_description')
    completion_date = request.form.get('completion_date')
    priority = request.form.get('priority')
    status = 'waiting'  # Значение по умолчанию

    # Проверка, что все необходимые поля заполнены
    if not task_title or not completion_date or not priority:
        flash("Ошибка: все поля должны быть заполнены!")
        return redirect(url_for('tasks_calendar'))

    user_id = session['user_id']

    # Получаем текущее время в формате TIMESTAMP
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Логируем значения для отладки
    print(f"Adding task with values: Title: {task_title}, Description: {task_description}, "
          f"Completion Date: {completion_date}, Priority: {priority}, Status: {status}, Time Spent: {current_time}")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO tasks (user_id, title, description, end_time, priority, status, time_spent)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, task_title, task_description, completion_date, priority, status, current_time))  # Записываем текущее время в time_spent

        conn.commit()
        flash("Задача успешно добавлена!", "success")
        return redirect(url_for('tasks_calendar'))
    except Exception as e:
        print(f"Ошибка при добавлении задачи: {e}")
        flash("Ошибка при добавлении задачи.", "danger")
        return redirect(url_for('tasks_calendar'))
    finally:
        conn.close()

def get_user_tasks(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tasks WHERE user_id = ?', (user_id,))
    tasks_data = cursor.fetchall()  # Получение всех задач
    conn.close()

    return [dict(task) for task in tasks_data]  # Возвращаем каждую задачу как словарь


@app.route('/tasks_calendar', methods=['GET'])
def tasks_calendar():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    # Получаем параметры фильтрации и сортировки
    search_query = request.args.get('search')
    status_filter = request.args.get('status_filter')
    sort = request.args.get('sort')

    # Извлекаем задачи пользователя из базы данных
    tasks = get_user_tasks(user_id)

    # Фильтрация
    if search_query:
        tasks = [task for task in tasks if search_query.lower() in task['title'].lower() or search_query.lower() in task['description'].lower()]

    if status_filter:
        tasks = [task for task in tasks if task['status'] == status_filter]

    # Сортировка
    if sort == 'due_date':
        tasks.sort(key=lambda x: x['end_time'])  # Предполагая, что end_time — это подходящее поле для сортировки
    elif sort == 'priority':
        tasks.sort(key=lambda x: x['priority'])  # Предполагая, что priority — это строка

    # Разделение задач по статусам для отправки на фронт
    tasks_waiting = [task for task in tasks if task['status'] == 'waiting']
    tasks_in_progress = [task for task in tasks if task['status'] == 'inProgress']
    tasks_completed = [task for task in tasks if task['status'] == 'completed']

    return render_template('tasks_calendar.html',
                           tasks_waiting=tasks_waiting,
                           tasks_in_progress=tasks_in_progress,
                           tasks_completed=tasks_completed)

@app.route('/delete_task', methods=['POST'])
def delete_task():
    if 'user_id' not in session:
        flash("Пожалуйста, войдите в систему для доступа к задачам.")
        return redirect(url_for('login'))

    task_id = request.form['task_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()

    flash("Задача успешно удалена!")
    return redirect(url_for('tasks_calendar'))


@app.route('/oproduct')
def oproduct():
    return render_template('oproduct.html')


@app.route('/opportunities')
def opportunities():
    return render_template('opportunities.html')


@app.route('/price')
def price():
    return render_template('price.html')


@app.route('/manual')
def manual():
    return render_template('manual.html')


@app.route('/videotutorials')
def videotutorials():
    return render_template('videotutorials.html')


@app.route('/edit_task', methods=['POST'])
def edit_task():
    try:
        task_id = request.form['task_id']
        new_title = request.form['task_title']
        new_description = request.form['task_description']  # Получаем новое описание
        new_completion_date = request.form['completion_date']  # Получаем новую дату завершения
        new_priority = request.form['priority']  # Получаем новый приоритет

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE tasks 
            SET title = ?, description = ?, end_time = ?, priority = ? 
            WHERE id = ?
        ''', (new_title, new_description, new_completion_date, new_priority, task_id))

        conn.commit()
        conn.close()
        flash("Задача успешно обновлена!", "success")
        return redirect(url_for('tasks_calendar'))
    except Exception as e:
        print(f"Ошибка при редактировании задачи: {e}")
        flash("Ошибка при редактировании задачи.", "danger")
        return redirect(url_for('tasks_calendar'))


@app.route('/update_task_status', methods=['POST'])
def update_task_status():
    data = request.get_json()
    task_id = data.get('task_id')
    new_status = data.get('new_status')

    if not task_id or not new_status:
        return jsonify({'error': 'Missing task_id or new_status'}), 400

    # Обновите статус задачи в базе данных
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE tasks SET status = ? WHERE id = ?', (new_status, task_id))
        conn.commit()

        # Получение информации о задаче после обновления
        cursor.execute('SELECT title, description, end_time, priority FROM tasks WHERE id = ?', (task_id,))
        task = cursor.fetchone()

    if task:
        return jsonify({
            'id': task_id,
            'title': task[0],
            'description': task[1],
            'end_time': task[2],
            'priority': task[3],
            'status': new_status
        }), 200
    else:
        return jsonify({'error': 'Task not found'}), 404


@app.route('/update_task_time', methods=['POST'])
def update_task_time():
    try:
        data = request.get_json()
        task_id = data.get('task_id')  # Используем get для безопасного получения
        timer_time = data.get('timer_time')  # Получаем значение для timer_time

        # Проверка наличия task_id и timer_time
        if task_id is None or timer_time is None:
            return jsonify({"error": "Missing task_id or timer_time"}), 400

        # Обновление timer_time в базе данных
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('UPDATE tasks SET timer_time = ? WHERE id = ?', (timer_time, task_id))
        conn.commit()

        # Проверка, была ли задача обновлена
        if cursor.rowcount > 0:
            return jsonify({"success": True}), 200
        else:
            return jsonify({"error": "Task not found"}), 404

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

if __name__ == '__main__':
    if not os.path.exists('tasks.db'):
        init_db()
    app.run(debug=True)