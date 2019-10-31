import configparser

import pandas as pd
import telebot
import urllib
import os
from collections import defaultdict
import requests

from telebot import types
from telebot.apihelper import ApiException

from db.postgresql_query import DataBase

# abs path to project
abs_path_to_runfile = os.path.dirname(os.path.abspath(__file__))
project_abs_path = os.path.join(abs_path_to_runfile, "..")

# initialization
config = configparser.ConfigParser()
config.read(os.path.join(project_abs_path, 'config.cfg'))
token = config["visited_places_bot"]['telebot_token']
api_key = config["visited_places_bot"]['google_api_key']

no_data_message = "нет данных"

START, NAME, ADDRESS, PHOTO, COORDINATES = range(5)
USER_STATE = defaultdict(lambda: START)

PLACE = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: None)))  # keys are without place_id. user_id and
# the place features only
place_ids = defaultdict(lambda: 0)
data_base = DataBase()


# functions
def get_state(message):
    return USER_STATE[message.chat.id]


def update_state(message, state):
    USER_STATE[message.chat.id] = state


def update_place(user_id, key, value):
    PLACE[user_id][key] = value


def reset_place(user_id):
    PLACE[user_id] = defaultdict(lambda: defaultdict(lambda: None))


def get_places_less500(user_id, my_coords):
    places_with_locs = get_places_from_db(user_id)   # df
    if places_with_locs.empty:
        return places_with_locs

    places_less500 = get_places_with_dists(my_coords, places_with_locs)

    return places_less500


def get_places_from_db(user_id, limit=None):
    cols = ['name', 'address', 'photo_id', "lat", "lon"]
    cols_join = ", ".join(cols)
    query_text = f"""
                    SELECT {cols_join} FROM places WHERE user_id = %s
                  """
    query_params = (str(user_id),)
    if limit is not None:
        query_text += f"LIMIT %s"
        query_params = (str(user_id), str(limit))
    rows = data_base.query_fetchall(query_text, query_params)
    places_with_locs = pd.DataFrame(rows, columns=cols)
    return places_with_locs


def get_places_with_dists(my_coords, places_with_locs):
    """
    my_location: (lat, lon)
    places_with_locs: [[place_id, (lat, lon)], ...]
    """
    url_pref = "https://maps.googleapis.com/maps/api/distancematrix/"
    output_format = "json"
    origins = ','.join(my_coords)
    places_coords = zip(places_with_locs["lat"], places_with_locs["lon"])
    destinations = "|".join([','.join([str(lat), str(lon)]) for lat, lon in places_coords])

    url = f"{url_pref}{output_format}?origins={origins}&destinations={destinations}&key={api_key}"

    # request to google api
    request = requests.get(url)
    info = request.json()
    rows = info['rows']
    distances = list(map(lambda x: x.get("distance", {}).get("value", float("inf")), rows[0]['elements']))
    places_with_locs["dist"] = distances
    return places_with_locs[places_with_locs.dist <= 500].sort_values("dist")


# initialization for keyboard
mark_less500 = "Места не далее 500м"
mark_last10 = "Последние 10 мест"
buttons_list = [mark_less500, mark_last10]


def create_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    buttons = [types.InlineKeyboardButton(text=item, callback_data=item) for item in buttons_list]
    keyboard.add(*buttons)
    return keyboard


def place_to_db(user_id):
    psql_query = DataBase()
    values = (
        user_id,
        PLACE[user_id]["name"],
        PLACE[user_id]["address"],
        PLACE[user_id]["photo_id"],
        PLACE[user_id]["lat"],
        PLACE[user_id]["lon"]
    )
    psql_query.query_insert(values)


def reset_places(user_id):
    query_text = f"DELETE FROM places WHERE user_id = %s"
    query_params = (str(user_id),)
    data_base.query(query_text, query_params, commit=True)


