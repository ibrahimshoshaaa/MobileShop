"""Generic (de)serialization for everything ERPCommandEngine's repositories
store: frozen dataclasses from shared/models/erp.py (some nesting others,
e.g. Sale containing SaleItem/Payment tuples) and, in a few places, plain
dicts (transfers, returns, settings). Tags each non-JSON-native type so it
round-trips exactly, including which dataclass to reconstruct.
"""
from __future__ import annotations

import dataclasses
from datetime import date, datetime
from decimal import Decimal

import shared.models.erp as erp_models

# name -> class, for every frozen dataclass in the domain model. Used to
# reconstruct the correct type on load instead of leaving everything as
# plain dicts.
TYPE_REGISTRY: dict[str, type] = {
    name: obj
    for name, obj in vars(erp_models).items()
    if dataclasses.is_dataclass(obj) and isinstance(obj, type)
}


def serialize_value(value):
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            "__dataclass__": type(value).__name__,
            "fields": {f.name: serialize_value(getattr(value, f.name)) for f in dataclasses.fields(value)},
        }
    if isinstance(value, Decimal):
        return {"__decimal__": str(value)}
    if isinstance(value, datetime):
        return {"__datetime__": value.isoformat()}
    if isinstance(value, date):
        return {"__date__": value.isoformat()}
    if isinstance(value, frozenset):
        return {"__frozenset__": [serialize_value(v) for v in value]}
    if isinstance(value, tuple):
        return {"__tuple__": [serialize_value(v) for v in value]}
    if isinstance(value, list):
        return [serialize_value(v) for v in value]
    if isinstance(value, dict):
        # Tagged distinctly from the dataclass-fields dict shape above so a
        # plain domain dict (e.g. a transfer record) round-trips as a plain
        # dict, not something deserialize_value tries to specially unpack.
        return {"__plain_dict__": {k: serialize_value(v) for k, v in value.items()}}
    return value  # str, int, bool, float, None


def deserialize_value(value):
    if isinstance(value, dict):
        if "__dataclass__" in value:
            cls = TYPE_REGISTRY[value["__dataclass__"]]
            kwargs = {k: deserialize_value(v) for k, v in value["fields"].items()}
            return cls(**kwargs)
        if "__decimal__" in value:
            return Decimal(value["__decimal__"])
        if "__datetime__" in value:
            return datetime.fromisoformat(value["__datetime__"])
        if "__date__" in value:
            return date.fromisoformat(value["__date__"])
        if "__frozenset__" in value:
            return frozenset(deserialize_value(v) for v in value["__frozenset__"])
        if "__tuple__" in value:
            return tuple(deserialize_value(v) for v in value["__tuple__"])
        if "__plain_dict__" in value:
            return {k: deserialize_value(v) for k, v in value["__plain_dict__"].items()}
        # Shouldn't normally be reached — every dict this serializer produces
        # is tagged — but fall back to a shallow pass-through rather than
        # raising, in case older untagged data is ever loaded.
        return {k: deserialize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [deserialize_value(v) for v in value]
    return value
