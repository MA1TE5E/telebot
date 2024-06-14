import os
import logging
import telebot
import csv
from telebot import types
import time
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Вставьте сюда токен своего бота
API_TOKEN = '6885524246:AAHnUb7W71CbTofNMw4YrnyLb-bnloBoc4I'
bot = telebot.TeleBot(API_TOKEN)

# Папки для сохранения изображений
IMAGE_FOLDER = 'images'
ANNOTATED_IMAGE_FOLDER = 'annotated_images'
CSV_FILE_PATH = 'weld_defects.csv'
WEB_APP_URL = 'http://65.108.250.169/draw.html?image=images/'  # Убедитесь, что путь соответствует вашему серверу

# Google Drive API настройки
SERVICE_ACCOUNT_FILE = 'tgbot2-426018-f1f15b697496.json'
SCOPES = ['https://www.googleapis.com/auth/drive.file']

credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=credentials, cache_discovery=False)

# Идентификаторы папок на Google Drive
IMAGE_FOLDER_ID = '1qWzjpJpked8OuEa-AUSWKs0UBijO4ak3'
ANNOTATED_IMAGE_FOLDER_ID = '1BvuP9-DEea-F4Y6Hk_s5UPNLzV5wHzbf'
CSV_FOLDER_ID = '1P7y9VVaMP2Yhv2Aunqnep3CvmyqZbBO7'

# Убедимся, что папки существуют
os.makedirs(IMAGE_FOLDER, exist_ok=True)
os.makedirs(ANNOTATED_IMAGE_FOLDER, exist_ok=True)

