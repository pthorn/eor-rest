# coding; utf-8

import logging
log = logging.getLogger(__name__)

import sqlalchemy
from sqlalchemy.sql import and_, or_, desc
from sqlalchemy.sql.expression import func
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.orm.properties import  ColumnProperty

from .config import config


class RestMixin(object):

    @classmethod
    def rest_get_by_id(cls, id):
        obj = config.sqlalchemy_session().query(cls).get(id)

        if obj is None:
            raise NoResultFound

        return obj

    @classmethod
    def rest_get_by_ids(cls, appstruct):
        ids = [el['id'] for el in appstruct]

        return (config.sqlalchemy_session().query(cls)
            .filter(cls.id.in_(ids))
            .all())

    @classmethod
    def _rest_get_inner_query(cls, session, query, query_params):
        return query

    @classmethod
    def _rest_get_joined_query(cls, session, query, query_params):
        return query

    @classmethod
    def rest_get_list(cls, query_params):
        """
        cls._rest_search_columns = [cls.name, cls.description] - list of columns for search filtering
        :param start: number (default 0)
        :param limit: number or None
        :param order: {col: '', dir: 'asc|desc'} or None
        :param search:
        :param filters:
        :param query: sqlalchemy query
        :return: result of an executed query
        """

        def apply_search(query):
            search_columns = getattr(cls, '_rest_search_columns', None)
            if not search_columns or not 'search' in query_params:
                return query

            search = query_params['search'].lower()

            if len(search_columns) == 1:
                col = search_columns[0]
                search_filter = func.lower(col).like('%' + search + '%')
            else:  # > 1
                clauses = [func.lower(col).like('%' + search + '%') for col in search_columns]
                search_filter = or_(*clauses)

            return query.filter(search_filter)

        def apply_filters(query):
            if 'filters' not in query_params:
                return query

            filters = query_params['filters']

            for key, val in filters.items():
                op, field_name = key.split('_', 1)

                try:
                    field = getattr(cls, field_name)
                except AttributeError:
                    log.warn('RestMixin.rest_get_list(): filter "%s=%s": unknown attribute %s',
                             key, val, field_name)
                    continue

                if op == 'e':
                    query = query.filter(field == val)
                elif op == 'n':
                    query = query.filter(or_(field == val, field == None))
                elif op == 'l':
                    query = query.filter(func.lower(field).like('%' + val.lower() + '%'))
                elif op == 's':
                    query = query.filter(func.lower(field).like(val.lower() + '%'))
                else:
                    log.error('get_for_rest_grid: filter "%s=%s": unknown op: %s' % (key, val, op))

            return query

        def apply_order(query):
            if 'order' not in query_params:
                return query

            order = query_params['order']
            order_split = order['col'].split('.')

            try:
                order_attr = getattr(cls, order_split[0])
            except AttributeError:
                log.error('get_for_rest_grid: sort key %s: unknown attribute %s.%s' % (order['col'], cls.__name__, order['col']))
                return query

            for el in order_split[1:]:
                if not isinstance(order_attr.property, RelationshipProperty):
                    log.error('get_for_rest_grid: sort key %s: not a RelationshipProperty: %s' % (order['col'], str(order_attr.property)))
                    return query

                entity = order_attr.property.mapper.entity

                try:
                    order_attr = getattr(entity, el)
                except AttributeError:
                    log.error('get_for_rest_grid: sort key %s: unknown attribute %s.%s' % (order['col'], entity.__name__, el))
                    return query

            if not isinstance(order_attr.property, ColumnProperty):
                log.error('get_for_rest_grid: sort key %s: not a ColumnProperty: %s' % (order['col'], str(order_attr.property)))
                return query

            return query.order_by(desc(order_attr) if order['dir'] == 'desc' else order_attr)

        def apply_limit(query):
            if 'limit' in query_params:
                query = query.limit(query_params['limit'])

            if 'start' in query_params:
                query = query.offset(query_params['start'])

            return query

        # select * from (select * from users limit 10 offset 10) as u left join files f on u.id = f.user_id
        # http://docs.sqlalchemy.org/en/rel_1_0/orm/tutorial.html#using-subqueries

        session = config.sqlalchemy_session

        q_inner = session().query(cls)
        q_inner = cls._rest_get_inner_query(session, q_inner, query_params)
        q_inner = apply_search(q_inner)
        q_inner = apply_filters(q_inner)
        q_count = q_inner  # count() query should not have ORDER BY
        q_inner = apply_order(q_inner)
        q_inner = apply_limit(q_inner)

        q_joined = q_inner.from_self()
        q_joined = cls._rest_get_joined_query(session, q_joined, query_params)
        q_joined = apply_order(q_joined)

        return q_count.count(), q_joined.all()

    def rest_add(self, flush=False):
        config.sqlalchemy_session().add(self)
        if flush:
            config.sqlalchemy_session().flush()

    def rest_delete(self, flush=False):
        config.sqlalchemy_session().delete(self)
        if flush:
            config.sqlalchemy_session().flush()
