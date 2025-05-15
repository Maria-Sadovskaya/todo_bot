import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
import db
import os

with open('token') as f:
    TOKEN = f.readline().strip()
    WEATHER_API_KEY = f.readlines()[0]
WEATHER_API_URL = "http://api.weatherapi.com/v1/current.json"


# ===== Обработчики команд =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start."""
    await update.message.reply_text(
        "📝 *To-Do Bot*\n\n"
        "Добавляй задачи, ставь дедлайны и отмечай выполненные!\n\n"
        "Доступные команды:\n"
        "/add - добавить задачу (можно отправить отдельным сообщением)\n"
        "/list - показать список невыполненных дел\n"
        "/weather - узнать текущую погоду\n"
        "/help - справка",
        parse_mode="Markdown"
    )


async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавление задачи."""
    user_id = update.message.from_user.id
    task_text = " ".join(context.args) if context.args else None

    if task_text:
        # Если задача передана сразу с командой
        await process_task(update, context, user_id, task_text)
    else:
        # Если задача будет отправлена следующим сообщением
        await update.message.reply_text("📝 Отправьте мне задачу следующим сообщением:")
        context.user_data["waiting_for_task"] = True


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Универсальный обработчик сообщений."""
    user_id = update.message.from_user.id
    text = update.message.text

    # Если ожидаем задачу после /add
    if context.user_data.get("waiting_for_task"):
        await process_task(update, context, user_id, text)
        context.user_data["waiting_for_task"] = False
        return

    # Если есть активное действие (done/delete) и введен номер задачи
    if "action" in context.user_data:
        action = context.user_data.get("action")
        task_number = text.strip()

        if not task_number.isdigit():
            await update.message.reply_text("❌ Введи номер задачи (цифру)!")
            return

        task_id = int(task_number)
        tasks = db.get_tasks(user_id)
        task_nums = len(tasks) + 1

        if task_id > task_nums or task_id < 0:
            await update.message.reply_text("❌ Такой задачи нет в списке!")
            return

        if action == "done":
            db.mark_task_done(task_id)
            await update.message.reply_text(f"✅ Задача {task_id} выполнена!")
            return
        elif action == "delete":
            db.delete_task(task_id)
            await update.message.reply_text(f"🗑 Задача {task_id} удалена!")
            return

    # Если сообщение не распознано
    await update.message.reply_text("ℹ Используйте команды для работы с ботом (/start для списка команд)")


async def process_task(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, task_text: str):
    """Обрабатывает текст задачи и добавляет в БД."""
    # Парсинг дедлайна (пример: "задача --завтра 18:00")
    deadline = None
    if "--" in task_text:
        task_text, deadline_part = task_text.split("--", 1)
        deadline = deadline_part.strip()

    db.add_task(user_id, task_text.strip(), deadline)
    await update.message.reply_text(f"✅ Задача добавлена: *{task_text.strip()}*", parse_mode="Markdown")


async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список задач."""
    user_id = update.message.from_user.id
    tasks = db.get_tasks(user_id)

    if not tasks:
        await update.message.reply_text("📭 Список задач пуст!")
        return

    tasks_text = "📋 *Твои задачи:*\n\n"
    for i in range(len(tasks)):
        task_id, task_text, deadline, is_done = tasks[i]
        status = "✓" if is_done else "◻"
        deadline_str = f" (до {deadline})" if deadline else ""
        tasks_text += f"{status} {i + 1}. {task_text}{deadline_str}\n"

    # Кнопки для управления задачами
    keyboard = [
        [InlineKeyboardButton("✔ Отметить выполненным", callback_data="done")],
        [InlineKeyboardButton("🗑 Удалить задачу", callback_data="delete")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(tasks_text, reply_markup=reply_markup)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок (выполнить/удалить)."""
    query = update.callback_query
    await query.answer()

    if query.data == "done":
        await query.edit_message_text("Напиши номер задачи для отметки (например, '1'):")
        context.user_data["action"] = "done"
    elif query.data == "delete":
        await query.edit_message_text("Напиши номер задачи для удаления (например, '1'):")
        context.user_data["action"] = "delete"


