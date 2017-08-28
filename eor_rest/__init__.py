# coding: utf-8

from . import config as config_module
from .delegate import RestDelegate
from .views import RestViews
from .model import RestMixin
from .exceptions import RESTException, ValidationException


def includeme(config):
    settings = config.get_settings()
    config_module.config.sqlalchemy_session = settings['eor_rest.sqlalchemy_session']

    from .json import get_json_renderer
    config.add_renderer('eor-rest-json', get_json_renderer(config))

    from .views import exception_view
    config.add_view(exception_view, context=RESTException)
