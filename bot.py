from typing import Callable
from functools import partial
import telebot as tb
import io
import os
from PIL import Image
import folium
from arrival_analysis import get_time_to_arival, UserRequest, get_all_the_stops, get_current_feed,\
                            get_route_id
from config import TOKEN

REQUESTS = {}

bot = tb.TeleBot(TOKEN)

bot.set_my_commands([
    tb.types.BotCommand("/start", "get menu with greetings"),
    tb.types.BotCommand("/help", "get menu with greetings"),
    tb.types.BotCommand("/support", "write about a problem"),
    tb.types.BotCommand("/arrival_time", "get arrival time of certain bus"),
    tb.types.BotCommand("/stops", "get list of stops for a certain bus"),
    tb.types.BotCommand("/plot", "get a map with all the specific number buses")
])

ALLOWED_BUSSES = ['18']

@bot.message_handler(commands=['start', 'help'])
def main_menu(msg: tb.types.Message, first_time: bool = True) -> None:
    '''
    main_menu-function that will give the user an ability to choose what he wants to
    discover via custom keyboard.
    '''

    # prepares the keyboard
    markup = tb.types.InlineKeyboardMarkup(row_width=2)
    markup.add(tb.types.InlineKeyboardButton('Where is that bus?', callback_data='arrival_time'),
               tb.types.InlineKeyboardButton('Bus\' stops', callback_data='stops'),
               tb.types.InlineKeyboardButton('Bus on map', callback_data="plot"),
               tb.types.InlineKeyboardButton('Support', callback_data='support'))

    if first_time:
        # prepares the main_menu message
        main_str = f'''Greetings, {msg.from_user.first_name}.
The bot currently supports such features:
- where is a bus that you would specify and how long would you have to wait for it'''
        bot.send_message(msg.chat.id, main_str, reply_markup=markup)
    else:
        bot.send_message(msg.chat.id, 'What you\'d like to do?', reply_markup=markup)
    bot.send_sticker(msg.chat.id, 'CAACAgIAAxkBAAEBdaRgza6qS-oE30b9jDb8VSXLjF8XggACEQADdahyE0TO3mRyQA8bHwQ')

    # creates an user to collect some data from him
    # TODO: reinitialises user when the function is called
    REQUESTS[msg.chat.id] = UserRequest()

@bot.message_handler(commands=['arrival_time'])
def arrival_time_(msg):
    # TODO: depricated
    REQUESTS[msg.chat.id] = UserRequest()
    bot.send_message(msg.chat.id, 'Please type what exactly bus do you want to find')
    location_handler = partial(get_bus_num_from_user, handle_next=_handle_location)
    bot.register_next_step_handler(msg, location_handler)

@bot.message_handler(commands=['stops'])
def stops(msg):
    # TODO: depricated
    REQUESTS[msg.chat.id] = UserRequest()
    bot.send_message(msg.chat.id, 'Please type what exactly bus do you want to find')
    stops_handler = partial(get_bus_num_from_user, handle_next=print_stops)
    bot.register_next_step_handler(msg, stops_handler)

@bot.message_handler(commands=['support'])
def support(msg):
    REQUESTS[msg.chat.id] = UserRequest()
    bot.send_message(msg.chat.id, 'What exaclty problem has occured? We would definetely look into it')
    bot.register_next_step_handler(msg, _log_support)

@bot.message_handler(commands=['plot'])
def plot(msg):
    REQUESTS[msg.chat.id] = UserRequest()
    bot.send_message(msg.chat.id, 'Please type what exactly bus do you want to find')
    stops_handler = partial(get_bus_num_from_user, handle_next=plot_buses)
    bot.register_next_step_handler(msg, stops_handler)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call: tb.types.CallbackQuery) -> None:
    '''
    Handles the callbacks
    '''

    call_data_mapping = {
        "arrival_time": arrival_time_,
        "stops": stops,
        "plot": plot,
        "support": support,
        "other_direction": partial(nearest_bus_info, direction=1),
        "menu": partial(main_menu, first_time=False)
    }

    call_data_mapping[call.data](call.message)

