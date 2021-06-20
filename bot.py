from typing import Callable
from functools import partial
import telebot as tb
from arrival_analysis import get_time_to_arival, UserRequest, get_all_the_stops
from config import TOKEN

REQUESTS = {}

bot = tb.TeleBot(TOKEN)

FEATURES = ['Where is that bus?', 'Support']
ALLOWED_BUSSES = ['18']

@bot.message_handler(commands=['start', 'help'])
def greetings(msg: tb.types.Message, first_time: bool = True) -> None:
    '''
    Greetings-function that will give the user an ability to choose what he wants to
    discover via custom keyboard.
    '''

    # prepares the keyboard
    markup = tb.types.InlineKeyboardMarkup(row_width=2)
    markup.add(tb.types.InlineKeyboardButton('Where is that bus?', callback_data='bus_location'),
               tb.types.InlineKeyboardButton('Bus\' stops', callback_data='stops'),
               tb.types.InlineKeyboardButton('Bus on map', callback_data='plot'),
               tb.types.InlineKeyboardButton('Support', callback_data='support'))

    if first_time:
        # prepares the greetings message
        greetings_str = f'''Greetings, {msg.from_user.first_name}.
The bot currently supports such features:
- where is a bus that you would specify and how long would you have to wait for it'''
        bot.send_message(msg.chat.id, greetings_str, reply_markup=markup)
    else:
        bot.send_message(msg.chat.id, 'What you\'d like to do?', reply_markup=markup)
    bot.send_sticker(msg.chat.id, 'CAACAgIAAxkBAAEBdaRgza6qS-oE30b9jDb8VSXLjF8XggACEQADdahyE0TO3mRyQA8bHwQ')

    # creates an user to collect some data from him
    # TODO: reinitialises user when the function is called
    REQUESTS[msg.chat.id] = UserRequest()

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call: tb.types.CallbackQuery) -> None:
    '''
    Handles the callback
    '''

    if call.data == "bus_location":
        bot.send_message(call.message.chat.id, 'Please type what exactly bus do you want to find')
        location_handler = partial(_bus_num_handler, handle_next=_handle_location)
        bot.register_next_step_handler(call.message, location_handler)
    elif call.data == "stops":
        bot.send_message(call.message.chat.id, 'Please type what exactly bus do you want to find')
        stops_handler = partial(_bus_num_handler, handle_next=print_stops)
        bot.register_next_step_handler(call.message, stops_handler)
    elif call.data == "plot":
        pass
    elif call.data == "support":
        bot.send_message(call.message.chat.id, 'What exaclty problem has occured? We would definetely look into it')
        bot.register_next_step_handler(call.message, _log_support)
    elif call.data == "menu":
        # TODO: why this does not work ???
        greetings(call.message, first_time=False)
    elif call.data == "other_direction":
        nearest_bus_info(call.message, direction=1)

def _log_support(msg):
    '''
    Receives some message from the user, that will be redirected to admin.
    '''

    print(msg.json['text'])

def _bus_num_handler(msg, handle_next: Callable):
    '''
    Receives number of bus from the user
    '''

    if (bus_num := msg.json['text']) not in ALLOWED_BUSSES:
        bot.register_next_step_handler(msg, _bus_num_handler)
        if '/' not in msg.json['text']:
            bot.send_message(msg.chat.id, 'Ooooops, something has gone wrong, try again!')
        return

    # TODO: how to do this slightly more efficient?????????
    if handle_next is _handle_location:
        REQUESTS[msg.chat.id].add_bus_num(bus_num)
        keyboard = tb.types.ReplyKeyboardMarkup(row_width=1)
        keyboard.add(tb.types.KeyboardButton('Send Location', request_location=True))

        bot.send_message(msg.chat.id, 'Please send us your location', reply_markup=keyboard)
        bot.register_next_step_handler_by_chat_id(msg.chat.id, handle_next)
    elif handle_next is print_stops:
        REQUESTS[msg.chat.id].add_bus_num(bus_num)
        print_stops(msg)

def _handle_location(msg):
    '''
    Handles receivign location from the user
    '''

    location = (msg.location.latitude, msg.location.longitude)
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
