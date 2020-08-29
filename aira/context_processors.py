from django.conf import settings
from django.utils.translation import gettext as _


def map(request):
    query_element = ""
    thunderforest_api_key = getattr(settings, "AIRA_THUNDERFOREST_API_KEY", None)
    if thunderforest_api_key:
        query_element = "apikey={}".format(thunderforest_api_key)
    map_js = (
        """
        aira.thunderforestApiKeyQueryElement = "{}";
        aira.mapserverBaseUrl = "{}";
        aira.mapDefaultCenter = [{}];
        aira.mapDefaultZoom = {};
        aira.strings = {{ covered_area: "{}" }};
        """
    ).format(
        query_element,
        settings.AIRA_MAPSERVER_BASE_URL,
        ",".join([str(x) for x in settings.AIRA_MAP_DEFAULT_CENTER]),
        settings.AIRA_MAP_DEFAULT_ZOOM,
        _("Covered area"),
    )
    return {
        "map_js": map_js,
        "google_maps_api_key": getattr(settings, "AIRA_GOOGLE_MAPS_API_KEY", ""),
    }
