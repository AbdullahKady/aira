from decimal import Decimal
import requests
from django.core.cache import cache
from django.conf import settings

from aira.celery import app
from aira.models import AppliedIrrigation, TelemetricFlowmeter
from aira.utils import group_by_key_value


@app.task
def calculate_agrifield(agrifield):
    cache_key = "agrifield_{}_status".format(agrifield.id)
    cache.set(cache_key, "being processed", None)
    agrifield.execute_model()
    cache.set(cache_key, "done", None)


@app.task
def add_irrigations_from_telemetric_flowmeters():
    """
    A scheduled task that inserts AppliedIrrigations for all the flowmeters in
    the system. For the time being, it's only "LoRA_ARTA"
    """
    if settings.THE_THINGS_NETWORK_ACCESS_KEY:
        _add_irrigations_for_LoRA_ARTA_flowmeters()


def _add_irrigations_for_LoRA_ARTA_flowmeters():
    data_points_grouped_by_device = _request_the_things_network_digest()
    for device_id, data_points in data_points_grouped_by_device.items():
        try:
            flowmeter = TelemetricFlowmeter.objects.get(
                device_id=device_id, system_type="LoRA_ARTA"
            )
        except TelemetricFlowmeter.DoesNotExist:
            continue  # TODO: Log to an error handler?
        _bulk_create_irrigations(flowmeter, data_points)


def _calculate_water_volume_LoRA_ARTA(flowmeter, point):
    # TODO: Do we need the water percentage anymore?
    return (
        Decimal((1 / flowmeter.water_percentage))
        * (flowmeter.report_frequency_in_minutes * point["SensorFrequency"])
        / flowmeter.conversion_rate
    )


def _bulk_create_irrigations(flowmeter, data_points):
    """
    Creates the irrigations reported in data_points in bulk (per flowmeter)
    NOTE: We use `ignore_conflicts` in case ttn reports duplicate data points
    either as a problem on their side, or a timing problem from ours. So with
    a `unique_together` constraint on the volume and the timestamp we can avoid that
    """
    kwargs_list = [
        {
            "is_flowmeter_reported": True,
            "irrigation_type": "VOLUME_OF_WATER",
            "supplied_water_volume": _calculate_water_volume_LoRA_ARTA(
                flowmeter, point
            ),
            "agrifield_id": flowmeter.agrifield_id,
            "timestamp": point["time"],
        }
        for point in data_points
    ]
    AppliedIrrigation.objects.bulk_create(
        [AppliedIrrigation(**kwargs) for kwargs in kwargs_list], ignore_conflicts=True
    )


def _request_the_things_network_digest(since="1d"):
    headers = {"Authorization": f"key {settings.THE_THINGS_NETWORK_ACCESS_KEY}"}
    url = f"{settings.THE_THINGS_NETWORK_QUERY_URL}?last={since}"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception()
    filtered_data = [d for d in response.json() if d["SensorFrequency"] is not None]
    return group_by_key_value(filtered_data, "device_id")