# bot
def my_bot():
    bot = telebot.TeleBot(token)

    def get_photo(photo_id):
        try:
            file_info = bot.get_file(photo_id)
            photo = urllib.request.urlopen(f'https://api.telegram.org/file/bot{token}/{file_info.file_path}').read()
        except ApiException:
            photo = None
        return photo

    def send_place_to_chat(message, row, num):
        name = row["name"]
        address = row["address"]
        photo_id = row["photo_id"]
        dist = row["dist"]

        text = f"""
#{num}
Название: {name}
Адрес: {address}
"""
        if dist != no_data_message:
            text += f"Расстояние до вас (м): {dist}\n"

        # TODO переделать эту конструкцию
        if photo_id:
            # send photo with text
            photo = get_photo(photo_id)
            if photo:
                bot.send_photo(message.chat.id, photo, caption=text)
            else:
                # send message with text
                text += "Фото: отсутствует"
                bot.send_message(message.chat.id, text=text)
        else:
            # send message with text
            text += "Фото: отсутствует"
            bot.send_message(message.chat.id, text=text)

    def send_selected_places_to_chat(message, selected_places, text_by_success, text_by_fail):
        if not selected_places.empty:
            bot.send_message(message.chat.id, text=text_by_success)
            for num, (index, row) in enumerate(selected_places.fillna(no_data_message).iterrows()):
                send_place_to_chat(message, row, num + 1)
        else:
            text = text_by_fail
            bot.send_message(message.chat.id, text=text)

    @bot.message_handler(commands=["add"])
    def handle_add(message):
        reset_place(message.chat.id)

        bot.send_message(message.chat.id, text="Напиши название")
        update_state(message, NAME)

    @bot.message_handler(func=lambda message: get_state(message) == NAME)
    def handle_name(message):
        # name
        print("place_ids[message.chat.id]", place_ids[message.chat.id], "\n")
        update_place(message.chat.id, "name", message.text)
        bot.send_message(message.chat.id, text="Укажи адрес")
        update_state(message, ADDRESS)

    @bot.message_handler(func=lambda message: get_state(message) == ADDRESS)
    def handle_address(message):
        # адрес
        update_place(message.chat.id, "address", message.text)
        bot.send_message(message.chat.id, text='Загрузи фото\n(отправь "нет" или любые символы, если фото нет)')
        update_state(message, PHOTO)

    @bot.message_handler(content_types=["photo"])
    @bot.message_handler(func=lambda message: get_state(message) == PHOTO)
    def handle_photo(message):
        # photo
        if message.photo:
            photo_id = message.photo[0].file_id
        else:
            photo_id = None

        update_place(message.chat.id, "photo_id", photo_id)
        bot.send_message(message.chat.id,
                         text="Загрузи координаты - широту, долготу (через запятую, без скобок). \nПример: "
                              "\n51.678727, 39.206864")
        update_state(message, COORDINATES)

    # @bot.message_handler(content_types=["location"])
    @bot.message_handler(func=lambda message: get_state(message) == COORDINATES)
    def handle_coordinates(message):
        if message.location is not None:
            coords = [message.location.latitude, message.location.longitude]
        else:
            # coordinates from text
            text = message.text
            try:
                coords = [str(float(coord.strip())) for coord in text.split(",")]
            except ValueError:
                coords = [None, None]
            if len(coords) < 2:
                coords = [None, None]  # fixed bug if len(coords) = 1

        update_place(message.chat.id, "lat", coords[0])
        update_place(message.chat.id, "lon", coords[1])
        place_to_db(message.chat.id)
        bot.send_message(message.chat.id, text="Место сохранено :)")
        update_state(message, START)

    # list
    @bot.message_handler(commands=["list"])
    def handle_list(message):
        places_one_row = get_places_from_db(message.chat.id, limit=1)
        if not places_one_row.empty:
            keyboard = create_keyboard()
            bot.send_message(chat_id=message.chat.id, text="Что бы вы хотели:", reply_markup=keyboard)
        else:
            text = """
                Список ваших мест пуст. Вы можете начать их добавлять с помощью команды /add
                """
            bot.send_message(message.chat.id, text=text)

    # обрабатываем кнопки
    @bot.callback_query_handler(func=lambda x: True)
    def callback_handler(callback_query):
        message = callback_query.message
        user_id = message.chat.id
        callback_text = callback_query.data

        if callback_text == mark_less500:
            text = """
            Отправьте вашу локацию. Будут выведены все сохраненные места в радиусе 500м
            """
            bot.send_message(message.chat.id, text=text)

        if callback_text == mark_last10:
            # последние 10 добавленных мест
            cols = ['name', 'address', 'photo_id']
            cols_join = ", ".join(cols)
            query_text = f"""
                SELECT {cols_join} FROM places WHERE user_id = %s ORDER BY id DESC LIMIT 10
            """
            query_params = (str(user_id),)
            rows = data_base.query_fetchall(query_text, query_params)
            places_last10 = pd.DataFrame(rows, columns=cols)
            places_last10["dist"] = None
            text_by_success = "Ваши до 10 последних сохраненных мест:"
            text_by_fail = "Список ваших мест пуст. Вы также можете начать добавлять места с помощью команды /add"
            send_selected_places_to_chat(message, places_last10, text_by_success, text_by_fail)

    @bot.message_handler(content_types=["location"])
    def handle_location(message):
        my_location = message.location
        my_coords = (str(my_location.latitude), str(my_location.longitude))
        places_less500 = get_places_less500(message.chat.id, my_coords)
        text_by_success = "Ваши сохраненные места не далее 500м:"
        text_by_fail = "В радиусе 500м ваших сохраненных мест не обнаружено :(. Вы можете добавить новые места с " \
                       "помощью команды /add "
        send_selected_places_to_chat(message, places_less500, text_by_success, text_by_fail)

    @bot.message_handler(commands=["reset"])
    def handle_reset(message):
        reset_places(message.chat.id)
        bot.send_message(message.chat.id, text="Все ваши сохраненные места удалены")

    @bot.message_handler(commands=["start"])
    def handle_list(message):
        text = """
Привет! Я Бот, который поможет тебе сохранить места для будущего посещения.
Воспользуйся командой /help, чтобы узнать все доступные команды.
"""
        bot.send_message(message.chat.id, text=text)

    @bot.message_handler(commands=["help"])
    def handle_list(message):
        text = """
/add – добавление нового места
/list – отображение добавленных мест - в радиусе 500м или последних 10ти
/reset – удаление всех ваших добавленных локаций

/start - начало общения с ботом
/help - помощь
"""
        bot.send_message(message.chat.id, text=text)

    @bot.message_handler()
    def handle_list(message):
        text = """
Привет! Я Бот, который поможет тебе сохранить места для будущего посещения.
Воспользуйся командой /help, чтобы узнать все доступные команды.
"""
        bot.send_message(message.chat.id, text=text)

    bot.polling()


if __name__ == '__main__':
    my_bot()
