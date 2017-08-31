# coding: utf-8

import logging
log = logging.getLogger(__name__)

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import NoResultFound

from pyramid.renderers import render_to_response
from pyramid.httpexceptions import HTTPNotFound, HTTPMethodNotAllowed
from pyramid.session import check_csrf_token

from .exceptions import *
from .serialization import update_entity_from_appstruct


class RestViews(object):

    delegates = dict()

    @classmethod
    def register(cls, group='default'):
        """
        @RestViews.register('site') class User(RestDelegate): pass
        """
        def decorate(delegate):
            if delegate.name is None:
                delegate.name = delegate.__name__.lower()

            if delegate.entity is None:
                raise ValueError('RestViews.register(): %r must have attribute "entity"' % delegate)

            if delegate.name in cls.delegates:
                raise ValueError('RestViews.register(): %r: name %r already registered for class %r' % (
                    delegate, delegate.name, cls.delegates[delegate.name]))

            if group not in cls.delegates:
                cls.delegates[group] = dict()

            cls.delegates[group][delegate.name] = delegate

            return delegate

        return decorate

    @classmethod
    def configure(cls, config, group='default', url_prefix='/rest', **kwargs):
        """
        RestViews.configure(config, group='site', url_prefix='/rest', factory=ebff('admin-panel'))
        """
        if group not in cls.delegates:
            if group == 'default':
                return
            else:
                raise RuntimeError('group %r does not exist' % group)

        for delegate_name, delegate in cls.delegates[group].items():
            # example: eor.rest.default.user.get
            route_name = lambda suffix: 'eor.rest.%s.%s.%s' % (group, delegate_name, suffix)

            def permission(method):
                if isinstance(delegate.permission, dict):
                    try:
                        return delegate.permission[method]
                    except KeyError:
                        return delegate.permission.get('*', None)  # TODO no perm in dict -> do not allow access?
                else:
                    return delegate.permission

            # collection resource

            url_pattern = R'%s/%s' % (url_prefix, delegate_name)  # example: /rest/user

            config.add_route(route_name('get'),       url_pattern, request_method='GET',  **kwargs)
            config.add_route(route_name('create'),    url_pattern, request_method='POST', **kwargs)
            config.add_route(route_name('badmethod'), url_pattern, **kwargs)

            config.add_view(cls, attr='get_list', route_name=route_name('get'), renderer='eor-rest-json',
                            permission=permission('get'))
            config.add_view(cls, attr='create',  route_name=route_name('create'), renderer='eor-rest-json',
                            permission=permission('create'))
            config.add_view(cls, attr='bad_method',  route_name=route_name('badmethod'), renderer='eor-rest-json')

            # item resource

            url_pattern = R'%s/%s/{id}' % (url_prefix, delegate_name)  # example: /rest/user/{id}

            config.add_route(route_name('getbyid'),    url_pattern, request_method='GET',    **kwargs)
            config.add_route(route_name('update'),     url_pattern, request_method='PUT',    **kwargs)
            config.add_route(route_name('delete'),     url_pattern, request_method='DELETE', **kwargs)
            config.add_route(route_name('badmethod2'), url_pattern, **kwargs)

            config.add_view(cls, attr='get_by_id', route_name=route_name('getbyid'), renderer='eor-rest-json',
                            permission=permission('getbyid'))
            config.add_view(cls, attr='update',  route_name=route_name('update'), renderer='eor-rest-json',
                            permission=permission('update'))
            config.add_view(cls, attr='delete',  route_name=route_name('delete'), renderer='eor-rest-json',
                            permission=permission('delete'))
            config.add_view(cls, attr='bad_method',  route_name=route_name('badmethod2'), renderer='eor-rest-json')

    def __init__(self, request):
        self.request = request
        self.json = None  # for delegate
        self.obj = None   # for delegate

        # parse route name: eor.rest.default.user.get

        if not request.matched_route.name.startswith('eor.rest'):
            log.error('RestViews: bad route name: %r', route_name)
            raise HTTPNotFound()

        route_name = request.matched_route.name.split('.')
        group = route_name[2]
        entity_name = route_name[3]

        try:
            self.delegate = self.delegates[group][entity_name](self)
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
