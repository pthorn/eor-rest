# coding: utf-8

class Config(object):
    """
    from eor_rest import config as rest_config
    from eor.models import Session
    rest_config.sqlalchemy_session = Session
    """

    def __init__(self):
        self.sqlalchemy_session = None

config = Config()
