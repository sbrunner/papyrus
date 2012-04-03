import decimal
import datetime
try:
    from cStringIO import StringIO
except ImportError: # pragma: no cover
    from StringIO import StringIO

import geojson
from geojson.codec import PyGFPEncoder as GeoJSONEncoder

from xsd import get_class_xsd


class Encoder(GeoJSONEncoder):
    # SQLAlchemy's Reflecting Tables mechanism uses decimal.Decimal
    # for numeric columns and datetime.date for dates. simplejson
    # does'nt deal with these types. This class provides a simple
    # encoder to deal with objects of these types.

    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        return GeoJSONEncoder.default(self, obj)

class GeoJSON(object):
    """ GeoJSON renderer.

    This class is actually a renderer factory helper, implemented in
    the same way as Pyramid's JSONP renderer.

    Configure a GeoJSON renderer using the ``add_renderer`` method on
    the Configurator object:

    .. code-block:: python

        from papyrus.renderers import GeoJSON

        config.add_renderer('geojson', GeoJSON())

    Once this renderer has been registered as above , you can use
    ``geojson`` as the ``renderer`` parameter to ``@view_config``
    or to the ``add_view`` method on the Configurator object:

    .. code-block:: python

        @view_config(renderer='geojson')
        def myview(request):
            return Feature(id=1, geometry=Point(1, 2), properties=dict(foo='bar'))

    The GeoJSON renderer supports `JSONP <http://en.wikipedia.org/wiki/JSONP>`_:

    - If there is a parameter in the request's HTTP query string that matches
      the ``jsonp_param_name`` of the registered JSONP renderer (by default,
      ``callback``), the renderer will return a JSONP response.
    
    - If there is no callback parameter in the request's query string, the
      renderer will return a 'plain' JSON response.

    By default the renderer treats lists and tuples as feature collections. If
    you want lists and tuples to be treated as geometry collections, set
    ``collection_type`` to ``'GeometryCollection'``:

    .. code-block:: python

        config.add_renderer('geojson', GeoJSON(collection_type='GeometryCollection')

    """

    def __init__(self, jsonp_param_name='callback',
                 collection_type=geojson.factory.FeatureCollection):
        self.jsonp_param_name = jsonp_param_name
        if isinstance(collection_type, basestring):
            collection_type = getattr(geojson.factory, collection_type)
        self.collection_type = collection_type

    def __call__(self, info):
        def _render(value, system):
            if isinstance(value, (list, tuple)):
                value = self.collection_type(value)
            ret = geojson.dumps(value, cls=Encoder, use_decimal=True)
            request = system.get('request')
            if request is not None:
                response = request.response
                ct = response.content_type
                if ct == response.default_content_type:
                    callback = request.params.get(self.jsonp_param_name)
                    if callback is None:
                        response.content_type = 'application/json'
                    else:
                        response.content_type = 'text/javascript'
                        ret = '%(callback)s(%(json)s);' % {'callback': callback,
                                                           'json': ret}
            return ret
        return _render


class XSD(object):
    """ XSD renderer.

    An XSD renderer generate an XML schema document from an SQLAlchemy
    Table object.

    Configure a XSD renderer using the ``add_renderer`` method on
    the Configurator object:

    .. code-block:: python

        from papyrus.renderers import XSD

        config.add_renderer('xsd', XSD())

    Once this renderer has been registered as above , you can use
    ``xsd`` as the ``renderer`` parameter to ``@view_config``
    or to the ``add_view`` method on the Configurator object:

    .. code-block:: python

        from myapp.models import Spot

        @view_config(renderer='xsd')
        def myview(request):
            return Spot.__table__

    By default, the XSD renderer will skip columns which are primary keys or
    foreign keys.

    If you wish to include primary keys then pass ``include_primary_keys=True``
    when creating the XSD object, for example:

    .. code-block:: python

        from papyrus.renderers import XSD

        config.add_renderer('xsd', XSD(include_primary_keys=True))

    If you wish to include foreign keys then pass ``include_foreign_keys=True``
    when creating the XSD object, for example:

    .. code-block:: python

        from papyrus.renderers import XSD

        config.add_renderer('xsd', XSD(include_foreign_keys=True))

    The XSD renderer does not handle SQLAlchemy `relationship properties
    <http://docs.sqlalchemy.org/en/latest/orm/relationships.html#sqlalchemy.orm.relationship>`_,
    nor does it handle `association proxies
    http://docs.sqlalchemy.org/en/latest/orm/extensions/associationproxy.html`_.

    If you wish to handle relationship properties at application level then
    register a ``relationship_property_callback`` when creating the XSD object.
    Likewise, if you wish to handle association proxies then register
    a ``association_proxy_callback``.

    The callbacks are called with the following args:

    * ``tb`` A `TreeBuilder
      <http://docs.python.org/library/xml.etree.elementtree.html#xml.etree.ElementTree.TreeBuilder>`_
      object, which can be used to add elements to the XSD.
    * ``key`` The name of the class property.
    * ``property`` The class property.

    Callback example:

    .. code-block: python

        from papyrus.xsd import tag

        def callback(tb, key, property):
            attrs = {}
            attrs['minOccurs'] = str(0)
            attrs['nillable'] = 'true'
            attrs['name'] = property.key
            with tag(tb, 'xsd:element', attrs) as tb:
                with tag(tb, 'xsd:simpleType') as tb:
                    with tag(tb, 'xsd:restriction',
                             {'base': 'xsd:string'}) as tb:
                        for enum in ('male', 'female'):
                            with tag(tb, 'xsd:enumeration',
                                     {'value': enum}):
                                pass
    """

    def __init__(self,
                 include_primary_keys=False,
                 include_foreign_keys=False,
                 relationship_property_callback=None,
                 association_proxy_callback=None):
        self.include_primary_keys = include_primary_keys
        self.include_foreign_keys = include_foreign_keys
        self.relationship_property_callback = relationship_property_callback
        self.association_proxy_callback = association_proxy_callback

    def __call__(self, table):
        def _render(cls, system):
            request = system.get('request')
            if request is not None:
                response = request.response
                response.content_type = 'application/xml'
                relatcb = self.relationship_property_callback
                proxycb = self.association_proxy_callback
                io = get_class_xsd(StringIO(), cls,
                    include_primary_keys=self.include_primary_keys,
                    include_foreign_keys=self.include_foreign_keys,
                    relationship_property_callback=relatcb,
                    association_proxy_callback=proxycb)
                return io.getvalue()
        return _render
