# coding: utf-8

import sqlalchemy

import logging
log = logging.getLogger(__name__)


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

    if _is_sequence(val) and not isinstance(val, dict):
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
