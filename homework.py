import logging
import os
import sys
import time
from functools import wraps
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv
from telegram import Bot

from exception import RequestStatusNotOkError,\
    EmptyAnswerAPIError, RequestAPIAnswerError,\
    NameHomeworkMissingError, VerdictMissingHomework

load_dotenv()

logger = logging.getLogger(__name__)
handlers = logging.StreamHandler(sys.stdout)


PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

RETRY_PERIOD = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}

HOMEWORK_VERDICTS = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания.",
}


def handle_exception(exceptions: tuple[type[Exception]] = (Exception,)):
    """Decorator error."""

    def decorator(func):
        @wraps(func)
        def inner_decorator(*args, **kwargs):
            try:
                func(*args, **kwargs)
            except exceptions as error:
                logging.error(f"Произошла ошибка: {error}")

        return inner_decorator

    return decorator


def check_tokens():
    """Check tokens in environment."""
    variables = {
        PRACTICUM_TOKEN: "PRACTICUM_TOKEN",
        TELEGRAM_TOKEN: "TELEGRAM_TOKEN",
        TELEGRAM_CHAT_ID: "TELEGRAM_CHAT_ID",
    }
    for variable in variables:
        if not variable:
            logging.critical(
                f"Отсутствует переменная среды {variables.get(variable)}",
                exc_info=True
            )
            sys.exit(
                f"Отсутствует переменная среды {variables.get(variable)},"
                " невозможно продолжить работу"
            )


@handle_exception(exceptions=(telegram.TelegramError,))
def send_message(bot, message):
    """Send message."""
    logging.info("Начало отправки сообщений в Telegram")
    bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=message,
    )

    logging.debug(f"Отправлено сообщение: {message}")


def get_api_answer(timestamp):
    """Request endpoint."""
    try:
        params = {"from_date": timestamp}
        logging.info(f"Отправка запроса на {ENDPOINT}, параметры: {params}")
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            return RequestStatusNotOkError(
                f"Эндпоинт {response.url} получил статус отличный от 200."
            )
    except requests.RequestException as error:
        return RequestAPIAnswerError(f"Возникла ошибка: {error}")
    return response.json()


def check_response(response):
    """Check response for correct."""
    if not isinstance(response, dict):
        raise TypeError("Получен не верный тип данных")
    homeworks = response.get("homeworks")
    if homeworks is None:
        raise EmptyAnswerAPIError
    if not isinstance(homeworks, list):
        raise TypeError("Домашки пришли не списком")
    return homeworks


def parse_status(homework: dict):
    """Parse status in response."""
    homework_name = homework.get("homework_name")
    if not homework_name:
        raise NameHomeworkMissingError("Отсутствует название домашней работы")
    homework_status = homework.get("status")
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    if not verdict:
        raise VerdictMissingHomework(
            f"Статус отсутствует или не задан: {verdict}"
        )
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = Bot(token=TELEGRAM_TOKEN)
    timestamp = 0
    last_message = ""
    while True:
        try:
            response_api = requests.get(
                ENDPOINT, headers=HEADERS, params={"from_date": timestamp}
            )
            response = get_api_answer(timestamp)
            timestamp = response_api.json().get("current_date", timestamp)
            homeworks = check_response(response)
            if homeworks:
                homework = homeworks[0]
                message = parse_status(homework)
            else:
                logger.debug("Отсутствуют новые статусы")
                message = parse_status(homework)
            if last_message != message:
                send_message(bot, message)
                last_message = message
                logger.debug(f"Новый статус - {message}")
            else:
                logger.debug("Отсутствуют новые статусы")
        except EmptyAnswerAPIError as error:
            logger.error(f"Сбой в работе программы: {error}")
        except Exception as error:
            message = f"Сбой в работе программы: {error}"
            if last_message != message:
                send_message(bot, message)
                last_message = message
                logger.error(message, exc_info=True)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    main()
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.DEBUG,
    )