# Убедимся, что CSV файл существует
if not os.path.exists(CSV_FILE_PATH):
    with open(CSV_FILE_PATH, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = [
            'ФИО',
            'Должность',
            'Вид сварки',
            'Тип покрытия электрода',
            'Марка электрода',
            'Диаметр электрода',
            'Тип соединения',
            'Пространственное положение сварки',
            'Сила тока',
            'Ссылка на изображение',
            'Ссылка на аннотированное изображение',
            'Дефекты'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

# Хранилище состояний и данных пользователей
user_data = {}

# Состояния для процесса логина и получения информации о сварке
STATE_NONE = 0
STATE_WAITING_FOR_FIO = 1
STATE_WAITING_FOR_POSITION = 2
STATE_WAITING_FOR_COMMAND = 3
STATE_WAITING_FOR_SET_WELDING_PARAMS = 4
STATE_WAITING_FOR_IMAGE = 5
STATE_WAITING_FOR_DRAWN_IMAGE = 6
STATE_WAITING_FOR_DEFECT_DETAILS = 7

# Состояния для установки параметров сварки
STATE_WAITING_FOR_WELDING_TYPE = 10
STATE_WAITING_FOR_COVERAGE_TYPE = 11
STATE_WAITING_FOR_ELECTRODE_BRAND = 12
STATE_WAITING_FOR_ELECTRODE_DIAMETER = 13
STATE_WAITING_FOR_CONNECTION_TYPE = 14
STATE_WAITING_FOR_WELDING_POSITION = 15
STATE_WAITING_FOR_CURRENT = 16

# Функция для создания главного меню
def create_main_menu():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton("📙 About"),
        types.KeyboardButton("📄 Types"),
        types.KeyboardButton("🆘 Help"),
        types.KeyboardButton("⁉️ FAQ"),
        types.KeyboardButton("🗾 Отправить изображение"),
        types.KeyboardButton("⚙️ Установить параметры сварки")
    )
    return markup

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_data[message.chat.id] = {"state": STATE_WAITING_FOR_FIO}
    bot.send_message(message.chat.id, "Добро пожаловать! Пожалуйста, введите ваше ФИО:")
    logger.info(f"User {message.chat.id} started the bot and is asked for FIO.")

# Обработчик для кнопок меню
@bot.message_handler(func=lambda message: message.text in ["📙 About", "📄 Types", "🆘 Help", "⁉️ FAQ", "🗾 Отправить изображение", "⚙️ Установить параметры сварки"])
def handle_menu_buttons(message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        bot.send_message(chat_id, "Пожалуйста, начните с команды /start")
        return

    if message.text == "📙 About":
        bot.send_message(chat_id,
                         "🤖 *WeldDefectBot* - это телеграм-бот, разработанный для сбора изображений сварных соединений. "
                         "С его помощью вы можете быстро обозначить все дефекты, которые есть на изображении.",
                         parse_mode="Markdown")
    elif message.text == "📄 Types":
        bot.send_message(chat_id, "Вы сможете обозначить такие дефекты как:\n"
                                  "1. Ассиметрия углового шва\n"
                                  "2. Бризги металла\n"
                                  "3. Волкрамовое включение\n"
                                  "4. Включение\n"
                                  "5. Включение одиночное\n"
                                  "6. Вогнутость корня шва\n"
                                  "7. Выпуклость (превышение проплавления) корня шва\n"
                                  "8. Глубокий валик\n"
                                  "9. Кратерная трещина. Трещина в кратере\n"
                                  "10. Кратер. Усадочная раковина сварного шва\n"
                                  "11. Линия пор. Линейная пористость\n"
                                  "12. Максимальная ширина включения\n"
                                  "13. Максимальный размер включения\n"
                                  "14. Местное превышение проплава\n"
                                  "15. Неплавящийся наплыв\n"
                                  "16. Наплыв\n"
                                  "17. Неправильный профиль сварного шва\n"
                                  "18. Непровар. Неполный провар\n"
                                  "19. Несполошность\n"
                                  "20. Оксиальное включение\n"
                                  "21. Отслоение\n"
                                  "22. Плохое возобновление шва\n"
                                  "23. Подрез\n"
                                  "24. Поры\n"
                                  "25. Превышение выпуклости\n"
                                  "26. Превышение усиления сварного шва\n"
                                  "27. Прерывистая линия\n"
                                  "28. Продольная трещина сварного соединения. Продольная трещина\n"
                                  "29. Прохождение сварного шва\n"
                                  "30. Радиационная трещина\n"
                                  "31. Разветвленная трещина сварного соединения. Разветвленная трещина\n"
                                  "32. Скопление включений\n"
                                  "33. Свищ в сварном шве\n"
                                  "34. Трещина поперечная\n"
                                  "35. Трещина сварного соединения. Трещина\n"
                                  "36. Углубление (западание) между валиками шва\n"
                                  "37. Усадочные раковины\n"
                                  "38. Флюсовое включение\n"
                                  "39. Шлаковое включение сварного шва. Шлаковое включение\n"
                                  "40. Шлаковое включение\n"
                                  "41. Неровная поверхность шва\n"
                                  "42. Неровная ширина шва\n",
                         parse_mode="Markdown")
    elif message.text == "🆘 Help":
        bot.send_message(chat_id,
                         "Просто отправь мне фотографию сварного шва. Я сохраню её и скину ссылку на аннотацию. "
                         "Вы можете аннотировать изображение дефектами, и я сохраню эти аннотации для последующего анализа.\n\n"
                         "Как пользоваться ботом:\n"
                         "0. Установите параметры сварки, которые использовались на сварном шве.\n"
                         "1. Отправьте фотографию сварного шва.\n"
                         "2. Перейдите по ссылке для аннотирования изображения.\n"
                         "3. Отправьте аннотированное изображение обратно в бот.\n"
                         "4. Укажите названия всех дефектов и их координаты.\n"
                         "5. Все данные будут сохранены в CSV файл и загружены на Google Drive.",
                         parse_mode="Markdown")
    elif message.text == "⁉️ FAQ":
        bot.send_message(chat_id,
                         "❓ *Часто задаваемые вопросы*\n\n"
                         "1. Какой тип фотографий лучше всего подходит для анализа?\n"
                         "Рекомендуется использовать фотографии с высоким разрешением, на которых четко видны сварные швы.\n\n"
                         "2. Как сохранить аннотированное изображение?\n"
                         "После аннотирования изображения, нажмите кнопку 'Сохранить' и отправьте сохраненное изображение обратно в бот.\n\n"
                         "3. Как получить данные в CSV формате?\n"
                         "Все данные автоматически сохраняются в CSV файл, который загружается на ваш Google Drive.",
                         parse_mode="Markdown")
    elif message.text == "🗾 Отправить изображение":
        if "welding_params" in user_data[chat_id]:
            user_data[chat_id]["state"] = STATE_WAITING_FOR_IMAGE
            bot.send_message(chat_id, "Теперь отправьте изображение:")
        else:
            user_data[chat_id]["state"] = STATE_WAITING_FOR_SET_WELDING_PARAMS
            bot.send_message(chat_id, "Пожалуйста, сначала установите параметры сварки.")
    elif message.text == "⚙️ Установить параметры сварки":
        user_data[chat_id]["state"] = STATE_WAITING_FOR_WELDING_TYPE
        bot.send_message(chat_id, "Вид сварки:")
        logger.info(f"User {chat_id} is asked for welding type.")

# Обработчик для текстовых сообщений
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        bot.send_message(chat_id, "Пожалуйста, начните с команды /start")
        return

    state = user_data[chat_id].get("state", STATE_NONE)

    if state == STATE_WAITING_FOR_FIO:
        user_data[chat_id]["fio"] = message.text
        user_data[chat_id]["state"] = STATE_WAITING_FOR_POSITION
        bot.send_message(chat_id, "Введите вашу должность:")
        logger.info(f"User {message.chat.id} provided FIO: {message.text}.")
    elif state == STATE_WAITING_FOR_POSITION:
        user_data[chat_id]["position"] = message.text
        user_data[chat_id]["state"] = STATE_WAITING_FOR_COMMAND
        bot.send_message(chat_id, "Регистрация завершена. Выберите опцию из меню ниже:", reply_markup=create_main_menu())
        logger.info(f"User {message.chat.id} provided position: {message.text}.")
    elif state == STATE_WAITING_FOR_WELDING_TYPE:
        user_data[chat_id].setdefault("welding_params", {})["welding_type"] = message.text
        user_data[chat_id]["state"] = STATE_WAITING_FOR_COVERAGE_TYPE
        bot.send_message(chat_id, "Тип покрытия электрода:")
        logger.info(f"User {message.chat.id} provided welding type: {message.text}.")
    elif state == STATE_WAITING_FOR_COVERAGE_TYPE:
        user_data[chat_id]["welding_params"]["coverage_type"] = message.text
        user_data[chat_id]["state"] = STATE_WAITING_FOR_ELECTRODE_BRAND
        bot.send_message(chat_id, "Марка электрода:")
        logger.info(f"User {message.chat.id} provided coverage type: {message.text}.")
    elif state == STATE_WAITING_FOR_ELECTRODE_BRAND:
        user_data[chat_id]["welding_params"]["electrode_brand"] = message.text
        user_data[chat_id]["state"] = STATE_WAITING_FOR_ELECTRODE_DIAMETER
        bot.send_message(chat_id, "Диаметр электрода:")
        logger.info(f"User {message.chat.id} provided electrode brand: {message.text}.")
    elif state == STATE_WAITING_FOR_ELECTRODE_DIAMETER:
        user_data[chat_id]["welding_params"]["electrode_diameter"] = message.text
        user_data[chat_id]["state"] = STATE_WAITING_FOR_CONNECTION_TYPE
        bot.send_message(chat_id, "Тип соединения:")
        logger.info(f"User {message.chat.id} provided electrode diameter: {message.text}.")
    elif state == STATE_WAITING_FOR_CONNECTION_TYPE:
        user_data[chat_id]["welding_params"]["connection_type"] = message.text
        user_data[chat_id]["state"] = STATE_WAITING_FOR_WELDING_POSITION
        bot.send_message(chat_id, "Пространственное положение сварки:")
        logger.info(f"User {message.chat.id} provided connection type: {message.text}.")
    elif state == STATE_WAITING_FOR_WELDING_POSITION:
        user_data[chat_id]["welding_params"]["welding_position"] = message.text
        user_data[chat_id]["state"] = STATE_WAITING_FOR_CURRENT
        bot.send_message(chat_id, "Сила тока:")
        logger.info(f"User {message.chat.id} provided welding position: {message.text}.")
    elif state == STATE_WAITING_FOR_CURRENT:
        user_data[chat_id]["welding_params"]["current"] = message.text
        user_data[chat_id]["state"] = STATE_WAITING_FOR_COMMAND
        bot.send_message(chat_id, "Параметры сварки установлены. Выберите опцию из меню ниже:", reply_markup=create_main_menu())
        logger.info(f"User {message.chat.id} provided current: {message.text}.")
    elif state == STATE_WAITING_FOR_IMAGE:
        handle_image(message)
    elif state == STATE_WAITING_FOR_DEFECT_DETAILS:
        user_data[chat_id]["defects"] = message.text
        save_data_to_file(chat_id)
        bot.send_message(chat_id, "Спасибо! Все данные сохранены.")
        user_data[chat_id]["state"] = STATE_NONE

# Функция для загрузки файла на Google Drive в указанную папку
def upload_file_to_drive(file_path, file_name, mime_type, folder_id):
    file_metadata = {
        'name': file_name,
        'parents': [folder_id]
    }
    media = MediaFileUpload(file_path, mimetype=mime_type)
    file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file.get('id')

# Функция для сохранения изображения
def save_image(file_info, file_id):
    try:
        files = os.listdir(IMAGE_FOLDER)
        file_number = len(files) + 1
        file_path = os.path.join(IMAGE_FOLDER, f"{file_number}.jpg")

        downloaded_file = bot.download_file(file_info.file_path)

        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        google_drive_id = upload_file_to_drive(file_path, f"{file_number}.jpg", 'image/jpeg', IMAGE_FOLDER_ID)
        file_url = f"https://drive.google.com/file/d/{google_drive_id}/view?usp=sharing"

        logger.info(f"Image saved at path: {file_path} and uploaded to Google Drive")
        return file_path  # Вернуть локальный путь к изображению
    except Exception as e:
        logger.error(f"Error saving image: {e}")
        return None

# Обработчик для приема изображений
@bot.message_handler(content_types=['photo'])
def handle_image(message):
    chat_id = message.chat.id
    state = user_data.get(chat_id, {}).get("state", STATE_NONE)

    if state == STATE_WAITING_FOR_IMAGE:
        try:
            file_id = message.photo[-1].file_id
            file_info = bot.get_file(file_id)

            file_path = save_image(file_info, file_id)
            if file_path:
                if chat_id not in user_data:
                    user_data[chat_id] = {}
                user_data[chat_id]["image_path"] = file_path
                logger.info(f"Image path saved for user {chat_id}: {file_path}")
                print(f"DEBUG: Image path for user {chat_id} is {user_data[chat_id]['image_path']}")

                image_url = f"{WEB_APP_URL}{os.path.basename(file_path)}"
                bot.send_message(chat_id, f"Изображение получено. Перейдите по ссылке для обозначения дефектов: {image_url}")
                user_data[chat_id]["state"] = STATE_WAITING_FOR_DRAWN_IMAGE
                bot.send_message(chat_id, "Теперь отправьте аннотированное изображение.")
                logger.info(f"Image received and saved as {file_path}. User {chat_id} is asked for annotated image.")
            else:
                bot.send_message(chat_id, "Произошла ошибка при сохранении изображения.")
                logger.error(f"Failed to save image for user {chat_id}.")
        except Exception as e:
            logger.error(f"Error handling image for user {chat_id}: {e}")
            bot.send_message(chat_id, "Произошла ошибка при обработке изображения.")
    elif state == STATE_WAITING_FOR_DRAWN_IMAGE:
        handle_annotated_image(message)

# Обработчик для приема аннотированных изображений
@bot.message_handler(content_types=['document', 'photo'])
def handle_annotated_image(message):
    chat_id = message.chat.id
    state = user_data.get(chat_id, {}).get("state", STATE_NONE)

    if state != STATE_WAITING_FOR_DRAWN_IMAGE:
        bot.send_message(chat_id, "Пожалуйста, следуйте инструкциям и отправьте аннотированное изображение, когда это необходимо.")
        return

    try:
        logger.info(f"Checking for image_path for user {chat_id}")
        print(f"DEBUG: Checking for image_path for user {chat_id}")

        if 'image_path' not in user_data[chat_id]:
            bot.send_message(chat_id, "Изображение не найдено. Пожалуйста, начните сначала.")
            logger.error(f"No image path found for user {chat_id} when receiving annotated image.")
            print(f"DEBUG: No image path found for user {chat_id} in user_data")
            return

        logger.info(f"Image path for user {chat_id}: {user_data[chat_id]['image_path']}")
        print(f"DEBUG: Image path for user {chat_id}: {user_data[chat_id]['image_path']}")

        file_id = message.photo[-1].file_id if message.content_type == 'photo' else message.document.file_id
        file_info = bot.get_file(file_id)

        annotated_google_drive_url = save_annotated_image(file_info, user_data[chat_id]["image_path"])
        if annotated_google_drive_url:
            user_data[chat_id]["annotated_image_path"] = annotated_google_drive_url
            bot.send_message(chat_id, "Аннотированное изображение получено. Спасибо!")
            user_data[chat_id]["state"] = STATE_WAITING_FOR_DEFECT_DETAILS
            bot.send_message(chat_id, "Пожалуйста, введите наименования всех дефектов и их координаты:")
            logger.info(f"Annotated image received and saved as {annotated_google_drive_url} for user {chat_id}.")
        else:
            bot.send_message(chat_id, "Произошла ошибка при сохранении аннотированного изображения.")
            logger.error(f"Failed to save annotated image for user {chat_id}.")
    except Exception as e:
        logger.error(f"Error handling annotated image for user {chat_id}: {e}")
        bot.send_message(chat_id, "Произошла ошибка при обработке аннотированного изображения.")

# Функция для сохранения аннотированного изображения
def save_annotated_image(file_info, original_image_path):
    try:
        base_name = os.path.basename(original_image_path)
        name, ext = os.path.splitext(base_name)
        annotated_file_path = os.path.join(ANNOTATED_IMAGE_FOLDER, f"{name}_a{ext}")

        downloaded_file = bot.download_file(file_info.file_path)

        with open(annotated_file_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        google_drive_id = upload_file_to_drive(annotated_file_path, f"{name}_a{ext}", 'image/jpeg', ANNOTATED_IMAGE_FOLDER_ID)
        annotated_google_drive_url = f"https://drive.google.com/file/d/{google_drive_id}/view?usp=sharing"

        logger.info(f"Annotated image saved at path: {annotated_file_path} and uploaded to Google Drive")
        return annotated_google_drive_url
    except Exception as e:
        logger.error(f"Error saving annotated image: {e}")
        return None

# Функция для сохранения данных в CSV файл
def search_and_delete_existing_csv(drive_service, folder_id, file_name):
    query = f"'{folder_id}' in parents and name='{file_name}' and mimeType='text/csv'"
    results = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    items = results.get('files', [])
    if items:
        for item in items:
            drive_service.files().delete(fileId=item['id']).execute()
            logger.info(f"Deleted existing CSV file: {item['name']}")

def save_data_to_file(chat_id):
    try:
        data = user_data[chat_id]
        file_url = data.get("image_path", "N/A")
        annotated_google_drive_url = data.get("annotated_image_path", "N/A")
        welding_params = data.get("welding_params", {})
        defects = data.get("defects", "N/A")

        file_exists = os.path.isfile(CSV_FILE_PATH)

        with open(CSV_FILE_PATH, 'a', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'ФИО',
                'Должность',
                'Вид сварки',
                'Тип покрытия электрода',
                'Марка электрода',
                'Диаметр электрода',
                'Тип соединения',
                'Пространственное положение сварки',
                'Сила тока',
                'Ссылка на изображение',
                'Ссылка на аннотированное изображение',
                'Дефекты'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            if not file_exists:
                writer.writeheader()

            row = {
                'ФИО': data.get("fio", ""),
                'Должность': data.get("position", ""),
                'Вид сварки': welding_params.get("welding_type", ""),
                'Тип покрытия электрода': welding_params.get("coverage_type", ""),
                'Марка электрода': welding_params.get("electrode_brand", ""),
                'Диаметр электрода': welding_params.get("electrode_diameter", ""),
                'Тип соединения': welding_params.get("connection_type", ""),
                'Пространственное положение сварки': welding_params.get("welding_position", ""),
                'Сила тока': welding_params.get("current", ""),
                'Ссылка на изображение': file_url,
                'Ссылка на аннотированное изображение': annotated_google_drive_url,
                'Дефекты': defects
            }
            writer.writerow(row)

        # Удаление старого CSV файла и загрузка нового
        search_and_delete_existing_csv(drive_service, CSV_FOLDER_ID, 'weld_defects.csv')
        save_csv_to_drive(CSV_FILE_PATH, 'weld_defects.csv', CSV_FOLDER_ID)

        logger.info(f"Data for user {chat_id} saved to CSV.")
    except Exception as e:
        logger.error(f"Error saving data to file: {e}")

def save_csv_to_drive(file_path, file_name, folder_id):
    file_metadata = {'name': file_name, 'parents': [folder_id]}
    media = MediaFileUpload(file_path, mimetype='text/csv')
    file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    logger.info(f"CSV file {file_name} uploaded to Google Drive")

# Запуск бота с обработкой исключений
def run_bot():
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            logger.error(f"Error: {e}")
            bot.stop_polling()
            time.sleep(15)

if __name__ == "__main__":
    run_bot()
