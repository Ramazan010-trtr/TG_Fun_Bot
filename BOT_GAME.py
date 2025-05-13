import logging
import random
import os
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

#Telegram TOKEN
BOT_TOKEN = "7546943111:AAEz0DCb5R1mmkYcMNu0x9NhVE9EittRROI"  # ВАЖНО: Замените на ваш реальный токен

# Включаем логирование, чтобы видеть ошибки
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Константы для файлов ---
DATA_DIR = "data"
JOKES_FILE = os.path.join(DATA_DIR, "jokes.txt")
FACTS_FILE = os.path.join(DATA_DIR, "facts.txt")
CITIES_FILE = os.path.join(DATA_DIR, "cities.txt")
HANGMAN_WORDS_FILE = os.path.join(DATA_DIR, "words_hangman.txt")
WORDLE_WORDS_FILE = os.path.join(DATA_DIR, "words_wordle.txt")

# --- Глобальные переменные для загруженных данных (кэширование) ---
ALL_JOKES = []
ALL_FACTS = []
ALL_CITIES = []
ALL_HANGMAN_WORDS = []
ALL_WORDLE_WORDS = []

# --- Состояния для игр ---
RPS_CHOICES = ["камень", "ножницы", "бумага"]
HANGMAN_STAGES = [
    """
       -----
       |   |
           |
           |
           |
           |
    --------
    """,
    """
       -----
       |   |
      X_X   |
           |
           |
           |
    --------
    """,
    """
       -----
       |   |
      X_X   |
       |   |
           |
           |
    --------
    """,
    """
       -----
       |   |
      X_X   |
      /|   |
           |
           |
    --------
    """,
    """
       -----
       |   |
      X_X   |
      /|\  |
           |
           |
    --------
    """,
    """
       -----
       |   |
      X_X   |
      /|\  |
      /    |
           |
    --------
    """,
    """
       -----
       |   |
      X_X   |
      /|\  |
      / \  |
           |
    --------
    """
]
WORDLE_MAX_GUESSES = 6
WORDLE_WORD_LENGTH = 5
RUSSIAN_ALPHABET = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"


# --- Вспомогательная функция для экранирования MarkdownV2 ---
def escape_markdown_v2(text: str) -> str:
    """Экранирует специальные символы для MarkdownV2."""
    if not isinstance(text, str):
        return ""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return "".join(f'\\{char}' if char in escape_chars else char for char in text)


# --- Функции для загрузки данных из файлов ---
def load_data_from_file(filepath):
    """Загружает строки из файла, удаляя пустые строки и пробелы по краям."""
    try:
        if not os.path.exists(filepath):
            logger.error(f"Файл не найден: {filepath}")
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                if "jokes" in filepath:
                    f.write("Это шутка по умолчанию, потому что файл jokes.txt пуст или не найден.\n")
                elif "facts" in filepath:
                    f.write("Это факт по умолчанию, потому что файл facts.txt пуст или не найден.\n")
                elif "cities" in filepath:
                    f.write("москва\n")
                elif "words_hangman" in filepath:
                    f.write("слово\n")
                elif "words_wordle" in filepath:
                    f.write("слово\n")
                else:
                    f.write("Данные по умолчанию, файл не найден.\n")
            logger.info(f"Создан пустой файл: {filepath} с содержимым по умолчанию.")

        with open(filepath, "r", encoding="utf-8") as f:
            items = [line.strip() for line in f if line.strip()]
        if not items:
            logger.warning(f"Файл пуст: {filepath}. Используется значение по умолчанию.")
            if "jokes" in filepath: return ["Это шутка по умолчанию, потому что файл jokes.txt пуст."]
            if "facts" in filepath: return ["Это факт по умолчанию, потому что файл facts.txt пуст."]
            if "cities" in filepath: return ["москва"]
            if "words_hangman" in filepath: return ["слово"]
            if "words_wordle" in filepath: return ["слово"]
            return ["Нет данных в файле."]
        return items
    except Exception as e:
        logger.error(f"Ошибка загрузки файла {filepath}: {e}")
        return []


