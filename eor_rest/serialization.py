# coding: utf-8

import sqlalchemy


def serialize_sqlalchemy_obj(obj, field_spec=None):
    """
    serialize sqlalchemy object

    :param obj: sqlalchemy object
    :param field_spec: list of field names: ['*', '-a', '-b', 'rel.foo'] or ['c', 'd', 'rel.foo']
    :return: serislized structure
    """

    include_all = field_spec is None or field_spec[0] == '*'

    if field_spec[0] == '*':
        field_spec = field_spec[1:]

    mapper = sqlalchemy.inspect(obj.__class__)

    fields = []
    if include_all:
        fields = [p.key for p in mapper.iterate_properties if isinstance(p, sqlalchemy.orm.properties.ColumnProperty)]

    fields.extend(el for el in field_spec if not el.startswith('-'))

    to_remove = frozenset(el[1:] for el in field_spec if el.startswith('-'))
    fields = (el for el in fields if el not in to_remove)

    fields = (el.split('.') if el.find('.') != -1 else el for el in fields)

    # TODO complete hierarchical serialization!
    res = dict()
    for key in fields:
        if isinstance(key, str):
            res[key] = getattr(obj, key)
        else:
            p = obj
            r = res
            for el in key[:-1]:
                p = getattr(p, el)
                if el not in r:
                    r[el] = dict()
                r = r[el]
            r[key[-1]] = getattr(p, key[-1])

    return res


def serialize_sqlalchemy_list(lst, field_spec=None):
    return [serialize_sqlalchemy_obj(e, field_spec) for e in lst]


class _do_not_set(object): pass
do_not_set = _do_not_set()

def update_entity_from_appstruct(entity, appstruct):
    for key, val in appstruct.items():
        if val is not do_not_set:
            setattr(entity, key, val)
