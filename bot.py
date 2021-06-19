import telebot as tb
from arrival_analysis import get_time_to_arival, UserRequest
from config import TOKEN

REQUESTS = {}

bot = tb.TeleBot(TOKEN)

FEATURES = ['Where is that bus?', 'Support']
ALLOWED_BUSSES = ['18']

@bot.message_handler(commands=['start', 'help'])
def greetings(msg: tb.types.Message) -> None:
    '''
    Greetings-function that will give the user an ability to choose what he wants to
    discover via custom keyboard.
    '''

    # prepares the keyboard
    markup = tb.types.InlineKeyboardMarkup(row_width=2)
    markup.add(tb.types.InlineKeyboardButton('Where is that bus?', callback_data='bus_location'),
               tb.types.InlineKeyboardButton('Support', callback_data='support'))

    # prepares the greetings message
    greetings_str = f'''Greetings, {msg.from_user.first_name}.
The bot currently supports such features:
- where is a bus that you would specify and how long would you have to wait for it'''

    bot.send_message(msg.chat.id, greetings_str, reply_markup=markup)
    bot.send_sticker(msg.chat.id, 'CAACAgIAAxkBAAEBdaRgza6qS-oE30b9jDb8VSXLjF8XggACEQADdahyE0TO3mRyQA8bHwQ')

    REQUESTS[msg.chat.id] = UserRequest()

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call: tb.types.CallbackQuery) -> None:
    '''
    Handles the callback
    '''

    if call.data == "bus_location":
        bot.send_message(call.message.chat.id, 'Please type what exactly bus do you want to find')
        bot.register_next_step_handler(call.message, _bus_num_handler)
    elif call.data == "support":
        bot.send_message(call.message.chat.id, 'What exaclty problem has occured? We would definetely look into it')
        bot.register_next_step_handler(call.message, _log_support)

def _log_support(msg):
    print(msg.json['text'])

def _bus_num_handler(msg):
    if (bus_num := msg.json['text']) not in ALLOWED_BUSSES:
        bot.register_next_step_handler(msg, _bus_num_handler)
        if '/' not in msg.json['text']:
            bot.send_message(msg.chat.id, 'Ooooops, something has gone wrong, try again!')
        return

    REQUESTS[msg.chat.id].add_bus_num(bus_num)
    keyboard = tb.types.ReplyKeyboardMarkup(row_width=1)
    keyboard.add(tb.types.KeyboardButton('Send Location', request_location=True))

    bot.send_message(msg.chat.id, 'Please send us your location', reply_markup=keyboard)
    bot.register_next_step_handler_by_chat_id(msg.chat.id, _handle_location)


def _handle_location(msg):
    location = (msg.location.latitude, msg.location.longitude)
    REQUESTS[msg.chat.id].add_bus_location(location)
    time, bus_stop = get_time_to_arival(REQUESTS[msg.chat.id])
    bot.send_message(msg.chat.id, f'Bus will be at {bus_stop[1]} in {time}')
    bot.send_location(msg.chat.id, latitude=bus_stop[2], longitude=bus_stop[3]);

if __name__ == '__main__':
    bot.polling()
