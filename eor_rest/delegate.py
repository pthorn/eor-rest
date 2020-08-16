# coding: utf-8

import logging
log = logging.getLogger(__name__)

from voluptuous import Schema, Required, All, MultipleInvalid, Invalid

from .exceptions import *
from .serialize import serialize_sqlalchemy_obj, serialize_sqlalchemy_list
from .deserialize import update_entity_from_appstruct, run_hooks_on_delete


class RestDelegate(object):  #, metaclass=RestDelegateMeta):
    """
    permission: None, string, dict {, '*': string};
      dict keys: get, getbyid, create, update, delete
    """

    name = None  # 'entity' -> /rest/entities, /rest/entity/{id} etc.
    entity = None # models.Entity
    entity_getter = 'rest_get_by_id'
    entity_list_getter = 'rest_get_list'
    permission = None
    allow_create_on_update = False

    def __init__(self, views):
        self.views = views
        self.request = views.request
        self.method = views.request.method

    def parse_request_body(self):
        if self.views.request.content_type != 'application/json':
            raise RequestParseException()

        try:
            return self.views.request.json_body
        except ValueError as e:
            raise RequestParseException(e)

    def get_entity(self):
        return self.entity

    def get_id_from_request(self):
        return self.views.request.matchdict['id']

    def get_id_from_obj(self, obj):
        return obj.id

    def get_obj_by_id(self):
        obj_id = self.get_id_from_request()

        obj = getattr(self.get_entity(), self.entity_getter)(obj_id)

        # security check
        if not self.is_access_allowed_for_obj(obj, self.request.method):
            log.debug('is_access_allowed_for_obj() is False, method %s, entity %r, id %r',
                self.request.method, self.name, obj_id)
            raise RESTException(code='forbidden')

        return obj

    def is_access_allowed_for_obj(self, obj, method):
        return True

    def get_schema(self):
        return Schema({}, required=True)

    def deserialize(self, serialized):
        try:
            return self.get_schema()(serialized)
        except MultipleInvalid as e:
            print('\n', str(e), '\n', e.errors, '\n', e.errors[0].path, '\n', e.errors[0].error_message, '\n')
            from pprint import pprint
            print('pprint:', pprint(e), '\n')
            raise ValidationException(e)

    def update_obj(self, obj, deserialized):
        """
        Used by create and update handlers
        """
        update_entity_from_appstruct(obj, deserialized)

    # get list

    def get_list_handler(self):
        count, lst = self.get_obj_list()

        return {
            'status': 'ok',
            'count': count,
            'data': self.serialize_coll(lst)
        }

    def get_fields_for_coll(self):
        return {'*': True}

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

    def serialize_coll(self, lst):
        return serialize_sqlalchemy_list(lst, field_spec=self.get_fields_for_coll())

    # get item

    def get_fields_for_obj(self):
        return {'*': True}

    def serialize_obj(self, obj):
        return serialize_sqlalchemy_obj(obj, field_spec=self.get_fields_for_obj())

    # create

    def create_handler(self):
        self.mode = 'CREATE'

        # parse request body
        json = self.parse_request_body()

        # check existing
        # TODO no ID in request; some objects may have ID in request data, need get_id_from_deserialized()

        #try:
        #    self.get_obj_by_id()
        #    return self._error_response(code='object-already-exists')
        #except NoResultFound:
        #    pass

        # create object
        obj = self.create_instance()

        # deserialize
        deserialized = self.deserialize(json)

        # update object
        self.before_create(obj, deserialized)
        self.update_obj(obj, deserialized)
        self.after_populated(obj, deserialized)

        # save to database
        obj.rest_add(flush=True)
        self.after_create(obj, deserialized)

        return self.create_response(obj)

    def create_instance(self):
        """
        Create entity object
        Can bwe overridden to e.g. supply constructor parameters
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

    def update_handler(self):
        self.mode = 'UPDATE'

        # parse request body
        json = self.parse_request_body()

        # get object by id
        obj = self.get_obj_by_id_or_create()

        # deserialize
        deserialized = self.deserialize(json)

        # update object
        self.before_update(obj, deserialized)
        self.update_obj(obj, deserialized)
        self.after_populated(obj, deserialized)

        # save to database
        obj.rest_add(flush=True)
        self.after_update(obj, deserialized)

        return self.update_response(obj)

    def get_obj_by_id_or_create(self):
        if not self.allow_create_on_update:
            return self.get_obj_by_id()

        try:
            return self.get_obj_by_id()
        except:
            return self.create_obj()

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

    def run_delete_hooks(self, obj):
        run_hooks_on_delete(obj)

    def delete_obj(self, obj):
        obj.rest_delete(flush=True)

    def after_delete(self):
        pass

    def delete_response(self, obj):
        return {'status': 'ok'}