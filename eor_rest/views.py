# coding: utf-8

import logging
log = logging.getLogger(__name__)

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import NoResultFound

from pyramid.renderers import render_to_response
from pyramid.httpexceptions import HTTPNotFound, HTTPMethodNotAllowed
from pyramid.session import check_csrf_token

from .exceptions import *
from .deserialize import update_entity_from_appstruct


class RestViews(object):

    apis = dict()

    def __init__(self, request):
        self.request = request
        self.json = None  # for delegate
        self.obj = None   # for delegate

        # parse route name: eor-rest.default.user.get

        route_name = request.matched_route.name
        route_split = request.matched_route.name.split('.', 4)

        if not route_name.startswith('eor-rest'):
            log.error('RestViews: bad route name: %r', route_name)
            raise HTTPNotFound()

        api = route_split[1]
        delegate = route_split[2]

        try:
            self.delegate = self.apis[api].delegates[delegate](self)
        except KeyError:
            log.error('RestViews: group %r / entity %r not registered but route exists',
                group, entity_name)
            raise HTTPNotFound()

    def get_list(self):
        """
        GET /prefix/{entity}[?qs]
        parameters:
        """

        try:
            return self.delegate.get_list_handler()
        except SQLAlchemyError as e:
            raise RESTException(code='database-error', exc=e)

    def get_by_id(self):
        """
        GET /prefix/{entity}/{id}
        """

        try:
            obj = self.delegate.get_obj_by_id()

            return {
                'status': 'ok',
                'data': self.delegate.serialize_obj(obj)
            }
        except NoResultFound:
            raise RESTException(code='object-not-found')
        except SQLAlchemyError as e:
            raise RESTException(code='database-error', exc=e)

    def create(self):
        """
        POST /prefix/{entity}
        """

        try:
            # TODO check origin?
            #check_csrf_token(self.request)  # TODO proper response

            # parse request body

            json = self.json = self.delegate.parse_request_body()

            # check existing
            # TODO no ID in request; some objects may have ID in request data, need get_id_from_deserialized()

            #try:
            #    self.delegate.get_obj_by_id()
            #    return self._error_response(code='object-already-exists')
            #except NoResultFound:
            #    pass

            # create object

            obj = self.obj = self.delegate.create_obj()

            # deserialize

            deserialized = self.delegate.deserialize(json)

            # update object

            self.delegate.before_create(obj, deserialized)

            update_entity_from_appstruct(obj, deserialized)

            self.delegate.after_populated(obj, deserialized)

            obj.rest_add(flush=True)

            self.delegate.after_create(obj, deserialized)

            return self.delegate.create_response(obj)
        except SQLAlchemyError as e:
            raise RESTException(code='database-error', exc=e)

    def update(self):
        """
        POST /prefix/{entity}/{id}
        """

        try:
            # TODO check origin?
            #check_csrf_token(self.request)  # TODO proper response

            # parse request body

            json = self.json = self.delegate.parse_request_body()

            # get object by id

            obj = self.obj = self.delegate.get_obj_by_id()

            # deserialize

            deserialized = self.delegate.deserialize(json)

            # update object

            self.delegate.before_update(obj, deserialized)

            update_entity_from_appstruct(obj, deserialized)

            self.delegate.after_populated(obj, deserialized)

            obj.rest_add(flush=True)

            self.delegate.after_update(obj, deserialized)

            return self.delegate.update_response(obj)
        except SQLAlchemyError as e:
            raise RESTException(code='database-error', exc=e)

    def delete(self):
        """
        DELETE /prefix/{entity}/{id}
        """

        try:
            # TODO check origin?
            #check_csrf_token(self.request)  # TODO proper response

            obj = self.obj = self.delegate.get_obj_by_id()

            self.delegate.before_delete(obj)

            self.delegate.delete_obj(obj)

            self.delegate.after_delete()

            return self.delegate.delete_response(obj)
        except SQLAlchemyError as e:
            raise RESTException(code='database-error', exc=e)

    def custom_method(self):
        method = self.request.matched_route.name.split('.', 4)[3]
        method = method[len('custom-'):]
        d = self.delegate.custom_methods[method]

        try:
            if d['item']:
                obj = self.obj = self.delegate.get_obj_by_id()
                return getattr(self.delegate, method)(obj)
            else:
                return getattr(self.delegate, method)()
        except NoResultFound:
            raise RESTException(code='object-not-found')
        except SQLAlchemyError as e:
            raise RESTException(code='database-error', exc=e)

    def bad_method(self):
        #log.warn(TODO)
        raise HTTPMethodNotAllowed()

    # TODO
    @classmethod
    def _check_origin(cls):
        pass

    # TODO
    @classmethod
    def _check_csrf(cls):
        pass


def exception_view(context, request):
    return render_to_response('eor-rest-json', context.response(), request=request)
