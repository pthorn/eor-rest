# coding: utf-8

from .config import config
from .delegate import RestDelegate
from .views import RestViews
from .model import RestMixin
from .exceptions import RESTException, ValidationException


def includeme(config):
    from .json import get_json_renderer
    config.add_renderer('eor-rest-json', get_json_renderer(config))