def initialize_data():
    """Загружает все данные при старте бота."""
    global ALL_JOKES, ALL_FACTS, ALL_CITIES, ALL_HANGMAN_WORDS, ALL_WORDLE_WORDS
    logger.info("Инициализация данных из файлов...")
    ALL_JOKES = load_data_from_file(JOKES_FILE)
    ALL_FACTS = load_data_from_file(FACTS_FILE)
    ALL_CITIES = [city.lower() for city in load_data_from_file(CITIES_FILE)]
    ALL_HANGMAN_WORDS = [word.lower() for word in load_data_from_file(HANGMAN_WORDS_FILE)]
    ALL_WORDLE_WORDS = [word.lower() for word in load_data_from_file(WORDLE_WORDS_FILE) if
                        len(word) == WORDLE_WORD_LENGTH]

    if not ALL_WORDLE_WORDS:
        logger.warning(f"Не найдено слов длиной {WORDLE_WORD_LENGTH} в {WORDLE_WORDS_FILE}. Wordle может не работать.")
        ALL_WORDLE_WORDS.append("слово")
    if not ALL_CITIES: ALL_CITIES.append("москва")
    if not ALL_HANGMAN_WORDS: ALL_HANGMAN_WORDS.append("слово")

    logger.info(f"Загружено {len(ALL_JOKES)} шуток, {len(ALL_FACTS)} фактов.")
    logger.info(
        f"Загружено {len(ALL_CITIES)} городов, {len(ALL_HANGMAN_WORDS)} слов для Виселицы, {len(ALL_WORDLE_WORDS)} слов для Wordle.")