def _log_support(msg):
    '''
    Receives some message from the user, that will be redirected to admin.
    '''

    print(msg.json['text'])

def get_bus_num_from_user(msg, handle_next: Callable):
    '''
    Receives number of bus from the user
    '''

    if (bus_num := msg.json['text']) not in ALLOWED_BUSSES:
        bot.register_next_step_handler(msg, get_bus_num_from_user(handle_next=handle_next))
        if '/' not in msg.json['text']:
            bot.send_message(msg.chat.id, 'Ooooops, something has gone wrong, try again!')
        return

    # TODO: how to do this slightly more efficient?????????
    if handle_next is _handle_location:
        REQUESTS[msg.chat.id].add_bus_num(bus_num)
        keyboard = tb.types.ReplyKeyboardMarkup(row_width=1)
        keyboard.add(tb.types.KeyboardButton('Send Location', request_location=True),
                     tb.types.KeyboardButton('Cancel'))

        bot.send_message(msg.chat.id, 'Please send us your location', reply_markup=keyboard)
        bot.register_next_step_handler_by_chat_id(msg.chat.id, handle_next)
    elif handle_next in [print_stops, plot_buses]:
        REQUESTS[msg.chat.id].add_bus_num(bus_num)
        handle_next(msg)

def plot_buses(msg):
    '''
    I know, I know...
    '''

    feed = get_current_feed()
    bus_id = get_route_id(REQUESTS[msg.chat.id])

    buses = [bus for bus in feed.entity if bus.vehicle.trip.route_id == str(bus_id)]

    buses_map = folium.Map(location=[49.842957, 24.03111], zoom_start=12, tiles='cartodbpositron')

    for bus in buses:
        coords = [bus.vehicle.position.latitude, bus.vehicle.position.longitude]
        folium.CircleMarker(coords, radius=1,
                    color='#0080bb', fill_color='#0080bb').add_to(buses_map)

    buses_map.save('buses_map.html')
    html_file = open('buses_map.html', 'rb')

    response = bot.send_document(chat_id=msg.chat.id, data=html_file, caption='html-map')
    os.remove('buses_map.html')


def _handle_location(msg):
    '''
    Handles receivign location from the user
    '''

    try:
        location = (msg.location.latitude, msg.location.longitude)
    except AttributeError: # this means that the user has pressed cancel
        main_menu(msg, first_time=False)
        return
    REQUESTS[msg.chat.id].add_user_location(location)

    nearest_bus_info(msg, 0)

def print_stops(msg):
    bus_num = REQUESTS[msg.chat.id].bus_num
    stops, _ = get_all_the_stops(bus_num)
    stop_str = f'Bus {bus_num} covers such stops:\n'
    stop_str += '\n'.join(stops)
    bot.send_message(msg.chat.id, stop_str)

def nearest_bus_info(msg, direction: int = 0):
    time, bus_loc, bus_stop, direction = get_time_to_arival(REQUESTS[msg.chat.id], direction)

    bot.send_message(msg.chat.id, f'Bus will be at {bus_stop[1]} in {time}. It\'d destination is: {direction}')
    bot.send_location(msg.chat.id, latitude=bus_loc[0], longitude=bus_loc[1])
    bot.send_message(msg.chat.id, 'Nearest bus stop location for it:')
    bot.send_location(msg.chat.id, latitude=bus_stop[2], longitude=bus_stop[3])

    markup = tb.types.InlineKeyboardMarkup(row_width=2)
    markup.add(tb.types.InlineKeyboardButton('Other direction', callback_data='other_direction'),
                tb.types.InlineKeyboardButton('Main menu', callback_data='menu'))

    bot.send_message(msg.chat.id, 'Thanks for using', reply_markup=markup)


if __name__ == '__main__':
    bot.polling()
