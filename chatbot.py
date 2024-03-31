import asyncio
from asyncore import dispatcher

import fastapi_poe as fp
import pymongo
from telegram import Update, constants, error, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, MessageHandler, filters, CommandHandler, CallbackQueryHandler
import logging
import os


class GetUpdatesFilter(logging.Filter):
    def filter(self, record):
        return "api.telegram.org" not in record.getMessage()


class CustomHandler(logging.Handler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.addFilter(GetUpdatesFilter())

    def emit(self, record):
        if not self.filter(record):
            return
        print(self.format(record))


# 配置日志记录器
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[CustomHandler()])

# Replace <api_key> with your actual API key, ensuring it is a string.
api_key = os.environ['API_KEY']
bot_names = {
    'Web-Search': 'textbook231'
}
short_bot_name = 'GPT-4'
default_bot_name = bot_names['Web-Search']
user_tasks = {}
user_context = {}
cts = {}
ct = []
model_setting = {
    'gob' : "撤回",
    'new' : "不撤回"
}
async def get_responses(api_key, messages, response_list, done, bot_name):
    async for chunk in fp.get_bot_response(messages=messages, bot_name=bot_name, api_key=api_key):
        response_list.append(chunk.text)
    done.set()


async def update_telegram_message(update, context, response_list, done, response_text, update_interval=1):
    response_message = None
    last_response_text = ""

    while not done.is_set():
        if response_list:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)

            response_text[0] += "".join(response_list)
            response_list.clear()

            if response_text[0].strip() != last_response_text.strip():
                response_message = await send_response_message(context, update.effective_chat.id, response_text[0],
                                                               response_message)

                last_response_text = response_text[0]
        await asyncio.sleep(update_interval)

    if response_list:
        response_text[0] += "".join(response_list)
        response_list.clear()

        if response_text[0].strip() != last_response_text.strip():
            await send_response_message(context, update.effective_chat.id, response_text[0], response_message)



async def handle_user_request(user_id, update, context):
    if user_id in user_context and user_context[user_id]['messages']:
        response_list = []
        done = asyncio.Event()
        response_text = [""]
        api_task = asyncio.create_task(get_responses(api_key, user_context[user_id]['messages'], response_list, done,
                                                     user_context[user_id]['bot_name']))
        telegram_task = asyncio.create_task(
            update_telegram_message(update, context, response_list, done, response_text))
        try:
            await asyncio.gather(api_task, telegram_task)
        except:
            print(1)
            await problem_warning(update,context)
            raise
        # Add the bot's response to the context
        t = response_text[0]
        msg = fp.ProtocolMessage(role="user", content="帮我精简这段话:" + t + "你只需要回答精简的语句")
        await get_responses_short(api_key, [msg], response_list)
        cts['bot'] = ''.join(response_list)
        ct.append(cts.copy())
        user_context[user_id]['messages'].append(fp.ProtocolMessage(role="bot", content=response_text[0]))





async def handle_message(update: Update, context):
    user_id = update.effective_user.id
    logging.info(f"开始处理用户 {user_id} 的请求")
    user_input = update.message.text
    message = fp.ProtocolMessage(role="user", content=user_input)
    cts['user'] = user_input
    # 获取用户上下文
    if user_id not in user_context:
        user_context[user_id] = {'messages': [message], 'bot_name': default_bot_name}
    else:
        user_context[user_id]['messages'].append(message)
    # 检查用户是否已有对应的任务,如果没有则创建一个新任务
    if user_id not in user_tasks or user_tasks[user_id].done():
        user_tasks[user_id] = asyncio.create_task(handle_user_request(user_id, update, context))


async def send_response_message(context, chat_id, response_text, response_message=None):
    if response_text.strip():
        try:
            if response_message is None:
                response_message = await context.bot.send_message(chat_id=chat_id, text=response_text,
                                                                  parse_mode="Markdown")
            else:
                await response_message.edit_text(response_text, parse_mode="Markdown")
        except error.BadRequest:
            if response_message is None:
                response_message = await context.bot.send_message(chat_id=chat_id, text=response_text)
            else:
                await response_message.edit_text(response_text)
    return response_message

