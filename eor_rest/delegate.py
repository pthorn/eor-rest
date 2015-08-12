# coding: utf-8

import logging
log = logging.getLogger(__name__)

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

    def get_entity(self):
        return self.entity

    def get_obj_list(self, **extra_getter_args):
        """
        :param extra_getter_args: additional args for self.entity_list_getter
        :return:
        """
        request = self.views.request

        # TODO calculates args from request and calls getter in the same method - difficult to override
        try:
            start = int(request.params['s'])
        except (KeyError, ValueError):
            start = 0
        try:
            limit = int(request.params['l'])
        except (KeyError, ValueError):
            limit = None
    
        order_s = request.params.get('o', None)
        if order_s:
            order = {'col': order_s.lstrip('-'),'dir': 'desc' if order_s.startswith('-') else 'asc'}
        else:
            order = None
    
        search = request.params.get('q', None)
    
        filters = dict()
        for param, val in request.params.items():
            if param.startswith('f'):
                filters[param[1:]] = val

        # returns (count, objs)
        return getattr(self.get_entity(), self.entity_list_getter)(
            start=start, limit=limit, order=order, search=search,
            filters=filters or None, **extra_getter_args
        )

    def get_id_from_request(self):
        return self.views.request.matchdict['id']

    def get_id_from_obj(self, obj):
        return obj.id

    def get_obj_by_id(self):
        obj_id = self.get_id_from_request()

        try:
            return getattr(self.get_entity(), self.entity_getter)(obj_id)
        except NoResultFound:
            raise RESTException(key='object-not-found')

    def get_fields_for_coll(self):
        return {'*': True}

    def get_query_for_coll(self):  # TODO query logic into get_list_for_rest
        return ['*']

    def is_obj_allowed(self, obj):  # TODO query logic into get_by_id
        return ['*']

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

    def after_create(self, obj, deserialized):
        pass

    # update

    def before_update(self, obj, deserialized):
        """
        Can interrupt update by raising RESTException
        """
        pass

    def after_update(self, obj, deserialized):
        pass

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
