# coding: utf-8

import datetime
import decimal
import uuid

from pyramid.renderers import JSON


def configure_renderer(json):
    def datetime_adapter(obj, request):
        return obj.isoformat()

    json.add_adapter(datetime.date, datetime_adapter)
    json.add_adapter(datetime.datetime, datetime_adapter)
    json.add_adapter(decimal.Decimal, lambda val, request: float(val))
    json.add_adapter(uuid.UUID, lambda val, request: str(val))


def get_json_renderer(config):
    """
    http://docs.pylonsproject.org/projects/pyramid/en/latest/narr/renderers.html#json-renderer
    """
    json = JSON(ensure_ascii=False)
    configure_renderer(json)
    return json
