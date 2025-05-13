from telethon import TelegramClient, events
import asyncio
import requests
import os
import html
from datetime import datetime

# Конфигурация из переменных окружения
api_id = int(os.environ['API_ID'])
api_hash = os.environ['API_HASH']
phone_number = os.environ['PHONE_NUMBER']
bot_token = os.environ['BOT_TOKEN']
user_id = int(os.environ['USER_ID'])

client = TelegramClient('spybot_session', api_id, api_hash)
msg_cache = {}
your_id = None

async def cache_existing_messages():
    """Кэшируем историю сообщений при запуске"""
    async for dialog in client.iter_dialogs():
        try:
            async for message in client.iter_messages(dialog.id, limit=200):
                if message.id not in msg_cache:
                    media_path = None
                    if message.media:
                        media_path = f'media/old_{message.id}'
                        await client.download_media(message.media, file=media_path)
                    
                    msg_cache[message.id] = {
                        'text': message.text or "(Медиа без текста)",
                        'media_path': media_path,
                        'sender_id': message.sender_id,
                        'chat_id': dialog.id
                    }
        except Exception as e:
            print(f"Ошибка кэширования истории: {e}")

def get_file_type(file_path):
    if not file_path or not os.path.exists(file_path):
        return None
    lower_path = file_path.lower()
    if lower_path.endswith(('.jpg', '.jpeg', '.png', '.webp')):
        return 'photo'
    elif lower_path.endswith(('.mp4', '.avi', '.mov', '.webm')):
        return 'video'
    else:
        return 'document'

def send_to_bot(text, file_path=None):
    try:
        if file_path and os.path.exists(file_path):
            file_type = get_file_type(file_path)
            if file_type == 'photo':
                url = f'https://api.telegram.org/bot{bot_token}/sendPhoto'
                with open(file_path, 'rb') as f:
                    files = {'photo': f}
                    data = {'chat_id': user_id, 'caption': text, 'parse_mode': 'HTML'}
                    requests.post(url, data=data, files=files)
            else:
                url = f'https://api.telegram.org/bot{bot_token}/sendDocument'
                with open(file_path, 'rb') as f:
                    files = {'document': f}
                    data = {'chat_id': user_id, 'caption': text, 'parse_mode': 'HTML'}
                    requests.post(url, data=data, files=files)
        else:
            url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
            data = {'chat_id': user_id, 'text': text, 'parse_mode': 'HTML'}
            requests.post(url, data=data)
    except Exception as e:
        print(f"Ошибка отправки: {e}")

async def get_profile_link(user_id):
    try:
        user = await client.get_entity(user_id)
        first_name = html.escape(user.first_name or '')
        last_name = html.escape(user.last_name or '')
        name = (first_name + ' ' + last_name).strip() or "Пользователь"
        if user.username:
            return f'<a href="https://t.me/{user.username}">{name}</a>'
        else:
            return f'{name} (ID: {user.id})'
    except Exception as e:
        print(f"Ошибка получения профиля: {e}")
        return f'Пользователь (ID: {user_id})'

@client.on(events.NewMessage(incoming=True))
async def handle_all_messages(event):
    global your_id
    if not your_id:
        your_id = (await client.get_me()).id
    
    # Игнорируем сообщения от ботов
    try:
        sender = await event.get_sender()
        if sender.bot:
            return
    except:
        pass

    # Обработка медиа и кэширование
    media_path = None
    if event.media:
        if not os.path.exists("media"):
            os.makedirs("media")
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        media_path = f'media/msg_{event.id}_{timestamp}'
        await client.download_media(event.media, file=media_path)
    
    msg_cache[event.id] = {
        'text': event.text or "(Медиа без текста)",
        'media_path': media_path,
        'sender_id': event.sender_id,
        'chat_id': event.chat_id
    }

@client.on(events.MessageDeleted())
async def handle_delete(event):
    for msg_id in event.deleted_ids:
        if msg_id in msg_cache:
            msg = msg_cache[msg_id]
            try:
                # Игнорируем свои сообщения и сообщения от ботов
                sender = await client.get_entity(msg['sender_id'])
                if msg['sender_id'] == your_id or sender.bot:
                    del msg_cache[msg_id]
                    continue
            except Exception as e:
                print(f"Ошибка проверки отправителя: {e}")
                continue
            
            # Отправка уведомления
            profile_link = await get_profile_link(msg['sender_id'])
            if msg['media_path'] and os.path.exists(msg['media_path']):
                send_to_bot(
                    f"{profile_link}\n🗑️ <b>Удалено сообщение с медиа</b>\n"
                    f"Текст: {msg['text']}",
                    msg['media_path']
                )
            else:
                send_to_bot(
                    f"{profile_link}\n🗑️ <b>Удалено сообщение</b>\n"
                    f"Текст: {msg['text']}"
                )
            del msg_cache[msg_id]

async def main():
    global your_id
    await client.start(phone_number)
    your_id = (await client.get_me()).id
    
    # Кэшируем историю сообщений
    await cache_existing_messages()
    
    send_to_bot("✅ Userbot запущен и готов к работе!")
    await client.run_until_disconnected()

if __name__ == '__main__':
    if not os.path.exists('media'):
        os.makedirs('media')
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Userbot остановлен")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
