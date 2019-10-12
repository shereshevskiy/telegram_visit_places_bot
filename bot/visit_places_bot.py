import telebot
import urllib
import os
from collections import defaultdict
import requests

# abs path to project
abs_path_to_runfile = os.path.dirname(os.path.abspath(__file__))
project_abs_path = os.path.join(abs_path_to_runfile, "..")

# initialization
token = "780799099:AAGGjJfeKRiXX7D34_ZrW19n_zxOFcZbs70"
photo_path = os.path.join(project_abs_path, "photos")
my_api_key = "AIzaSyB5N7lIE2T6a3hrUFm9dYvwqTaa1mMVC_c"
no_data_message = "Нет данных"


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


def send_place_to_chat(place):
    pass  # TODO


# bot
def main():
    bot = telebot.TeleBot(token)

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
        bot.send_message(message.chat.id, text="Загрузи фото")
        update_state(message, PHOTO)

    @bot.message_handler(content_types=["photo"])
    @bot.message_handler(func=lambda message: get_state(message) == PHOTO)
    def handle_photo(message):
        # photo
        if message.photo:
            photo_id = message.photo[0].file_id
            file_info = bot.get_file(photo_id)
            # urllib.request.urlretrieve(f'https://api.telegram.org/file/bot{token}/{file_info.file_path}',
            #                            os.path.join(photo_path, f"{photo_id}.jpg"))
            photo = urllib.urlopen(f'https://api.telegram.org/file/bot{token}/{file_info.file_path}').read()
            bot.send_photo(message.chat.id, photo, caption="Дублирую картинку обратно )")
            photo_info = photo_id
        else:
            photo_info = no_data_message

        update_place(message.chat.id, "photo", photo_info)
        bot.send_message(message.chat.id,
                         text="Загрузи координаты - широту, долготу (через запятую, без скобок)")
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
        if PLACES[message.chat.id] != defaultdict(lambda: defaultdict(lambda: no_data_message)):
            text = """
    Отправьте вашу локацию. Будут выведены все сохраненные места в радиусе 500м
    """
        else:
            text = """
    Список ваших мест пуст. 
    Вы их можете начать добавлять с помощью команды /add
    """
        bot.send_message(message.chat.id, text=text)

    @bot.message_handler(content_types=["location"])
    def handle_location(message):
        places = PLACES[message.chat.id]
        my_location = message.location
        my_coords = (str(my_location.latitude), str(my_location.longitude))
        places_less500 = get_places_less500(my_coords, places)
        if places_less500:
            bot.send_message(message.chat.id, text="Ваши сохраненные места в не далее 500м:")
            for place in places_less500:
                send_place_to_chat(place)
        else:
            text = """
    В радиусе 500м ваших сохраненных мест не обнаружено :(. 
    Вы можете добавить новые места с помощью команды /add
    """
            bot.send_message(message.chat.id, text=text)

    # # list для последних 10 добавленных мест
    # @bot.message_handler(commands=["list"])
    # def handle_list(message):
    #     # последние 10 добавленных мест
    #     places = PLACES[message.chat.id]
    #     places_all = sorted(list(places.items()), key=lambda x: x[0], reverse=True)
    #     places_last10 = places_all[:10]
    #     if places_last10 != []:
    #         text = f"{places_last10}"
    #     else:
    #         text = """
    # Список ваших мест пуст.
    # Вы их можете начать добавлять с помощью команды /add
    # """
    #     bot.send_message(message.chat.id, text=text)

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
