# coding: utf-8

import logging
log = logging.getLogger(__name__)

import sqlalchemy
from sqlalchemy.orm.properties import ColumnProperty, RelationshipProperty
from sqlalchemy.ext.associationproxy import _AssociationCollection
from sqlalchemy.orm.interfaces import ONETOMANY, MANYTOONE, MANYTOMANY

from .config import config


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

    objs_to_keep = target_entity.rest_get_related(appstructs_by_id.keys(), containing_obj, key)
    objs_to_keep_by_id = {getattr(obj, target_id_attr): obj for obj in objs_to_keep}

    # update existing objects
    for obj in objs_to_keep:
        update_entity(obj, appstructs_by_id[getattr(obj, target_id_attr)])

    # create new objects
    for el in appstruct:
        if target_id_attr in el and el[target_id_attr] in objs_to_keep_by_id:
            continue

        new_obj = target_entity()
        update_entity(new_obj, el)
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
            info = mapper.all_orm_descriptors[key].info

            # print(
            #     key,
            #     'PROP:', prop, type(prop),
            #     'ATTR:', obj_attr, type(obj_attr),
            #     'CLASS ATTR:',  getattr(obj.__class__, key), type(getattr(obj.__class__, key)),
            #     'DESCRIPTOR:', mapper.all_orm_descriptors[key],
            #     'INFO:', info
            # )

            if 'efs_category' in info and obj_attr != val:
                log.debug('deleting file id %s', obj_attr)
                from eor_filestore import delete_by_id
                delete_by_id(obj_attr)

            setattr(obj, key, val)
        elif isinstance(obj_attr, _AssociationCollection):
            # gdt AssociationProxy: getattr(obj.__class__, key)
            log.debug('updating association proxy: %s.%s', obj_name, key)

            if 'efs_category' in info:
                from eor_filestore import delete_by_id

                new_files = frozenset(val)

                for old_file in obj_attr:
                    if old_file not in new_files:
                        log.debug('deleting file id %s', old_file)
                        delete_by_id(old_file)

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