def get_random_item_with_memory(items_list: list, memory_key: str, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Возвращает случайный элемент, избегая повторений для пользователя, пока все не будут показаны."""
    if not items_list:
        return "Извините, по этой теме пока ничего нет."

    seen_items = context.user_data.get(memory_key, set())
    available_items = [item for item in items_list if item not in seen_items]

    if not available_items:
        seen_items = set()
        available_items = items_list
        if not available_items:
            return "Извините, данные для этой категории закончились и не были перезагружены."

    chosen_item = random.choice(available_items)
    seen_items.add(chosen_item)
    context.user_data[memory_key] = seen_items
    return chosen_item


# --- Вспомогательные функции для игр ---
def clear_game_state(context: ContextTypes.DEFAULT_TYPE):
    """Очищает состояние текущей игры для пользователя."""
    active_game = context.user_data.pop('active_game', None)
    keys_to_pop = ['guess_number_data', 'cities_data', 'hangman_data', 'wordle_data']
    for key in keys_to_pop:
        context.user_data.pop(key, None)
    logger.info(f"Очищено состояние игры: {active_game} для пользователя {context._user_id or context._chat_id}")
    return active_game


def get_game_over_keyboard(game_callback_data_restart: str) -> InlineKeyboardMarkup:
    """Возвращает клавиатуру для окончания игры."""
    keyboard = [
        [InlineKeyboardButton("Сыграть еще раз", callback_data=game_callback_data_restart)],
        [InlineKeyboardButton("Меню игр 🎮", callback_data="show_game_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


# --- Команды и обработчики кнопок главного меню ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение и основную клавиатуру."""
    user = update.effective_user
    clear_game_state(context)
    keyboard = [
        ["Анекдот 😂", "Факт 💡"],
        ["Игры 🎮"],
        ["Помощь ❓"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_html(
        rf"Привет, {user.mention_html()}! Я твой бот для развлечений. Чем займемся?"
        "\nЕсли ты был в игре, она остановлена.",
        reply_markup=reply_markup,
    )


async def help_command_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет список команд (действие)."""
    help_text = (
        "<b>Основные команды (также доступны через кнопки):</b>\n"
        "/start - Перезапустить бота и показать главное меню\n"
        "Помощь - Показать это сообщение\n"
        "Анекдот - Рассказать анекдот\n"
        "Факт - Рассказать интересный факт\n"
        "Игры - Показать меню игр\n"
        "/stop_game - Остановить текущую игру\n\n"
        "<b>Игры (доступны через меню 'Игры' или прямыми командами):</b>\n"
        "/guess_number - Игра 'Угадай число'\n"
        "/rps - Игра 'Камень, Ножницы, Бумага'\n"
        "/cities - Игра 'Города'\n"
        "/hangman - Игра 'Виселица'\n"
        "/wordle - Игра 'Wordle' (угадай слово из 5 букв)"
    )
    await update.message.reply_html(help_text)


async def joke_command_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет случайный анекдот (действие)."""
    await update.message.reply_text(get_random_item_with_memory(ALL_JOKES, "seen_jokes", context))


async def fact_command_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет случайный факт (действие)."""
    await update.message.reply_text(get_random_item_with_memory(ALL_FACTS, "seen_facts", context))


async def game_menu_command_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню с выбором игр (действие)."""
    clear_game_state(context)
    keyboard = [
        [InlineKeyboardButton("🎲 Угадай число", callback_data="game_start_guess_number")],
        [InlineKeyboardButton("🗿✂️📜 КНБ", callback_data="game_start_rps")],
        [InlineKeyboardButton("🏙️ Города", callback_data="game_start_cities")],
        [InlineKeyboardButton("🪓🦑 Виселица", callback_data="game_start_hangman")],
        [InlineKeyboardButton("🟩🟨 Wordle", callback_data="game_start_wordle")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message_text = "Выбери игру:"
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text=message_text, reply_markup=reply_markup)
        except Exception as e:
            logger.info(f"Не удалось изменить сообщение для game_menu: {e}. Возможно, оно идентично.")
        await update.callback_query.answer()
    else:
        await update.message.reply_text(message_text, reply_markup=reply_markup)


async def stop_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Останавливает текущую активную игру."""
    stopped_game = clear_game_state(context)
    if stopped_game:
        await update.message.reply_text(f"Игра '{stopped_game}' остановлена. Выбери что-нибудь из меню.")
    else:
        await update.message.reply_text("Сейчас нет активных игр для остановки.")


# --- Игра "Угадай число" ---
async def start_guess_number_game(update: Update, context: ContextTypes.DEFAULT_TYPE, from_command=False) -> None:
    clear_game_state(context)
    chat_id = update.effective_chat.id
    target_number = random.randint(1, 100)
    context.user_data['active_game'] = 'guess_number'
    context.user_data['guess_number_data'] = {
        "target_number": target_number,
        "attempts": 0,
        "max_attempts": 7
    }
    logger.info(f"Чат {chat_id}: Начата игра 'Угадай число'. Загадано: {target_number}")
    message_text = ("Я загадал число от 1 до 100. Попробуй угадать! У тебя 7 попыток.\n"
                    "Отправь мне число. Для выхода введите /stop_game")

    if from_command:
        await update.message.reply_text(message_text)
    elif update.callback_query:
        # Для игр, которые не используют Markdown для стартового сообщения, можно не экранировать
        await update.callback_query.edit_message_text(text="Запускаю 'Угадай число'")
        await update.callback_query.message.reply_text(message_text)
        await update.callback_query.answer()


async def handle_guess_number_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает попытку угадать число."""
    game_data = context.user_data.get('guess_number_data')
    if not game_data:
        await update.message.reply_text("Ошибка: не найдено данных игры. Попробуйте начать заново: /guess_number")
        clear_game_state(context)
        return

    try:
        guess = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Пожалуйста, отправь число.")
        return

    game_data["attempts"] += 1
    target = game_data["target_number"]
    attempts_left = game_data["max_attempts"] - game_data["attempts"]
    reply_markup = None
    message = ""

    if guess == target:
        message = f"🎉 Поздравляю! Ты угадал число {target} за {game_data['attempts']} попыток!"
        reply_markup = get_game_over_keyboard("game_start_guess_number")
        clear_game_state(context)
    elif attempts_left <= 0:
        message = f"Увы, попытки закончились! Я загадал число {target}."
        reply_markup = get_game_over_keyboard("game_start_guess_number")
        clear_game_state(context)
    elif guess < target:
        message = f"Мое число больше. Осталось попыток: {attempts_left}"
    else:  # guess > target
        message = f"Мое число меньше. Осталось попыток: {attempts_left}"

    await update.message.reply_text(message, reply_markup=reply_markup)


# --- Игра "Камень, Ножницы, Бумага" ---
async def start_rps_game(update: Update, context: ContextTypes.DEFAULT_TYPE, from_command=False) -> None:
    clear_game_state(context)
    keyboard = [
        [
            InlineKeyboardButton("Камень 🗿", callback_data="rps_choice_камень"),
            InlineKeyboardButton("Ножницы ✂️", callback_data="rps_choice_ножницы"),
            InlineKeyboardButton("Бумага 📜", callback_data="rps_choice_бумага"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message_text = "Твой ход! Выбирай:"

    if from_command:
        await update.message.reply_text(message_text, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text=message_text, reply_markup=reply_markup)
        await update.callback_query.answer()


async def handle_rps_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_choice = query.data.split("_")[2]
    bot_choice = random.choice(RPS_CHOICES)

    result_text = f"Ты выбрал: {user_choice.capitalize()}\nЯ выбрал: {bot_choice.capitalize()}\n\n"

    if user_choice == bot_choice:
        result_text += "🤝 Ничья!"
    elif (user_choice == "камень" and bot_choice == "ножницы") or \
            (user_choice == "ножницы" and bot_choice == "бумага") or \
            (user_choice == "бумага" and bot_choice == "камень"):
        result_text += "🥳 Ты победил!"
    else:
        result_text += "😔 Я победил!"

    reply_markup = get_game_over_keyboard("game_start_rps")
    await query.edit_message_text(text=result_text, reply_markup=reply_markup)


# --- Игра "Города" ---
async def start_cities_game(update: Update, context: ContextTypes.DEFAULT_TYPE, from_command=False) -> None:
    clear_game_state(context)
    context.user_data['active_game'] = 'cities'
    context.user_data['cities_data'] = {
        "used_cities": set(),
        "current_letter": None,
        "bot_last_city": None
    }
    if not ALL_CITIES:
        msg = "Список городов пуст. Не могу начать игру."
        if from_command:
            await update.message.reply_text(msg)
        elif update.callback_query:
            await update.callback_query.edit_message_text(text=msg)
            await update.callback_query.answer()
        return

    first_city = random.choice(ALL_CITIES)
    context.user_data['cities_data']['used_cities'].add(first_city)

    last_char_for_next_turn = first_city[-1]
    if last_char_for_next_turn in ['ь', 'ъ', 'ы']:
        if len(first_city) > 1:
            last_char_for_next_turn = first_city[-2]
        else:
            await update.message.reply_text("Необычный первый город, не могу определить букву для хода.")
            return

    context.user_data['cities_data']['current_letter'] = last_char_for_next_turn
    context.user_data['cities_data']['bot_last_city'] = first_city

    message_text = (f"Начинаем игру в Города! Я начну.\nМой город: <b>{first_city.capitalize()}</b>.\n"
                    f"Тебе на букву '<b>{last_char_for_next_turn.upper()}</b>'.\n"
                    "Отправь свой город. Для выхода введите /stop_game")

    if from_command:
        await update.message.reply_text(message_text, parse_mode=ParseMode.HTML)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text="Запускаю 'Города'")
        await update.callback_query.message.reply_text(message_text, parse_mode=ParseMode.HTML)
        await update.callback_query.answer()


async def handle_cities_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    game_data = context.user_data.get('cities_data')
    if not game_data:
        await update.message.reply_text("Ошибка: не найдено данных игры. Попробуйте начать заново: /cities")
        clear_game_state(context)
        return

    user_city = update.message.text.lower().strip()
    reply_markup = None

    if not user_city:
        await update.message.reply_text("Название города не может быть пустым. Попробуй еще раз.")
        return

    if user_city not in ALL_CITIES:
        await update.message.reply_text(
            f"Я не знаю города '{user_city.capitalize()}'. Попробуй другой или проверь правописание.")
        return

    if user_city in game_data["used_cities"]:
        await update.message.reply_text(f"Город '{user_city.capitalize()}' уже был. Давай другой!")
        return

    expected_letter = game_data["current_letter"]
    if not user_city.startswith(expected_letter):
        await update.message.reply_text(
            f"Твой город должен начинаться на букву '<b>{expected_letter.upper()}</b>'. "
            f"Мой последний город был <b>{game_data['bot_last_city'].capitalize()}</b>. Попробуй еще раз.",
            parse_mode=ParseMode.HTML
        )
        return

    game_data["used_cities"].add(user_city)

    bot_needed_letter = user_city[-1]
    if bot_needed_letter in ['ь', 'ъ', 'ы']:
        if len(user_city) > 1:
            bot_needed_letter = user_city[-2]
        else:
            message = f"Интересный город! Я не могу придумать город на '<b>{bot_needed_letter.upper()}</b>'. Ты победил! 🎉"
            reply_markup = get_game_over_keyboard("game_start_cities")
            clear_game_state(context)
            await update.message.reply_html(message, reply_markup=reply_markup)
            return

    possible_bot_cities = [
        city for city in ALL_CITIES
        if city.startswith(bot_needed_letter) and city not in game_data["used_cities"]
    ]

    if not possible_bot_cities:
        message = f"Ого! Я не могу придумать город на '<b>{bot_needed_letter.upper()}</b>'. Ты победил! 🎉"
        reply_markup = get_game_over_keyboard("game_start_cities")
        clear_game_state(context)
        await update.message.reply_html(message, reply_markup=reply_markup)
        return

    bot_city = random.choice(possible_bot_cities)
    game_data["used_cities"].add(bot_city)
    game_data["bot_last_city"] = bot_city

    next_user_letter = bot_city[-1]
    if next_user_letter in ['ь', 'ъ', 'ы']:
        if len(bot_city) > 1:
            next_user_letter = bot_city[-2]
        else:
            message = f"Мой город: {bot_city.capitalize()}. Кажется, я не могу продолжить. Ты победил! 🎉"
            reply_markup = get_game_over_keyboard("game_start_cities")
            clear_game_state(context)
            await update.message.reply_html(message, reply_markup=reply_markup)
            return

    game_data["current_letter"] = next_user_letter
    await update.message.reply_text(
        f"Отлично! Мой город: <b>{bot_city.capitalize()}</b>.\n"
        f"Тебе на букву '<b>{next_user_letter.upper()}</b>'.",
        parse_mode=ParseMode.HTML
    )


# --- Игра "Виселица" ---
def get_hangman_display(word, guessed_letters):
    display = ""
    for letter in word:
        if letter in guessed_letters:
            display += letter + " "
        else:
            display += "_ "
    return display.strip()


async def start_hangman_game(update: Update, context: ContextTypes.DEFAULT_TYPE, from_command=False) -> None:
    clear_game_state(context)
    if not ALL_HANGMAN_WORDS:
        msg = "Список слов для Виселицы пуст. Не могу начать игру."
        if from_command:
            await update.message.reply_text(msg)
        elif update.callback_query:
            await update.callback_query.edit_message_text(text=msg)
            await update.callback_query.answer()
        return

    target_word = random.choice(ALL_HANGMAN_WORDS)
    context.user_data['active_game'] = 'hangman'
    context.user_data['hangman_data'] = {
        "word": target_word,
        "guessed_letters": set(),
        "wrong_attempts": 0,
        "max_wrong_attempts": len(HANGMAN_STAGES) - 1
    }

    logger.info(f"Чат {update.effective_chat.id}: Начата игра 'Виселица'. Загадано: {target_word}")

    display_word_str = get_hangman_display(target_word, set())

    intro_text = escape_markdown_v2("Играем в Виселицу!")  # "!" экранируется
    hangman_art = HANGMAN_STAGES[0]
    word_prompt = escape_markdown_v2(f"Слово: ({len(target_word)} букв)")
    instruction_text = escape_markdown_v2("Отправь букву (кириллица). Для выхода введите /stop_game")

    message_text = (
        f"{intro_text}\n"
        f"```\n{hangman_art}\n```\n"
        f"{word_prompt} `{escape_markdown_v2(display_word_str)}`\n"
        f"{instruction_text}"
    )

    if from_command:
        await update.message.reply_text(message_text, parse_mode=ParseMode.MARKDOWN_V2)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text=escape_markdown_v2("Запускаю 'Виселицу'"),
                                                      parse_mode=ParseMode.MARKDOWN_V2)
        await update.callback_query.message.reply_text(message_text, parse_mode=ParseMode.MARKDOWN_V2)
        await update.callback_query.answer()


async def handle_hangman_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    game_data = context.user_data.get('hangman_data')
    if not game_data:
        await update.message.reply_text("Ошибка: не найдено данных игры. Попробуйте начать заново: /hangman")
        clear_game_state(context)
        return

    guess = update.message.text.lower().strip()
    reply_markup = None
    message = ""

    if not guess or not guess.isalpha() or len(guess) != 1:
        await update.message.reply_text(escape_markdown_v2("Пожалуйста, отправь одну букву (кириллица)."),
                                        parse_mode=ParseMode.MARKDOWN_V2)
        return

    if guess in game_data["guessed_letters"]:
        await update.message.reply_text(escape_markdown_v2(f"Букву '{guess.upper()}' ты уже называл. Попробуй другую."),
                                        parse_mode=ParseMode.MARKDOWN_V2)
        return

    game_data["guessed_letters"].add(guess)
    target_word = game_data["word"]
    display_word_str = get_hangman_display(target_word, game_data["guessed_letters"])

    guessed_letters_str = escape_markdown_v2(", ".join(sorted(list(game_data["guessed_letters"]))))

    if guess in target_word:
        hangman_art_current = HANGMAN_STAGES[game_data["wrong_attempts"]]
        if "_" not in display_word_str:
            win_text_part1 = escape_markdown_v2(f"🎉 Поздравляю! Ты угадал слово: ")
            win_text_part2 = f"**{escape_markdown_v2(target_word.upper())}**"
            win_text_part3 = escape_markdown_v2("!")
            win_text = win_text_part1 + win_text_part2 + win_text_part3

            message = (
                f"```\n{hangman_art_current}\n```\n"
                f"{win_text}"
            )
            reply_markup = get_game_over_keyboard("game_start_hangman")
            clear_game_state(context)
        else:
            correct_guess_text = escape_markdown_v2("Есть такая буква!")  # "!" экранируется
            message = (
                f"{correct_guess_text}\n"
                f"```\n{hangman_art_current}\n```\n"
                f"{escape_markdown_v2('Слово:')} `{escape_markdown_v2(display_word_str)}`\n"
                f"{escape_markdown_v2(f'Ошибок: {game_data["wrong_attempts"]}/{game_data["max_wrong_attempts"]}')}\n"
                f"{escape_markdown_v2('Названные буквы:')} {guessed_letters_str}"
            )
    else:
        game_data["wrong_attempts"] += 1
        hangman_art_current = HANGMAN_STAGES[game_data["wrong_attempts"]]
        if game_data["wrong_attempts"] >= game_data["max_wrong_attempts"]:
            lose_text_part1 = escape_markdown_v2(f"😔 Увы, ты проиграл. Загаданное слово было: ")
            lose_text_part2 = f"**{escape_markdown_v2(target_word.upper())}**"
            lose_text_part3 = escape_markdown_v2(".")
            lose_text = lose_text_part1 + lose_text_part2 + lose_text_part3

            message = (
                f"```\n{hangman_art_current}\n```\n"
                f"{lose_text}"
            )
            reply_markup = get_game_over_keyboard("game_start_hangman")
            clear_game_state(context)
        else:
            wrong_guess_text = escape_markdown_v2("Упс, такой буквы нет.")  # "." экранируется
            message = (
                f"{wrong_guess_text}\n"
                f"```\n{hangman_art_current}\n```\n"
                f"{escape_markdown_v2('Слово:')} `{escape_markdown_v2(display_word_str)}`\n"
                f"{escape_markdown_v2(f'Ошибок: {game_data["wrong_attempts"]}/{game_data["max_wrong_attempts"]}')}\n"
                f"{escape_markdown_v2('Названные буквы:')} {guessed_letters_str}"
            )

    await update.message.reply_text(message, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)


# --- Игра "Wordle" ---
def get_wordle_feedback(guess, target):
    feedback = ["⬜"] * WORDLE_WORD_LENGTH
    target_list = list(target)
    guess_list = list(guess)

    for i in range(WORDLE_WORD_LENGTH):
        if guess_list[i] == target_list[i]:
            feedback[i] = "🟩"
            target_list[i] = None
            guess_list[i] = "#"

    for i in range(WORDLE_WORD_LENGTH):
        if guess_list[i] != "#":
            if guess_list[i] in target_list:
                feedback[i] = "🟨"
                target_list[target_list.index(guess_list[i])] = None
    return "".join(feedback)


def format_wordle_alphabet_status(letter_statuses):
    """Форматирует статус букв алфавита для Wordle с экранированием."""
    # Буквы экранируются перед добавлением в список, join их не изменит
    greens = sorted([l.upper() for l, s in letter_statuses.items() if s == 'green'])
    yellows = sorted([l.upper() for l, s in letter_statuses.items() if s == 'yellow'])
    grays = sorted([l.upper() for l, s in letter_statuses.items() if s == 'gray'])

    status_parts = []
    # Экранируем строки перед форматированием f-строки
    if greens: status_parts.append(f"🟩 {escape_markdown_v2('Зеленые')}: {escape_markdown_v2(', '.join(greens))}")
    if yellows: status_parts.append(f"🟨 {escape_markdown_v2('Желтые')}: {escape_markdown_v2(', '.join(yellows))}")
    if grays: status_parts.append(f"⬜ {escape_markdown_v2('Серые')}: {escape_markdown_v2(', '.join(grays))}")

    if not status_parts:
        return escape_markdown_v2("Статус букв: Пока не угадано.")
    return escape_markdown_v2("Статус букв:\n") + "\n".join(
        status_parts)  # status_parts уже содержат экранированные строки


async def start_wordle_game(update: Update, context: ContextTypes.DEFAULT_TYPE, from_command=False) -> None:
    clear_game_state(context)
    if not ALL_WORDLE_WORDS:
        msg = f"Список слов для Wordle (длиной {WORDLE_WORD_LENGTH}) пуст. Не могу начать игру."
        if from_command:
            await update.message.reply_text(msg)
        elif update.callback_query:
            await update.callback_query.edit_message_text(text=msg)
            await update.callback_query.answer()
        return

    target_word = random.choice(ALL_WORDLE_WORDS)
    context.user_data['active_game'] = 'wordle'
    context.user_data['wordle_data'] = {
        "word": target_word,
        "guesses_history": [],
        "attempts": 0,
        "letter_statuses": {letter: "not_guessed" for letter in RUSSIAN_ALPHABET}
    }
    logger.info(f"Чат {update.effective_chat.id}: Начата игра 'Wordle'. Загадано: {target_word}")

    title_text = escape_markdown_v2(
        f"Играем в Wordle! Я загадал слово из {WORDLE_WORD_LENGTH} букв.")  # "!" экранируется
    attempts_text = escape_markdown_v2(f"У тебя {WORDLE_MAX_GUESSES} попыток.")  # "." экранируется
    instruction_text = escape_markdown_v2(
        "Отправь свое слово (кириллица). Для выхода введите /stop_game")  # "." экранируется
    legend_text = escape_markdown_v2(
        "🟩 - буква на верном месте\n"
        "🟨 - буква есть в слове, но на другом месте\n"
        "⬜ - такой буквы нет в слове"
    )  # "-" экранируется
    message_text = (
        f"{title_text}\n"
        f"{attempts_text}\n"
        f"{instruction_text}\n\n"
        f"{legend_text}"
    )

    if from_command:
        await update.message.reply_text(message_text, parse_mode=ParseMode.MARKDOWN_V2)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text=escape_markdown_v2("Запускаю 'Wordle'"),
                                                      parse_mode=ParseMode.MARKDOWN_V2)
        await update.callback_query.message.reply_text(message_text, parse_mode=ParseMode.MARKDOWN_V2)
        await update.callback_query.answer()


async def handle_wordle_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    game_data = context.user_data.get('wordle_data')
    if not game_data:
        await update.message.reply_text("Ошибка: не найдено данных игры. Попробуйте начать заново: /wordle")
        clear_game_state(context)
        return

    guess = update.message.text.lower().strip()
    reply_markup = None

    if len(guess) != WORDLE_WORD_LENGTH or not guess.isalpha():
        await update.message.reply_text(
            escape_markdown_v2(f"Пожалуйста, отправь слово из {WORDLE_WORD_LENGTH} букв (кириллица)."),
            parse_mode=ParseMode.MARKDOWN_V2)
        return

    game_data["attempts"] += 1
    target_word = game_data["word"]
    feedback = get_wordle_feedback(guess, target_word)
    # Экранируем слово пользователя перед добавлением в историю
    game_data["guesses_history"].append((escape_markdown_v2(guess.upper()), feedback))

    for i, char_guess in enumerate(guess):
        current_char_status = game_data["letter_statuses"].get(char_guess, "not_guessed")
        feedback_char_status = "gray"
        if feedback[i] == "🟩":
            feedback_char_status = "green"
        elif feedback[i] == "🟨":
            feedback_char_status = "yellow"

        if feedback_char_status == "green":
            game_data["letter_statuses"][char_guess] = "green"
        elif feedback_char_status == "yellow" and current_char_status != "green":
            game_data["letter_statuses"][char_guess] = "yellow"
        elif feedback_char_status == "gray" and current_char_status not in ["green", "yellow"]:
            game_data["letter_statuses"][char_guess] = "gray"

    alphabet_status_text = format_wordle_alphabet_status(game_data["letter_statuses"])
    history_text = "\n".join([f"{g_word}: {fb}" for g_word, fb in game_data["guesses_history"]])

    full_message_parts = [escape_markdown_v2(f"История попыток:\n") + f"{history_text}\n"]
    full_message_parts.append(f"{alphabet_status_text}\n")

    if guess == target_word:
        # ИСПРАВЛЕНО ЗДЕСЬ: экранируем каждую часть отдельно
        win_part1 = escape_markdown_v2(f"🎉 Поздравляю! Ты угадал слово ")
        win_part2 = f"**{escape_markdown_v2(target_word.upper())}**"
        win_part3 = escape_markdown_v2(f" за {game_data['attempts']} попыток!")  # "!" экранируется
        full_message_parts.append(win_part1 + win_part2 + win_part3)
        reply_markup = get_game_over_keyboard("game_start_wordle")
        clear_game_state(context)
    elif game_data["attempts"] >= WORDLE_MAX_GUESSES:
        lose_part1 = escape_markdown_v2(f"😔 Увы, попытки закончились. Загаданное слово было: ")
        lose_part2 = f"**{escape_markdown_v2(target_word.upper())}**"
        lose_part3 = escape_markdown_v2(".")  # "." экранируется
        full_message_parts.append(lose_part1 + lose_part2 + lose_part3)
        reply_markup = get_game_over_keyboard("game_start_wordle")
        clear_game_state(context)
    else:
        full_message_parts.append(escape_markdown_v2(
            f"Попытка {game_data['attempts']}/{WORDLE_MAX_GUESSES}. Введи следующее слово."))

    await update.message.reply_text(
        "\n".join(full_message_parts),
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN_V2
    )


# --- Обработчик текстовых сообщений для игр ---
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    active_game = context.user_data.get('active_game')

    if update.message and update.message.text:
        text = update.message.text
        if text == "Анекдот 😂":
            await joke_command_action(update, context)
            return
        if text == "Факт 💡":
            await fact_command_action(update, context)
            return
        if text == "Игры 🎮":
            await game_menu_command_action(update, context)
            return
        if text == "Помощь ❓":
            await help_command_action(update, context)
            return

    if active_game and update.message and update.message.text:
        logger.info(f"Обработка текста для активной игры: {active_game} от пользователя {update.effective_user.id}")
        if active_game == 'guess_number':
            await handle_guess_number_input(update, context)
        elif active_game == 'cities':
            await handle_cities_input(update, context)
        elif active_game == 'hangman':
            await handle_hangman_input(update, context)
        elif active_game == 'wordle':
            await handle_wordle_input(update, context)


# --- Обработчик инлайн-кнопок ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data
    logger.info(f"Получен CallbackQuery: {data}")

    if data == "game_start_guess_number":
        await start_guess_number_game(update, context)
    elif data == "game_start_rps":
        await start_rps_game(update, context)
    elif data.startswith("rps_choice_"):
        await handle_rps_choice(update, context)
    elif data == "game_start_cities":
        await start_cities_game(update, context)
    elif data == "game_start_hangman":
        await start_hangman_game(update, context)
    elif data == "game_start_wordle":
        await start_wordle_game(update, context)
    elif data == "show_game_menu":
        await game_menu_command_action(update, context)
    else:
        # Важно ответить на query, даже если действие неизвестно, чтобы убрать "часики" с кнопки
        await query.answer("Неизвестное действие кнопки.")
        logger.warning(f"Необработанные callback_data: {data}")


def main() -> None:
    """Запуск бота."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        logger.info(f"Создана директория data: {DATA_DIR}")

    initialize_data()

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command_action))
    application.add_handler(CommandHandler("stop_game", stop_game_command))
    application.add_handler(
        CommandHandler("guess_number", lambda u, c: start_guess_number_game(u, c, from_command=True)))
    application.add_handler(CommandHandler("rps", lambda u, c: start_rps_game(u, c, from_command=True)))
    application.add_handler(CommandHandler("cities", lambda u, c: start_cities_game(u, c, from_command=True)))
    application.add_handler(CommandHandler("hangman", lambda u, c: start_hangman_game(u, c, from_command=True)))
    application.add_handler(CommandHandler("wordle", lambda u, c: start_wordle_game(u, c, from_command=True)))
    application.add_handler(CommandHandler("joke", joke_command_action))
    application.add_handler(CommandHandler("fact", fact_command_action))
    application.add_handler(CommandHandler("game_menu", game_menu_command_action))

    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    logger.info("Бот запускается...")
    application.run_polling()
    logger.info("Бот остановлен.")


if __name__ == "__main__":
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or not BOT_TOKEN:
        logger.error("BOT_TOKEN не установлен. Пожалуйста, вставьте ваш токен в переменную BOT_TOKEN.")
    else:
        main()