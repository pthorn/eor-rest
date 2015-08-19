# coding: utf-8


class RESTException(Exception):

    def __init__(self, status=None, key=None, msg=None, exc=None):
        self.status = status or 'error'
        self.key = key
        self.msg = msg
        self.exc = exc

    def response(self):
        resp = {'status': self.status}
        if self.key:
            resp['key'] = self.key
        if self.msg:
            resp['message'] = self.msg

        return resp


class OriginException(RESTException):

    def __init__(self):
        super().__init__()


class CSRFException(RESTException):

    def __init__(self):
        super().__init__()


class RequestParseException(RESTException):

    def __init__(self, exc=None):
        super().__init__(*args, status='bad-json', exc=exc)


class ValidationException(RESTException):

    def __init__(self, exc):
        super().__init__(key='invalid', exc=exc)


    def response(self):
        resp = super().response()

        errors = {}
        for exc in self.exc.errors:
            d = errors
            for el in exc.path[:-1]:
                if not el in d:
                    d[el] = {}
                d = d[el]

            d[exc.path[-1]] = exc.error_message

        resp['errors'] = errors

        return resp
