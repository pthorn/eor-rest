# coding: utf-8


class Config(object):

    def __init__(self):
        self.sqlalchemy_session = None

    def _from_settings(self, settings):
        self.sqlalchemy_session = settings['eor_rest.sqlalchemy_session']


config = Config()