async def problem_warning(update: Update, context):
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text="系统后端出现异常，请等修复后在使用"
                                   ,parse_mode="Markdown")

async def start(update: Update, context):
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text="欢迎使用算命机器人，我不敢说我算命最准，但我算你的，肯定很准，如果你有什么需求，可以随时提问我哦，输入/question开启新的对话窗口。"
                                        "输入/back可以恢复上次聊天记录，中间过程中产生记录会消失。"
                                        "接受打赏https://www.zhiqihigh.com/upload/20240327/19cc5fbf1b2155b154d2354eb4e35b7f.jpg"
                                   ,parse_mode="Markdown")


async def go_back(update: Update, context):
    user_id = update.effective_user.id
    bot_name = default_bot_name
    if user_id in user_context:
        bot_name = user_context[user_id]['bot_name']
        user_context[user_id] = {'messages': [], 'bot_name': bot_name}
        c = db_connection();
        h1 = len(list(c.find({'userID': user_id})))
        mes = c.find_one({'userID': user_id, 'count': h1 - 1})
        for i in mes['messages']:
            user_context[user_id]['messages'].append(fp.ProtocolMessage(role="user", content=i['user']))
            user_context[user_id]['messages'].append(fp.ProtocolMessage(role="bot", content=i['bot']))

        print(user_context[user_id]['messages'])
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"已将上次对话重新恢复")
async def new_conversation(update: Update, context):
    user_id = update.effective_user.id
    bot_name = default_bot_name
    if user_id in user_context:
        bot_name = user_context[user_id]['bot_name']
        insert_infor(user_context[user_id],user_id,ct)
        ct.clear()
        user_context[user_id] = {'messages': [], 'bot_name': bot_name}
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"新的对话开始, 输入/back可以恢复上次聊天记录，中间过程中产生记录会消失")

async def qt2(update:Update, context):
    await update.message.reply_text('请选择你接下来的操作', reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton('开启新的会话窗口',callback_data='继续'),
        InlineKeyboardButton('取消操作', callback_data='取消'),
    ]]))


async def answer(update:Update,context):
    yours = update.callback_query.data
    if(yours == "继续"):
        await new_conversation(update, context)
    await update.callback_query.edit_message_text(text=yours)

# async def get_old_mess(update: Update, context):
# 精简回答存入数据库，方便上下文
async def get_responses_short(api_key, messages,response_list):
    async for partial in fp.get_bot_response(messages=messages, bot_name=short_bot_name, api_key=api_key):
        response_list.append(partial.text)


async def Web_Search(update: Update, context):
    user_id = update.effective_user.id
    bot_name = bot_names['Web-Search']
    #await switch_model(user_id, bot_name, update, context)

def insert_infor(information,userID,ct):
    c = db_connection()
    information['userID'] = userID
    l = len(list(c.find({'userID':userID})))
    information['count'] = l
    information['messages'] = ct
    c.insert_one(information)

def db_connection():
    mongoDB_conn = os.environ['MONGODB_URL']
    myclient = pymongo.MongoClient(mongoDB_conn)
    db = myclient['7940_group']
    col = db['chat_bot']
    return col



def main():
    telegram_access_token = os.getenv('TELEGRAM_ACCESS_TOKEN')
    application = Application.builder().token(telegram_access_token).build()

    start_handler = CommandHandler('start', start)
    application.add_handler(start_handler)

    # new_handler = CommandHandler('new', new_conversation)
    # application.add_handler(new_handler)
    #
    # gob = CommandHandler('back', qt2)
    # application.add_handler(gob)
    question = CommandHandler('question',qt2)
    application.add_handler(question)
    ans = CallbackQueryHandler(answer)
    application.add_handler(ans)


    message_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    application.add_handler(message_handler)

    Web_Search_handler = CommandHandler('Web_Search', Web_Search)
    application.add_handler(Web_Search_handler)

    # 运行
    application.run_polling()


if __name__ == '__main__':
    main()