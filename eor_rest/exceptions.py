# coding: utf-8


class RESTException(Exception):

    def __init__(self, status=None, key=None, msg=None, exc=None):
        slf.status = status or 'error'
        self.key = key
        self.msg = msg
        self.exc = exc


class OriginException(RESTException):

    def __init__(self):
        super().__init__()


class CSRFException(RESTException):

    def __init__(self):
        super().__init__()


class DeserializationException(RESTException):

    def __init__(self):
        super().__init__(*args, status='bad-json')


class ValidationException(RESTException):

    def __init__(self, exc):
        # TODO process exc!
        super().__init__(*args, key='invalid')
