# coding: utf-8

from . import config as config_module
from .delegate import RestDelegate
from .routes import RestAPI
from .model import RestMixin
from .exceptions import RESTException, ValidationException


def includeme(config):
    settings = config.get_settings()
    config_module.config._from_settings(settings)

    from .json import get_json_renderer
    config.add_renderer('eor-rest-json', get_json_renderer(config))

    from .views import exception_view
    config.add_view(exception_view, context=RESTException)
