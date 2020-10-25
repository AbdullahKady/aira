import logging
import requests
from django.core.cache import cache
from django.conf import settings

from aira.celery import app
from aira.models import LoRA_ARTAFlowmeter
from aira.utils import group_by_key_value

logger = logging.getLogger(__name__)


@app.task
def calculate_agrifield(agrifield):
    cache_key = "agrifield_{}_status".format(agrifield.id)
    cache.set(cache_key, "being processed", None)
    agrifield.execute_model()
    cache.set(cache_key, "done", None)


@app.task
def add_irrigations_from_telemetric_flowmeters():
    """
    A scheduled task that inserts `AppliedIrrigation` entries for all the
    flowmeters in the system. For the time being, it's only `LoRA_ARTAFlowmeter`
    """
    if settings.THE_THINGS_NETWORK_ACCESS_KEY:
        _add_irrigations_for_LoRA_ARTA_flowmeters()


def _add_irrigations_for_LoRA_ARTA_flowmeters():
    data_points_grouped_by_device = _request_the_things_network_digest()
    for device_id, data_points in data_points_grouped_by_device.items():
        try:
            flowmeter = LoRA_ARTAFlowmeter.objects.get(device_id=device_id)
            flowmeter.create_irrigations_in_bulk(data_points)
        except LoRA_ARTAFlowmeter.DoesNotExist:
            logger.warn(
                (
                    "Got a non-existing flowmeter through TTN."
                    "Flowmeter ID in retrieved from TTN: %s"
                ),
                device_id,
            )


def _request_the_things_network_digest(since="1d"):
    headers = {"Authorization": f"key {settings.THE_THINGS_NETWORK_ACCESS_KEY}"}
    url = f"{settings.THE_THINGS_NETWORK_QUERY_URL}?last={since}"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception()
    filtered_data = [d for d in response.json() if d["SensorFrequency"] is not None]
    return group_by_key_value(filtered_data, "device_id")
