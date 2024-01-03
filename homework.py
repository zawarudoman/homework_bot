import os
import logging
from functools import wraps
from http import HTTPStatus

import requests
import time
import telegram
from dotenv import load_dotenv
from telegram import TelegramError, Bot

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG)
logger = logging.getLogger(__name__)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
timestamp = {'from_date': 1700334422}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def handle_exception(exceptions: tuple[type[Exception]] = (Exception,)):
    """Decorator error."""
    def decorator(func):
        @wraps(func)
        def inner_decorator(*args, **kwargs):
            try:
                func(*args, **kwargs)
            except exceptions as error:
                logging.error(f'Произошла ошибка: {error}')

        return inner_decorator

    return decorator


def check_tokens():
    """Check tokens in environment."""
    variables = [
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID
    ]
    for variable in variables:
        if not variable:
            logging.critical(
                f'Отсутствует переменная среды {variable}',
                exc_info=True
            )


@handle_exception(exceptions=(telegram.TelegramError,))
def send_message(bot, message):
    """Send message."""
    bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=message,
    )

    logging.debug(f'Отправлено сообщение: {message}')


def get_api_answer(timestamp):
    """Request endpoint."""
    try:
        current_timestamp = timestamp or int(time.time())
        params = {'from_date': current_timestamp}
        logging.info(f'Отправка запроса на {ENDPOINT}, параметры: {params}')
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            message = (
                f'Эндпоинт {response.url} недоступен.'
            )
            return message
    except requests.RequestException as error:
        logging.error(error)
    check_response(response.json())
    return response.json()


def check_response(response):
    """Check response for correct."""
    if 'homeworks' in response and isinstance(response['homeworks'], list):
        for homework in response['homeworks']:
            required_fields = [
                'id',
                'status',
                'homework_name',
                'reviewer_comment',
                'date_updated',
                'lesson_name'
            ]
            if all(field in homework for field in required_fields):
                return homework
    else:
        raise TypeError(
            'Нету ключа homeworks или получен не верный тип данных'
        )


def parse_status(homework: dict):
    """Parse status in response."""
    homework_name = homework.get('homework_name')
    if not homework_name:
        raise logging.error('Отсутствует название домашней работы')
    homework_status = homework.get('status')
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    if not verdict:
        raise logging.error(f'Статус отсутсвует или не задан: {verdict}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = Bot(token=TELEGRAM_TOKEN)
    timestamp = 1688021623
    last_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homeworks = response['homeworks']
            homework = homeworks[0] if homeworks else {}
            if homework:
                message = parse_status(homework)
                if last_message != message:
                    send_message(bot, message)
                    last_message = message
                    logger.debug(f'Новый статус - {message}')
                else:
                    logger.debug('Отсутствуют новые статусы')
            else:
                logger.debug('Отсутствуют новые статусы')
        except TelegramError as error:
            logger.error(error)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if last_message != message:
                logger.error(message, exc_info=True)
                send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
