#!/usr/env/bin python3

from telegram.ext import Updater, CommandHandler
import logging

class Bot:

    def start(self, update, context):
        update.message.reply_text(f'Hi! This chat is {update.message.chat_id}')

    def earliest(self, update, context):
        update.message.reply_text(self.earliest_reply)

    def error(self, update, context):
        self.logger.warning('Update "%s" caused error "%s"', update, context.error)

    def __init__(self, token):
        updater = Updater(token, use_context=True)
        self.dp = updater.dispatcher
        self.bot = updater.bot
        self.dp.add_handler(CommandHandler("start", self.start))
        self.dp.add_handler(CommandHandler("earliest", self.earliest))

        logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        self.dp.add_error_handler(self.error)
        self.earliest_reply = 'Not crawled yet'
        
        updater.start_polling()

    def send_message(self, message, chat_id, notification=True):
        message = self.bot.send_message(chat_id=chat_id, text=message, disable_notification=not notification)
        self.logger.info('Sent message %s', message)
        return message