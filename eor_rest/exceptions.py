# coding: utf-8


class RESTException(Exception):

    def __init__(self, msg=None, exc=None):
        self.msg = msg
        self.exc = exc

class OriginException(RESTException):
    pass

class CSRFException(RESTException):
    pass

class DeserializationException(RESTException):
    pass

class ValidationException(RESTException):
    pass
