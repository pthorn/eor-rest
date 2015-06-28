# coding: utf-8

from __future__ import unicode_literals, print_function

import logging
log = logging.getLogger(__name__)

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import NoResultFound

from pyramid.renderers import render_to_response
from pyramid.httpexceptions import HTTPNotFound, HTTPMethodNotAllowed
from pyramid.session import check_csrf_token

from .delegate import DeserializationException
from .serialization import serialize_sqlalchemy_obj, serialize_sqlalchemy_list, update_entity_from_appstruct


class RestViews(object):

    delegates = dict()

    @classmethod
    def register(cls, group='default'):
        """
        @RestViews.register('site') class User(RestDelegate): pass
        """
        def decorate(delegate):
            if delegate.name is None:
                raise ValueError('RestViews.register(): %r must have attribute "name"' % delegate)

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
        for delegate_name, delegate in cls.delegates[group].items():
            # example: eor.rest.default.user.get
            route_name = lambda suffix: 'eor.rest.%s.%s.%s' % (group, delegate_name, suffix)

            def permission(method):
                if isinstance(delegate.permission, dict):
                    try:
                        return delegate.permission[method]
                    except KeyError:
                        return delegate.permission.get('*', None)
                else:
                    return delegate.permission

            # collection resource

            url_pattern = R'%s/%s' % (url_prefix, delegate_name)  # example: /rest/user

            config.add_route(route_name('get'),       url_pattern, request_method='GET',  **kwargs)
            config.add_route(route_name('create'),    url_pattern, request_method='POST', **kwargs)
            config.add_route(route_name('badmethod'), url_pattern, **kwargs)

            config.add_view(cls, attr='get_list', route_name=route_name('get'), renderer='json',
                            decorator=cls.handler_decorator, permission=permission('get'))
            config.add_view(cls, attr='create',  route_name=route_name('create'), renderer='json',
                            decorator=cls.handler_decorator, permission=permission('create'))
            config.add_view(cls, attr='bad_method',  route_name=route_name('badmethod'), renderer='json')

            # item resource

            url_pattern = R'%s/%s/{id}' % (url_prefix, delegate_name)  # example: /rest/user/{id}

            config.add_route(route_name('getbyid'),    url_pattern, request_method='GET',    **kwargs)
            config.add_route(route_name('update'),     url_pattern, request_method='PUT',    **kwargs)
            config.add_route(route_name('delete'),     url_pattern, request_method='DELETE', **kwargs)
            config.add_route(route_name('badmethod2'), url_pattern, **kwargs)

            config.add_view(cls, attr='get_by_id', route_name=route_name('getbyid'), renderer='json',
                            decorator=cls.handler_decorator, permission=permission('getbyid'))
            config.add_view(cls, attr='update',  route_name=route_name('update'), renderer='json',
                            decorator=cls.handler_decorator, permission=permission('update'))
            config.add_view(cls, attr='delete',  route_name=route_name('delete'), renderer='json',
                            decorator=cls.handler_decorator, permission=permission('delete'))
            config.add_view(cls, attr='bad_method',  route_name=route_name('badmethod2'), renderer='json')

            # custom methods TODO

            # for custom_method in delegate:
            #   config.add_route(
            #         '%s-%s-custom' % (cls.name, delegate.name),     # eor-rest-user
            #        R'%s/%s/{id}/{method}' % (url_prefix, delegate.name),  # /rest/user
            #       **kwargs
            #    )
            #
            #   config.add_view(....)

    def __init__(self, request):
        self.request = request
        self.json = None  # for delegate
        self.obj = None   # for delegate

        route_name = request.matched_route.name.split('.')  # eor.rest.default.user.get
        group = route_name[2]
        entity_name = route_name[3]

        try:
            self.delegate = self.delegates[group][entity_name](self)
        except KeyError:
            log.error('RestViews: group %r / entity %r not registered', group, entity_name)
            raise HTTPNotFound()

    def get_list(self):
        """
        GET /prefix/{entity}[?qs]
        parameters:
        """
        #try:
        count, lst = self.delegate.get_obj_list()
        #except SQLAlchemyError as e:
        #    return {'status': 'error', 'message': str(e)}

        return {
            'status': 'ok',
            'count': count,
            'data': serialize_sqlalchemy_list(lst, field_spec=self.delegate.get_fields_for_coll())
        }

    def get_by_id(self):
        """
        GET /prefix/{entity}/{id}
        """
        try:
            obj = self.delegate.get_obj_by_id()
        except NoResultFound:
            return self._error_response(key='object-not-found')

        return {
            'status': 'ok',
            'data': serialize_sqlalchemy_obj(obj, field_spec=self.delegate.get_fields_for_obj())
        }

    def create(self):
        """
        POST /prefix/{entity}
        """

        # TODO check origin?
        check_csrf_token(self.request)  # TODO proper response

        if self.request.content_type != 'application/json':
            return self._error_response(key='bad-content-type')

        try:
            json = self.json = self.request.json_body
        except ValueError as e:
            return self._error_response(key='bad-json', exception=e)

        # check existing


        # create object

        obj = self.obj = self.delegate.create_obj()

        # deserialize

        try:
            deserialized = self.delegate.deserialize(json)
        except DeserializationException as e:
            return {'status': 'invalid', 'errors': str(e)}  # TODO report server validation errors properly!

        # update object

        update_entity_from_appstruct(obj, deserialized)  # TODO do not pass args - accessible in self.views.<...> ?

        self.delegate.after_create_obj(obj, deserialized)

        try:
            obj.rest_add(flush=True)
        except SQLAlchemyError as e:
            log.error('rest update(): database error when saving: %s', e)
            return self._error_response(exception=e)

        return {'status': 'ok', 'id': self.delegate.get_id_from_obj(obj)}

    def update(self):
        """
        POST /prefix/{entity}/{id}
        """

        # TODO check origin?
        check_csrf_token(self.request)  # TODO proper response

        # parse request body

        if self.request.content_type != 'application/json':
            return self._error_response(key='bad-content-type')

        try:
            json = self.json = self.request.json_body
        except ValueError as e:
            return self._error_response(key='bad-json', exception=e)

        # get object by id

        try:
            obj = self.obj = self.delegate.get_obj_by_id()
        except NoResultFound:
            return self._error_response(key='object-not-found')

        # deserialize

        try:
            deserialized = self.delegate.deserialize(json)
        except DeserializationException as e:
            return {'status': 'invalid', 'errors': str(e)}  # TODO report server validation errors properly!

        # update object

        if not self.delegate.before_update_obj(obj, deserialized):
            return {'status': 'ok'}  # TODO

        update_entity_from_appstruct(obj, deserialized)

        self.delegate.after_update_obj(obj, deserialized)

        try:
            obj.rest_add(flush=True)
        except SQLAlchemyError as e:
            log.error('rest update(): database error when saving: %s', e)
            return self._error_response(exception=e)

        return {'status': 'ok', 'id': obj.id}  # TODO

    def delete(self):
        """
        DELETE /prefix/{entity}/{id}
        """

        # TODO check origin?
        check_csrf_token(self.request)  # TODO proper response

        try:
            obj = self.obj = self.delegate.get_obj_by_id()
        except NoResultFound:
            return self._error_response(key='object-not-found')

        try:
            obj.rest_delete(flush=True)
            return {'status': 'ok'}
        except SQLAlchemyError as e:
            return self._error_response(exception=e)

    def custom_view_handler(self):
        """
        POST /prefix/{entity}/{id}/{method}
        """

        # TODO check_csrf_token(self.request)

        pass

    def bad_method(self):
        #log.warn(TODO)
        raise HTTPMethodNotAllowed()

    @classmethod
    def _error_response(cls, key=None, message=None, exception=None):
        """
        return a JSON response with error information
        """
        resp = {'status': 'error'}

        if key:
            resp['key'] = key
        elif exception:
            resp['key'] = 'internal-error'

        if message:
            resp['message'] = message

        if exception:
            resp['message'] = str(exception)

        # TODO return {'status': 'error', 'message': u'Ошибка базы данных при удалении\n' + unicode(e).replace(u"' {'", u"'\n{'")}

        return resp

    # TODO
    @classmethod
    def _check_origin(cls):
        pass

    # TODO
    @classmethod
    def _check_csrf(cls):
        pass

    # TODO error view! this catches all exceptions
    @classmethod
    def handler_decorator(cls, view_handler):

        def replacement(context, request):
            try:
                return view_handler(context, request)
            except Exception as e:
                log.error('rest: unhandled exception: ', e)
                # TODO status?
                return render_to_response('json', cls._error_response(exception=e), request=request)

        return replacement
