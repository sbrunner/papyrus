from sqlalchemy.orm.util import class_mapper
from sqlalchemy.orm.properties import ColumnProperty

from geoalchemy2.types import Geometry
from geoalchemy2.shape import from_shape, to_shape

import geojson

from shapely.geometry import asShape


class GeoInterface(object):
    """

    Base class for SQLAlchemy/GeoAlchemy mapped classes. Using this class
    mapped objects implement the Python Geo Interface (``__geo_interface__``)
    and expose ``__init__`` and ``__update__`` functions as needed for use with
    :py:class:`papyrus.protocol.Protocol`.

    Using the class is optional, and implementing its own
    ``__geo_interface__``, ``__init__`` and ``__update__`` functions in its
    mapped classes is another option.

    This class can be used as the base class of the user-defined class.
    Example::

        class Spot(GeoInterface, Base):
            __tablename__ = 'spots'
            id = Column(Integer, primary_key=True)
            geom = Column('the_geom', Geometry('POINT', 4326))

    Or as the base class of classes generated by SQLAlchemy's declarative
    layer. Example::

        # constructor=None is required for declarative_base to not
        # provide its own __init__ constructor
        Base = declarative_base(cls=GeoInterface, constructor=None)

        class Spot(Base):
            __tablename__ = 'spots'
            id = Column(Integer, primary_key=True)
            geom = Geometry('the_geom', Geometry('POINT', 4326))
    """

    __add_properties__ = None
    """
    Use this property to make :py:meth:`.__read__` and :py:meth:`.__update__`
    read from, and write to, additional properties. By default column
    properties only are considered. Default is ``None``.

    Example::

        class Spot(Base):
            __tablename__ = 'spots'
            id = Column(Integer, primary_key=True)
            geom = Column('the_geom', Geometry('POINT', 4326))
            type_id = Column(Integer, ForeignKey('spot_type.id')
            type_ = relationship(SpotType)
            type = association_proxy('type_', 'type')
            __add_properties__ = ('type',)

    """

    def __init__(self, feature=None):
        """
        Called by the protocol on object creation.

        Arguments:

        * ``feature`` The GeoJSON feature as received from the client.
        """
        if feature:
            for p in class_mapper(self.__class__).iterate_properties:
                if not isinstance(p, ColumnProperty):
                    continue
                if p.columns[0].primary_key:
                    primary_key = p.key
            if hasattr(feature, 'id') and feature.id is not None:
                setattr(self, primary_key, feature.id)
            self.__update__(feature)

    def __update__(self, feature):
        """
        Called by the protocol on object update.

        Arguments:

        * ``feature`` The GeoJSON feature as received from the client.
        """
        for p in class_mapper(self.__class__).iterate_properties:
            if not isinstance(p, ColumnProperty):
                continue
            col = p.columns[0]
            if isinstance(col.type, Geometry):
                geom = feature.geometry
                if geom and not isinstance(geom, geojson.geometry.Default):
                    srid = col.type.srid
                    shape = asShape(geom)
                    setattr(self, p.key, from_shape(shape, srid=srid))
                    self._shape = shape
            elif not col.primary_key:
                if p.key in feature.properties:
                    setattr(self, p.key, feature.properties[p.key])

        if self.__add_properties__:
            for k in self.__add_properties__:
                setattr(self, k, feature.properties.get(k))

    def __read__(self):
        """
        Called by :py:attr:`.__geo_interface__`.
        """
        id = None
        geom = None
        properties = {}

        for p in class_mapper(self.__class__).iterate_properties:
            if isinstance(p, ColumnProperty):
                if len(p.columns) != 1:  # pragma: no cover
                    raise NotImplementedError
                col = p.columns[0]
                val = getattr(self, p.key)
                if col.primary_key:
                    id = val
                elif isinstance(col.type, Geometry):
                    if hasattr(self, '_shape'):
                        geom = self._shape
                    elif val is not None:
                        geom = to_shape(val)
                elif not col.foreign_keys:
                    properties[p.key] = val

        if self.__add_properties__:
            for k in self.__add_properties__:
                properties[k] = getattr(self, k)

        return geojson.Feature(id=id, geometry=geom, properties=properties)

    @property
    def __geo_interface__(self):
        """ GeoInterface objects implement the Python Geo Interface, making
        them candidates to serialization with the ``geojson`` module, or
        the Papyrus GeoJSON renderer.
        """
        return self.__read__()
