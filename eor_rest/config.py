# coding: utf-8


def _as_bool(str_val):
    return str_val.lower() in ('true', '1', 'yes')


class Config(object):

    def __init__(self):
        self.sqlalchemy_session = None
        self.do_csrf_checks = True

    def _from_settings(self, settings):
        self.sqlalchemy_session = settings['eor_rest.sqlalchemy_session']
        if 'eor_rest.do_csrf_checks' in settings:
            self.do_csrf_checks = _as_bool(settings['eor_rest.do_csrf_checks'])


config = Config()
