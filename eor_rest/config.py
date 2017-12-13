# coding: utf-8


def _as_bool(val):
    if type(val) == type(True):
        return val

    return val.lower() in ('true', '1', 'yes')


class Config(object):

    def __init__(self):
        self.sqlalchemy_session = None
        self.do_csrf_checks = True

    def _from_settings(self, settings):
        self.sqlalchemy_session = settings['eor_rest.sqlalchemy_session']
        if 'eor_rest.do_csrf_checks' in settings:
            self.do_csrf_checks = _as_bool(settings['eor_rest.do_csrf_checks'])


config = Config()
