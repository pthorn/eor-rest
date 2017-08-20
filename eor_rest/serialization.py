# coding: utf-8

import logging
log = logging.getLogger(__name__)

import sqlalchemy
from sqlalchemy.orm.properties import ColumnProperty, RelationshipProperty
from sqlalchemy.ext.associationproxy import _AssociationCollection
from sqlalchemy.orm.interfaces import ONETOMANY, MANYTOONE, MANYTOMANY

from .config import config


def _is_sequence(arg):
    """
    see http://stackoverflow.com/questions/10160416/json-serialization-of-sqlalchemy-association-proxies
    """
    return not hasattr(arg, "strip") and (hasattr(arg, "__getitem__") or hasattr(arg, "__iter__"))


def _serialize_value(val, func=None, obj=None):
    """
    serializes associaltion proxies to simple lists
    """
    if func:
        val = func(val, obj)

    if _is_sequence(val):
        return list(val)

    return val


def serialize_sqlalchemy_obj(obj, field_spec):
    """
    serialize sqlalchemy object

    :param obj: sqlalchemy object
    :param field_spec: dictionary
       example: {'*', True, 'a': False, 'b': False, 'c': {...}}
    :return: serialized structure
    """
    if obj is None:
        return None

    # in case of Session().query(entity, extra columns)
    try:
        obj = obj[0]
    except:
        pass

    obj_name = obj.__class__.__name__
    mapper = sqlalchemy.inspect(obj.__class__)

    try:
        include_all_own = field_spec.get('*', False)
    except AttributeError as e:
        log.error('serialize_sqlalchemy_obj(): bad field_spec: %r', field_spec)
        raise

    fields = {}

    if include_all_own:
        for p in mapper.column_attrs:
            fields[p.key] = True

    for k in mapper.attrs.keys():
        info = mapper.all_orm_descriptors[k].info
        if 'er_serialize' in info:
            fields[k] = info['er_serialize']

    fields.update(field_spec)

    for k in mapper.attrs.keys():
        info = mapper.all_orm_descriptors[k].info
        if 'er_ser_fn' in info and fields.get(k) == True:
            fields[k] = info['er_ser_fn']

    res = dict()

    for key, control in fields.items():
        if key == '*' or control == False:
            continue

        try:
            obj_attr = getattr(obj, key)
        except AttributeError:
            log.warn('attribute not present in object, skipped: %s.%s', obj_name, key)
            continue

        prop = mapper.attrs.get(key)  # does not exist for association proxies

        if isinstance(control, dict):
            if prop.uselist:
                res[key] = serialize_sqlalchemy_list(obj_attr, control)
            else:
                res[key] = serialize_sqlalchemy_obj(obj_attr, control)
        elif callable(control):
            res[key] = _serialize_value(obj_attr, control, obj)
        elif control == True:
            res[key] = _serialize_value(obj_attr)
        else:
            log.error('bad control value %r, skipped: %s.%s', control, obj_name, key)

    return res


def serialize_sqlalchemy_list(lst, field_spec):
    return [serialize_sqlalchemy_obj(e, field_spec) for e in lst]


def update_one_to_many(containing_obj, key, appstruct):
    """
    Update a collection attribute.

    :param containing_obj: sqlalchemy entity object
    :param key: string, such that getattr(containing_obj, key) returns the collection attribute
    :param appstruct:  list of dicts with or without ID fields, e.g. [{'id': 1, 'name': 'Foo'}, {'name': 'Bar'}]
    :return: nothing
    """

    mapper = sqlalchemy.inspect(containing_obj.__class__)
    prop = getattr(mapper.attrs, key)
    target_entity = prop.mapper.class_

    target_id_attr = 'id'

    appstructs_by_id = {el[target_id_attr]: el for el in appstruct if target_id_attr in el}

    objs_to_keep = target_entity.rest_get_related(appstructs_by_id.keys(), containing_obj)
    objs_to_keep_by_id = {getattr(obj, target_id_attr): obj for obj in objs_to_keep}

    # update existing objects
    for obj in objs_to_keep:
        update_entity_from_appstruct(obj, appstructs_by_id[getattr(obj, target_id_attr)])

    # create new objects
    for el in appstruct:
        if target_id_attr in el and el[target_id_attr] in objs_to_keep_by_id:
            continue

        new_obj = target_entity()
        update_entity_from_appstruct(new_obj, el)
        objs_to_keep.append(new_obj)

    setattr(containing_obj, key, objs_to_keep)


def update_many_to_many(containing_obj, key, appstruct):
    """
    :param containing_obj:
    :param key:
    :param appstruct: list of IDs, like [1, 2, 3]
    :return:
    """
    entity = containing_obj.__class__
    mapper = sqlalchemy.inspect(entity)
    prop = getattr(mapper.attrs, key)  # RelationshipProperty
    target_entity = prop.mapper.class_



    objs_to_keep = target_entity.rest_get_by_ids(appstruct)
    setattr(containing_obj, key, objs_to_keep)


def update_entity(obj, appstruct):
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
            #print(key, 'PROP:', prop, type(prop), 'ATTR:', obj_attr, type(obj_attr), 'CLASS ATTR:',  getattr(obj.__class__, key), type(getattr(obj.__class__, key)))
            setattr(obj, key, val)
        elif isinstance(obj_attr, _AssociationCollection):
            # gdt AssociationProxy: getattr(obj.__class__, key)
            log.debug('updating association proxy: %s.%s', obj_name, key)
            setattr(obj, key, val)
        elif isinstance(prop, RelationshipProperty):
            if not prop.uselist:
                log.warn('relationship property %s.%s: uselist==False not yet supported', obj_name, key, prop.direction)
                continue
            if prop.direction == ONETOMANY:
                log.debug('updating relationship property %s.%s, one to many', obj_name, key)
                update_one_to_many(obj, key, val)
            elif prop.direction == MANYTOMANY:
                log.debug('updating relationship property %s.%s, many to many', obj_name, key)
                update_many_to_many(obj, key, val)
            else:
                log.warn('updating relationship property %s.%s: direction %r not yet supported', obj_name, key, prop.direction)
        else:
            log.warn('unknown property type, skipped: %s.%s [%s]', obj_name, key, prop)


def update_entity_from_appstruct(obj, appstruct):
    with config.sqlalchemy_session.no_autoflush:
        update_entity(obj, appstruct)
