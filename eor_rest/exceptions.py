# coding: utf-8

from sqlalchemy.exc import SQLAlchemyError, DBAPIError


class RESTException(Exception):

    def __init__(self, status=None, code=None, msg=None, exc=None):
        self.status = status or 'error'
        self.code = code
        self.msg = msg
        self.exc = exc

    def response(self):
        """
        return a JSON response with error information
        """

        resp = {'status': self.status}

        # TODO only if allowed
        if isinstance(self.exc, Exception):
            resp['exception'] = {
                'name': self.exc.__class__.__name__,
                'message': str(self.exc)
            }

        if isinstance(self.exc, DBAPIError):
            resp['exception']['statement'] = self.exc.statement
            resp['exception']['params'] = self.exc.params
            resp['exception']['orig'] = {
                'name': self.exc.__class__.__name__,
                'message': str(self.exc.orig)
            }

        if self.code:
            resp['code'] = self.code
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
        super().__init__(code='invalid', exc=exc)


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
