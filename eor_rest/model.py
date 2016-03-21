# coding; utf-8

import logging
log = logging.getLogger(__name__)

import sqlalchemy
from sqlalchemy.sql import and_, or_, desc
from sqlalchemy.sql.expression import func

from .config import config


class RestMixin(object):

    @classmethod
    def rest_get_by_id(cls, id):
        return (config.sqlalchemy_session().query(cls)
            .filter(cls.id == id)
            .one())

    @classmethod
    def rest_get_by_ids(cls, ids):
        return (config.sqlalchemy_session().query(cls)
            .filter(cls.id.in_(ids))
            .all())

    @classmethod
    def rest_get_count(cls):
        return config.sqlalchemy_session().query(cls).count()

    @classmethod
    def _rest_get_inner_query(cls, session, query_params):
        return session().query(cls)

    @classmethod
    def _rest_get_joined_query(cls, filtered_query, query_params):
        return filtered_query

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

            from sqlalchemy.orm.relationships import RelationshipProperty
            from sqlalchemy.orm.properties import  ColumnProperty

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

        # select * from (select * from users limit 10 offset 10) as u left join files f on u.id = f.user_id
        # http://docs.sqlalchemy.org/en/rel_1_0/orm/tutorial.html#using-subqueries

        q_filtered = cls._rest_get_inner_query(config.sqlalchemy_session, query_params)
        q_filtered = apply_search(q_filtered)
        q_filtered = apply_filters(q_filtered)
        q_filtered = apply_order(q_filtered)

        q_limited = q_filtered.limit(query_params.get('limit', 25))  # TODO 25
        if 'start' in query_params:
            q_limited = q_limited.offset(query_params['start'])

        q_joined = cls._rest_get_joined_query(q_limited, query_params)  # .from_self()
        # TODO q_joined = apply_order_2(q_joined)

        return q_filtered.count(), q_joined.all()

    def rest_add(self, flush=False):
        config.sqlalchemy_session().add(self)
        if flush:
            config.sqlalchemy_session().flush()

    def rest_delete(self, flush=False):
        config.sqlalchemy_session().delete(self)
        if flush:
            config.sqlalchemy_session().flush()
