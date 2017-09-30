from .views import RestViews


class RestAPI(object):

    def __init__(self, name='default'):
        self.name = name
        self.delegates = {}

        if name in RestViews.apis:
            raise ValueError('RestAPI: duplicate API name %r', name)

        RestViews.apis[name] = self

    def endpoint(self):
        """
        decorator that registers delegates
        api = RestAPI('my-api')
        @api.endpoint()
        class FooEndpoint(RestDelegate):
            ...
        """
        def decorate(delegate):
            if delegate.name is None:
                delegate.name = delegate.__name__.lower()

            if delegate.entity is None:
                raise ValueError('RestViews.register(): %r must have attribute "entity"' % delegate)

            if delegate.name in self.delegates:
                raise ValueError('RestViews.register(): %r: name %r already registered for class %r' % (
                    delegate, delegate.name, cls.delegates[delegate.name]))

            self.delegates[delegate.name] = delegate

            return delegate

        return decorate

    def custom(self):  # decorator for a custom view
        def decorate(method):
            pass
        return decorate

    def add_routes(self, config, url_prefix='/rest', **kwargs):
        for delegate in self.delegates.values():
            self._add_routes_for_endpoint(delegate, config, url_prefix, **kwargs)

    def _add_routes_for_endpoint(self, delegate, config, url_prefix, **kwargs):

        def url_pattern(is_item):
            if is_item:
                # example: /rest/user
                return R'%s/%s/{id}' % (url_prefix, delegate.name)
            else:
                # example: /rest/user/{id}
                return R'%s/%s' % (url_prefix, delegate.name)

        def route_name(suffix):
            # example: eor.rest.default.user.get
            return 'eor-rest.%s.%s.%s' % (self.name, delegate.name, suffix)

        def permission(method):
            if isinstance(delegate.permission, dict):
                try:
                    return delegate.permission[method]
                except KeyError:
                    return delegate.permission.get('*', None)  # TODO no perm in dict -> do not allow access?
            else:
                return delegate.permission

        def register(is_item, route_part, method, attr):
            config.add_route(
                route_name(route_part),
                url_pattern(is_item),
                request_method=method,
                **kwargs
            )
            config.add_view(
                RestViews, attr=attr,
                route_name=route_name(route_part),
                renderer='eor-rest-json',
                permission=permission(method)
            )

        # collection resource

        register(False, 'get-list', 'GET',  'get_list')
        register(False, 'create',   'POST', 'create')
        register(False, 'bad-method-collection', None, 'bad_method')

        # item resource

        register(True, 'get-by-id', 'GET',    'get_by_id')
        register(True, 'update',    'PUT',    'update')
        register(True, 'delete',    'DELETE', 'delete')
        register(True, 'bad-method-item', None, 'bad_method')

        # custom methods