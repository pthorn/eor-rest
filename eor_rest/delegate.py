# coding: utf-8

import logging
log = logging.getLogger(__name__)

from sqlalchemy.orm.exc import NoResultFound

from voluptuous import Schema, Required, All, MultipleInvalid, Invalid

from .exceptions import *
from .serialization import serialize_sqlalchemy_obj, serialize_sqlalchemy_list


class RestDelegate(object):  #, metaclass=RestDelegateMeta):

    name = None  # 'entity' -> /rest/entities, /rest/entity/{id} etc.
    entity = None # models.Entity
    entity_getter = 'rest_get_by_id'
    entity_list_getter = 'rest_get_list'
    permission = None

    def __init__(self, views):
        self.views = views

    def parse_request_body(self):
        if self.views.request.content_type != 'application/json':
            raise RequestParseException()

        try:
            return self.views.request.json_body
        except ValueError as e:
            raise RequestParseException(e)

    def get_entity(self):
        return self.entity

    def get_query_params_for_coll(self):
        request_params = self.views.request.params
        query_params = {}

        # start

        try:
            query_params['start'] = int(request_params['s'])
        except (KeyError, ValueError):
            pass

        # limit

        try:
            query_params['limit'] = int(request_params['l'])
        except (KeyError, ValueError):
            pass

        # order

        order = request_params.get('o', None)
        if order:
            query_params['order'] = {
                'col': order.lstrip('-'),
                'dir': 'desc' if order.startswith('-') else 'asc'
            }

        # search

        search = request_params.get('q', '').strip()
        if search:
            query_params['search'] = search

        # filters: fe_foo=1

        filters = dict()
        for param, val in request_params.items():
            if param.startswith('f'):
                filters[param[1:]] = val

        if filters:
            query_params['filters'] = filters

        # TODO pass remaining params?

        return query_params

    def get_obj_list(self):
        """
        :return: (total_count, list_of_objects)
        """
        query_params = self.get_query_params_for_coll()

        # returns (count, objs)
        return getattr(self.get_entity(), self.entity_list_getter)(query_params)

    def get_id_from_request(self):
        return self.views.request.matchdict['id']

    def get_id_from_obj(self, obj):
        return obj.id

    def get_obj_by_id(self):
        obj_id = self.get_id_from_request()

        try:
            obj = getattr(self.get_entity(), self.entity_getter)(obj_id)
        except NoResultFound:
            raise RESTException(code='object-not-found')

        if not self.is_obj_allowed(obj):
            raise RESTException(code='forbidden')

        return obj

    def get_fields_for_coll(self):
        return {'*': True}

    def is_obj_allowed(self, obj):
        return True

    def get_fields_for_obj(self):
        return {'*': True}

    def serialize_obj(self, obj):
        return serialize_sqlalchemy_obj(obj, field_spec=self.get_fields_for_obj())

    def serialize_coll(self, lst):
        return serialize_sqlalchemy_list(lst, field_spec=self.get_fields_for_coll())

    def get_schema(self):
        return Schema({}, required=True)

    def deserialize(self, serialized):
        try:
            return self.get_schema()(serialized)
        except MultipleInvalid as e:
            raise ValidationException(e)

    # get list

    def get_list_handler(self):
        count, lst = self.get_obj_list()

        return {
            'status': 'ok',
            'count': count,
            'data': self.serialize_coll(lst)
        }

    # create

    def create_obj(self):
        """
        Create entity object, do not save to database
        """
        return self.entity()

    def before_create(self, obj, deserialized):
        """
        Can interrupt creation by raising RESTException
        """
        pass

    def after_populated(self, obj, deserialized):
        pass

    def after_create(self, obj, deserialized):
        pass

    def create_response(self, obj):
        return {
            'status': 'ok',
            'id': self.get_id_from_obj(obj)
        }

    # update

    def before_update(self, obj, deserialized):
        """
        Can interrupt update by raising RESTException
        """
        pass

    def after_update(self, obj, deserialized):
        pass

    def update_response(self, obj):
        return {'status': 'ok'}

    # delete

    def before_delete(self, obj):
        """
        Can interrupt delete by raising RESTException
        """
        pass

    def delete_obj(self, obj):
        obj.rest_delete(flush=True)

    def after_delete(self):
        pass

    def delete_response(self, obj):
        return {'status': 'ok'}