# coding: utf-8

import logging
log = logging.getLogger(__name__)

from voluptuous import Schema, Required, All, MultipleInvalid, Invalid


class DeserializationException(Exception):

    def __init__(self, exc):
        self.exc = exc


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

    def get_obj_list(self):
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

        get_args = None  # TODO!! additional args for self.entity_list_getter
        if not get_args:
            get_args = dict()
    
        # returns count, objs
        return getattr(self.get_entity(), self.entity_list_getter)(
            start, limit, order=order, search=search, filters=filters or None, **get_args)

    def get_id_from_request(self):
        return self.views.request.matchdict['id']

    def get_obj_by_id(self):
        obj_id = self.get_id_from_request()
        return getattr(self.get_entity(), self.entity_getter)(obj_id)

    def create_obj(self):
        return self.entity()

    def get_fields_for_coll(self):
        return ['*']

    def get_query_for_coll(self):  # TODO query logic into get_list_for_rest
        return ['*']

    def is_obj_allowed(self, obj):  # TODO query logic into get_by_id
        return ['*']

    def get_fields_for_obj(self):
        return ['*']

    def get_schema(self):
        return Schema({}, required=True)

    def deserialize(self, serialized):
        try:
            return self.get_schema()(serialized)
        except MultipleInvalid as e:
            raise DeserializationException(e)  # TODO

    def after_create_obj(self, obj, deserialized):
        pass

    def before_update_obj(self, obj, deserialized):
        return True

    def after_update_obj(self, obj, deserialized):
        pass

    def before_delete(self):
        return True

    def after_delete(self):
        pass
