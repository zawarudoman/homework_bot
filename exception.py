class RequestStatusNotOkError(Exception):
    """Exception for status request != 200."""

    pass


class RequestAPIAnswerError(Exception):
    """Error in get_api_answer func"""

    pass


class NameHomeworkMissingError(Exception):
    """Error missing homework name in homework list"""


class VerdictMissingHomework(Exception):
    """Verdict is missing or not specified in homework"""


class EmptyAnswerAPIError(Exception):
    pass
