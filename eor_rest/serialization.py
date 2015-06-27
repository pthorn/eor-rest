# coding: utf-8

import logging
log = logging.getLogger(__name__)

import sqlalchemy
from sqlalchemy.orm.properties import ColumnProperty, RelationshipProperty
from sqlalchemy.ext.associationproxy import _AssociationCollection


def _is_sequence(arg):
    """
    see http://stackoverflow.com/questions/10160416/json-serialization-of-sqlalchemy-association-proxies
    """
    return not hasattr(arg, "strip") and (hasattr(arg, "__getitem__") or hasattr(arg, "__iter__"))


def _serialize_value(val):
    """
    serializes associaltion proxies to simple lists
    """
    if _is_sequence(val):
        return list(val)
    return val


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
            res[key] = _serialize_value(getattr(obj, key))
        else:
            p = obj
            r = res
            for el in key[:-1]:
                p = getattr(p, el)
                if el not in r:
                    r[el] = dict()
                r = r[el]
            r[key[-1]] = _serialize_value(getattr(p, key[-1]))

    return res


def serialize_sqlalchemy_list(lst, field_spec=None):
    return [serialize_sqlalchemy_obj(e, field_spec) for e in lst]


def update_one_to_many(entity, key, appstruct):
    pass


def update_entity_from_appstruct(obj, appstruct):
    obj_name = obj.__class__.__name__
    mapper = sqlalchemy.inspect(obj.__class__)

    for key, val in appstruct.items():
        try:
            obj_attr = getattr(obj, key)
        except AttributeError:
            log.warn('attribute not present in object, skipped: %s.%s', obj_name, key)
            continue

        prop = mapper.attrs.get(key)  # does not exist for association proxies

        if isinstance(prop, ColumnProperty):
            setattr(obj, key, val)
        elif isinstance(obj_attr, _AssociationCollection):
            setattr(obj, key, val)
        elif isinstance(prop, RelationshipProperty):
            update_one_to_many(obj, key, val)
        else:
            log.warn('unknown property type, skipped: %s.%s [%s]', obj_name, key, prop)