async def handle_task_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод номера задачи."""
    user_id = update.message.from_user.id
    action = context.user_data.get("action")
    task_number = update.message.text.strip()

    if not task_number.isdigit():
        await update.message.reply_text("❌ Введи номер задачи (цифру)!")
        return

    task_id = int(task_number)
    tasks = db.get_tasks(user_id)
    task_ids = [task[0] for task in tasks]
    task_nums = len(tasks) + 1

    if task_id > task_nums or task_id < 0:
        await update.message.reply_text("❌ Такой задачи нет в списке!")
        return

    if action == "done":
        db.mark_task_done(task_id)
        await update.message.reply_text(f"✅ Задача {task_id} выполнена!")
    elif action == "delete":
        db.delete_task(task_id)
        await update.message.reply_text(f"🗑 Задача {task_id} удалена!")


async def get_weather(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Получение погоды по указанному городу."""
    if not context.args:
        await update.message.reply_text("Пожалуйста, укажите город. Например: /weather Москва")
        return

    location = " ".join(context.args)

    try:
        # Запрос к API погоды
        params = {
            "key": WEATHER_API_KEY,
            "q": location,
            "lang": "ru"
        }
        response = requests.get(WEATHER_API_URL, params=params)
        response.raise_for_status()  # Проверка на ошибки HTTP

        data = response.json()

        # Извлечение данных о погоде
        current = data["current"]
        location_data = data["location"]

        weather_info = (
            f"🌤 Погода в {location_data['name']}, {location_data['country']}:\n"
            f"🌡 Температура: {current['temp_c']}°C (ощущается как {current['feelslike_c']}°C)\n"
            f"☁ Состояние: {current['condition']['text']}\n"
            f"💨 Ветер: {current['wind_kph']} км/ч, направление: {current['wind_dir']}\n"
            f"💧 Влажность: {current['humidity']}%\n"
            f"🕒 Последнее обновление: {current['last_updated']}"
        )

        await update.message.reply_text(weather_info)

    except requests.exceptions.RequestException as e:
        await update.message.reply_text(f"Ошибка при запросе погоды: {e}")
    except KeyError:
        await update.message.reply_text("Не удалось обработать данные о погоде.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help. Показывает список всех доступных команд."""
    help_text = (
        "📝 *To-Do Bot - Справка по командам*\n\n"
        "Доступные команды:\n"
        "/start - начать работу с ботом\n"
        "/help - показать эту справку\n"
        "/add [задача] - добавить новую задачу (можно отправить отдельным сообщением)\n"
        "   Пример: /add Купить молоко --завтра 18:00\n"
        "/list - показать список всех задач\n"
        "/weather [город] - узнать текущую погоду в указанном городе\n"
        "\n"
        "Как работать с задачами:\n"
        "1. Добавьте задачу командой /add\n"
        "2. Просматривайте список задач командой /list\n"
        "3. Используйте кнопки под списком задач для отметки выполнения или удаления\n"
        "\n"
        "Вы можете указывать дедлайн для задачи, добавив '--' и дату/время:\n"
        "Пример: 'Позвонить маме --завтра 20:00'"
    )

    await update.message.reply_text(help_text, parse_mode="Markdown")


async def send_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет PDF-файл пользователю."""
    try:
        # Укажите путь к вашему PDF-файлу
        pdf_path = "./SQL.pdf"  # Замените на актуальный путь к файлу

        # Проверяем существование файла
        if not os.path.exists(pdf_path):
            await update.message.reply_text("❌ PDF-файл не найден!")
            return

        # Отправляем файл
        await update.message.reply_document(
            document=open(pdf_path, 'rb'),
            caption="Вот запрошенный PDF-файл 📄"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Произошла ошибка при отправке файла: {str(e)}")

async def send_pdf_python(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет PDF-файл пользователю."""
    try:
        # Укажите путь к вашему PDF-файлу
        pdf_path = "./pythonworldru.pdf"  # Замените на актуальный путь к файлу

        # Проверяем существование файла
        if not os.path.exists(pdf_path):
            await update.message.reply_text("❌ PDF-файл не найден!")
            return

        # Отправляем файл
        await update.message.reply_document(
            document=open(pdf_path, 'rb'),
            caption="Вот запрошенный PDF-файл 📄"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Произошла ошибка при отправке файла: {str(e)}")

# ===== Запуск бота =====
def main():
    app = Application.builder().token(TOKEN).build()

    # Регистрация обработчиков
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("add", add_task))
    app.add_handler(CommandHandler("list", list_tasks))
    app.add_handler(CommandHandler("weather", get_weather))
    app.add_handler(CommandHandler("sql", send_pdf))
    app.add_handler(CommandHandler("python", send_pdf_python))
    app.add_handler(CallbackQueryHandler(button_handler))

    # Универсальный обработчик сообщений
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен! 🚀")
    app.run_polling()


if __name__ == "__main__":
    main()
