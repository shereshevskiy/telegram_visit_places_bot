import telebot
import urllib
import os
from collections import defaultdict
import requests

# abs path to project
from telebot import types

abs_path_to_runfile = os.path.dirname(os.path.abspath(__file__))
project_abs_path = os.path.join(abs_path_to_runfile, "..")

# initialization
token = None  # use your token
photo_path = os.path.join(project_abs_path, "photos")
my_api_key = None  # use your key
no_data_message = "нет данных"


START, NAME, ADDRESS, PHOTO, COORDINATES = range(5)
USER_STATE = defaultdict(lambda: START)

PLACES = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: no_data_message)))
place_ids = defaultdict(lambda: 0)


# functions
def get_state(message):
    return USER_STATE[message.chat.id]


def update_state(message, state):
    USER_STATE[message.chat.id] = state


def update_place(user_id, key, value):
    PLACES[user_id][place_ids[user_id]][key] = value


def update_place_id(user_id):
    place_ids[user_id] += 1


def reset_places(user_id):
    PLACES[user_id] = defaultdict(lambda: defaultdict(lambda: no_data_message))
    place_ids[user_id] = 0


def get_places_less500(my_coords, places):
    places_with_locs = get_places_with_locs(places)
    if not places_with_locs:
        return []

    places_with_dists = get_places_with_dists(my_coords, places_with_locs, my_api_key)
    places_less500_draft = [place for place in places_with_dists if place[1] <= 500]
    places_less500_draft = sorted(places_less500_draft, key=lambda x: x[1])

    def get_place_info(place_id, dist, used_places):
        place_info = used_places[place_id]
        place_info['distance'] = dist
        return place_info

    places_less500 = [
        (place_id, get_place_info(place_id, dist, places))
        for place_id, dist in places_less500_draft
    ]
    return places_less500


def get_places_with_locs(places):
    places_with_locs = [
        [place_id, value["coordinates"]]
        for place_id, value in places.items() if value["coordinates"] != no_data_message
    ]
    return places_with_locs


def get_places_with_dists(my_coords, places_with_locs, api_key):
    """
    my_location: (lat, lon)
    places_with_locs: [[place_id, (lat, lon)], ...]
    """
    url_pref = "https://maps.googleapis.com/maps/api/distancematrix/"
    output_format = "json"
    origins = ','.join(my_coords)
    destinations = "|".join([','.join(place[1]) for place in places_with_locs])

    url = f"{url_pref}{output_format}?origins={origins}&destinations={destinations}&key={api_key}"

    # request to google api
    request = requests.get(url)
    info = request.json()
    rows = info['rows']
    distances = map(lambda x: x.get("distance", {}).get("value", float("inf")), rows[0]['elements'])
    # distances = map(lambda x: x["distance"]["value"], rows[0]['elements'])
    place_ids = map(lambda x: x[0], places_with_locs)

    places_with_dists = zip(place_ids, distances)
    return places_with_dists


mark_less500 = "Места не далее 500м"
mark_last10 = "Последние 10 мест"
what_list_need = [mark_less500, mark_last10]


def create_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    buttons = [types.InlineKeyboardButton(text=item, callback_data=item) for item in what_list_need]
    keyboard.add(*buttons)
    return keyboard


# bot
def main():
    bot = telebot.TeleBot(token)

    def get_photo(photo_id):
        file_info = bot.get_file(photo_id)
        photo = urllib.request.urlopen(f'https://api.telegram.org/file/bot{token}/{file_info.file_path}').read()
        return photo

    def send_place_to_chat(place, message, num):
        text = f"""
#{num}
Название: {place["name"]}
Адрес: {place["address"]}
Расстояние до вас (м): {place["distance"]}
"""
        if place["photo_id"]:
            # send photo with text
            photo = get_photo(place["photo_id"])
            bot.send_photo(message.chat.id, photo, caption=text)
        else:
            # send message with text
            text += "Фото: отсутствует"
            bot.send_message(message.chat.id, text=text)

    def send_selected_places_to_chat(message, selected_places, text_by_success, text_by_fail):
        if selected_places:
            bot.send_message(message.chat.id, text=text_by_success)
            for num, pair in enumerate(selected_places):
                place_id, place = pair
                send_place_to_chat(place, message, num + 1)
        else:
            text = text_by_fail
            bot.send_message(message.chat.id, text=text)

    @bot.message_handler(commands=["add"])
    def handle_add(message):
        update_place_id(message.chat.id)

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

    @bot.message_handler(func=lambda message: get_state(message) == COORDINATES)
    def handle_coordinates(message):
        # coordinates
        text = message.text
        try:
            coord = [str(float(coord.strip())) for coord in text.split(",")]
        except ValueError:
            coord = no_data_message
        update_place(message.chat.id, "coordinates", coord)
        bot.send_message(message.chat.id, text="Место сохранено :)")
        update_state(message, START)

    # list для мест в рабиусе 500м
    @bot.message_handler(commands=["list"])
    def handle_list(message):
        keyboard = create_keyboard()
        bot.send_message(chat_id=message.chat.id, text="Что бы вы хотели:", reply_markup=keyboard)

    # обрабатываем кнопки
    @bot.callback_query_handler(func=lambda x: True)
    def callback_handler(callback_query):
        message = callback_query.message
        text = callback_query.data

        if text == mark_less500:
            if PLACES[message.chat.id] != defaultdict(lambda: defaultdict(lambda: no_data_message)):
                text_to_chat = """
                Отправьте вашу локацию. Будут выведены все сохраненные места в радиусе 500м
                """
            else:
                text_to_chat = """
                Список ваших мест пуст. Вы их можете начать добавлять с помощью команды /add
                """
            bot.send_message(message.chat.id, text=text_to_chat)

        if text == mark_last10:
            # последние 10 добавленных мест
            places = PLACES[message.chat.id]
            places_all = sorted(list(places.items()), key=lambda x: x[0], reverse=True)
            places_last10 = places_all[:10]
            text_by_success = "Ваши до 10 последних сохраненных мест:"
            text_by_fail = "Список ваших мест пуст. Вы также можете начать добавлять места с помощью команды /add"
            send_selected_places_to_chat(message, places_last10, text_by_success, text_by_fail)

    @bot.message_handler(content_types=["location"])
    def handle_location(message):
        places = PLACES[message.chat.id]
        my_location = message.location
        my_coords = (str(my_location.latitude), str(my_location.longitude))
        places_less500 = get_places_less500(my_coords, places)
        text_by_success = "Ваши сохраненные места не далее 500м:"
        text_by_fail = "В радиусе 500м ваших сохраненных мест не обнаружено :(. Вы можете добавить новые места с " \
                       "помощью команды /add "
        send_selected_places_to_chat(message, places_less500, text_by_success, text_by_fail)

    @bot.message_handler(commands=["reset"])
    def handle_reset(message):
        reset_places(message.chat.id)
        bot.send_message(message.chat.id, text="Все ваши сохраненные места удалены")

    @bot.message_handler(commands=["start"])
    @bot.message_handler()
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
    /list – отображение добавленных мест в радиусе 500м от вашей локации
    /reset – удаление всех ваших добавленных локаций
    """
        bot.send_message(message.chat.id, text=text)

    bot.polling()


if __name__ == '__main__':
    main()
