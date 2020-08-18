# coding: utf-8

import logging
log = logging.getLogger(__name__)

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import NoResultFound

from pyramid.renderers import render_to_response
from pyramid.httpexceptions import HTTPNotFound, HTTPMethodNotAllowed
from pyramid.session import check_csrf_token

from .config import config
from .exceptions import *


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

        log.info('get list %s, %s', self.delegate.name, self._log_user())

        try:
            return self.delegate.get_list_handler()
        except SQLAlchemyError as e:
            raise RESTException(code='database-error', exc=e)

    def get_by_id(self):
        """
        GET /prefix/{entity}/{id}
        """

        log.info('get by id %s id %r, %s', self.delegate.name, self.delegate.get_id_from_request(),
            self._log_user())

        try:
            return self.delegate.get_item_handler()
        except NoResultFound:
            raise RESTException(code='object-not-found')
        except SQLAlchemyError as e:
            raise RESTException(code='database-error', exc=e)

    def create(self):
        """
        POST /prefix/{entity}
        """

        log.info('create %s, %r', self.delegate.name, self._log_user())

        try:
            self._security_check()
            return self.delegate.create_handler()
        except SQLAlchemyError as e:
            raise RESTException(code='database-error', exc=e)

    def update(self):
        """
        PUT /prefix/{entity}/{id}
        """

        log.info('update %s id %r, %s', self.delegate.name, self.delegate.get_id_from_request(),
            self._log_user())

        try:
            self._security_check()
            return self.delegate.update_handler()
        except SQLAlchemyError as e:
            raise RESTException(code='database-error', exc=e)

    def delete(self):
        """
        DELETE /prefix/{entity}/{id}
        """

        log.info('delete %s id %r, %s', self.delegate.name, self.delegate.get_id_from_request(),
            self._log_user())

        try:
            self._security_check()

            obj = self.obj = self.delegate.get_obj_by_id()

            self.delegate.before_delete(obj)

            self.delegate.run_delete_hooks(obj)

            self.delegate.delete_obj(obj)

            self.delegate.after_delete()

            return self.delegate.delete_response(obj)
        except SQLAlchemyError as e:
            raise RESTException(code='database-error', exc=e)

    def custom_method(self):
        method = self.request.matched_route.name.split('.', 4)[3]
        method = method[len('custom-'):]
        d = self.delegate.custom_methods[method]

        log.info('custom [%s] %s id %r, %s', method, self.delegate.name,
            self.delegate.get_id_from_request(), self._log_user())

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

    def _security_check(self):
        if config.do_csrf_checks:
            check_csrf_token(self.request)  # TODO proper response
        # TODO check origin?

    def _log_user(self):
        if self.request.user:
            return self.request.user
        else:
            return '<no user>'

def exception_view(context, request):
    return render_to_response('eor-rest-json', context.response(), request=request)
