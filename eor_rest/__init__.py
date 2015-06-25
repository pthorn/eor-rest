# coding: utf-8

from .config import config
from .delegate import RestDelegate
from .views import RestViews
from .model import RestMixin
from .exceptions import ValidationException


def includeme(config):
    pass
