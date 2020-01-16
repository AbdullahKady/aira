import datetime as dt
import os
import shutil
import tempfile
from unittest.mock import PropertyMock, patch

from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.core.cache import cache
from django.test import TestCase, override_settings

import numpy as np
import pandas as pd
from freezegun import freeze_time
from model_mommy import mommy
from osgeo import gdal, osr

from aira.models import Agrifield, CropType, IrrigationLog, IrrigationType


def setup_input_file(filename, value, timestamp_str):
    """Save value, which is an np array, to a GeoTIFF file."""
    nodata = 1e8
    value[np.isnan(value)] = nodata
    f = gdal.GetDriverByName("GTiff").Create(filename, 2, 2, 1, gdal.GDT_Float32)
    try:
        timestamp_str = timestamp_str or "1970-01-01"
        f.SetMetadataItem("TIMESTAMP", timestamp_str)
        f.SetGeoTransform((22.0, 0.01, 0, 38.0, 0, -0.01))
        wgs84 = osr.SpatialReference()
        wgs84.ImportFromEPSG(4326)
        f.SetProjection(wgs84.ExportToWkt())
        f.GetRasterBand(1).SetNoDataValue(nodata)
        f.GetRasterBand(1).WriteArray(value)
    finally:
        f = None


class SetupTestDataMixin:
    @classmethod
    def _setup_test_data(cls):
        cls._setup_field_capacity_raster()
        cls._setup_draintime_rasters()
        cls._setup_theta_s_raster()
        cls._setup_pwp_raster()
        cls._setup_meteo_rasters()
        cls._setup_agrifield()

    @classmethod
    def _setup_field_capacity_raster(cls):
        filename = os.path.join(cls.tempdir, "fc.tif")
        setup_input_file(filename, np.array([[1, 1], [1, 1]]), None)

    @classmethod
    def _setup_draintime_rasters(cls):
        filename = os.path.join(cls.tempdir, "a_1d.tif")
        setup_input_file(filename, np.array([[30, 30], [30, 30]]), None)
        filename = os.path.join(cls.tempdir, "b.tif")
        setup_input_file(filename, np.array([[0.95, 0.95], [0.95, 0.95]]), None)

    @classmethod
    def _setup_theta_s_raster(cls):
        filename = os.path.join(cls.tempdir, "theta_s.tif")
        setup_input_file(filename, np.array([[0.5, 0.5], [0.5, 0.5]]), None)

    @classmethod
    def _setup_pwp_raster(cls):
        filename = os.path.join(cls.tempdir, "pwp.tif")
        setup_input_file(filename, np.array([[0.1, 0.1], [0.1, 0.1]]), None)

    @classmethod
    def _setup_meteo_rasters(cls):
        cls._setup_test_raster("rain", "2018-03-15", [[0.0, 0.1], [0.2, 0.3]])
        cls._setup_test_raster("evaporation", "2018-03-15", [[2.1, 2.2], [2.3, 2.4]])
        cls._setup_test_raster("rain", "2018-03-16", [[0.5, 0.6], [0.7, 0.8]])
        cls._setup_test_raster("evaporation", "2018-03-16", [[9.1, 9.2], [9.3, 9.4]])
        cls._setup_test_raster("rain", "2018-03-17", [[0.4, 0.5], [0.6, 0.7]])
        cls._setup_test_raster("evaporation", "2018-03-17", [[9.5, 9.6], [9.7, 9.8]])
        cls._setup_test_raster("rain", "2018-03-18", [[0.3, 0.2], [0.1, 0.0]])
        cls._setup_test_raster("evaporation", "2018-03-18", [[9.6, 9.7], [9.8, 9.9]])

    @classmethod
    def _setup_test_raster(cls, var, datestr, contents):
        subdir = "forecast" if datestr >= "2018-03-18" else "historical"
        filename = os.path.join(
            cls.tempdir, subdir, "daily_{}-{}.tif".format(var, datestr)
        )
        setup_input_file(filename, np.array(contents), datestr)

    @classmethod
    def _setup_agrifield(cls):
        cls.crop_type = mommy.make(
            CropType,
            name="Grass",
            root_depth_max=0.7,
            root_depth_min=1.2,
            max_allowed_depletion=0.5,
            fek_category=4,
            kc_init=0.7,
            kc_mid=0.7,
            kc_end=0.7,
            days_kc_init=10,
            days_kc_dev=20,
            days_kc_mid=20,
            days_kc_late=30,
            planting_date=dt.date(2018, 3, 16),
        )
        cls.irrigation_type = mommy.make(
            IrrigationType, name="Surface irrigation", efficiency=0.60
        )
        cls.user = User.objects.create_user(id=55, username="bob", password="topsecret")
        cls.agrifield = mommy.make(
            Agrifield,
            owner=cls.user,
            name="A field",
            crop_type=cls.crop_type,
            irrigation_type=cls.irrigation_type,
            location=Point(22.0, 38.0),
            area=2000,
        )
        cls.irrigation_log = mommy.make(
            IrrigationLog,
            agrifield=cls.agrifield,
            time=dt.datetime(2018, 3, 15, 7, 0, tzinfo=dt.timezone.utc),
            applied_water=500,
        )


class DataTestCase(TestCase, SetupTestDataMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tempdir = tempfile.mkdtemp()
        os.mkdir(os.path.join(cls.tempdir, "historical"))
        os.mkdir(os.path.join(cls.tempdir, "forecast"))
        cls._setup_test_data()
        h = override_settings(
            AIRA_DATA_HISTORICAL=os.path.join(cls.tempdir, "historical")
        )
        f = override_settings(AIRA_DATA_FORECAST=os.path.join(cls.tempdir, "forecast"))
        s = override_settings(AIRA_DATA_SOIL=cls.tempdir)
        with h, f, s:
            cls.results = cls.agrifield.execute_model()
        cls.timeseries = cls.results["timeseries"]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tempdir)
        super().tearDownClass()


@freeze_time("2018-03-18 13:00:01")
class ExecuteModelTestCase(DataTestCase):
    def test_start_date(self):
        self.assertEqual(self.timeseries.index[0], pd.Timestamp("2018-03-15 23:59"))

    def test_historical_end_date(self):
        self.assertEqual(
            self.results["historical_end_date"], pd.Timestamp("2018-03-17 23:59")
        )

    def test_forecast_start_date(self):
        self.assertEqual(
            self.results["forecast_start_date"], pd.Timestamp("2018-03-18 23:59")
        )

    def test_end_date(self):
        self.assertEqual(self.timeseries.index[-1], pd.Timestamp("2018-03-18 23:59"))

    def test_ks(self):
        self.assertAlmostEqual(self.timeseries.at["2018-03-18 23:59", "ks"], 0.8611415)

    def test_ifinal(self):
        self.assertAlmostEqual(
            self.timeseries.at["2018-03-18 23:59", "ifinal"], 410.3407445
        )

    def test_ifinal_m3(self):
        self.assertAlmostEqual(
            self.timeseries.at["2018-03-18 23:59", "ifinal_m3"], 820.6814889
        )

    def test_effective_precipitation(self):
        var = "effective_precipitation"
        self.assertAlmostEqual(
            self.timeseries.at[pd.Timestamp("2018-03-15 23:59"), var], 0.0
        )
        self.assertAlmostEqual(
            self.timeseries.at[pd.Timestamp("2018-03-16 23:59"), var], 0.4
        )
        self.assertAlmostEqual(
            self.timeseries.at[pd.Timestamp("2018-03-17 23:59"), var], 0.32
        )
        self.assertAlmostEqual(
            self.timeseries.at[pd.Timestamp("2018-03-18 23:59"), var], 0.24
        )

    def test_dr(self):
        self.assertAlmostEqual(
            self.timeseries.at[pd.Timestamp("2018-03-18 23:59"), "dr"], 492.4088933
        )

    def test_theta(self):
        self.assertAlmostEqual(
            self.timeseries.at[pd.Timestamp("2018-03-18 23:59"), "theta"], 0.4816748
        )

    def test_actual_net_irrigation(self):
        var = "actual_net_irrigation"
        self.assertAlmostEqual(
            self.timeseries[var].at[dt.datetime(2018, 3, 15, 23, 59)], 250
        )
        self.assertAlmostEqual(
            self.timeseries.at[dt.datetime(2018, 3, 16, 23, 59), var], 0
        )
        self.assertAlmostEqual(
            self.timeseries.at[dt.datetime(2018, 3, 17, 23, 59), var], 0
        )
        self.assertAlmostEqual(
            self.timeseries.at[dt.datetime(2018, 3, 18, 23, 59), var], 0
        )

    def test_ifinal_theoretical(self):
        var = "ifinal_theoretical"
        self.assertAlmostEqual(
            self.timeseries.at[pd.Timestamp("2018-03-15 23:59"), var], 397.0583333
        )
        self.assertAlmostEqual(
            self.timeseries.at[pd.Timestamp("2018-03-16 23:59"), var], 401.1416669
        )
        self.assertAlmostEqual(
            self.timeseries.at[pd.Timestamp("2018-03-17 23:59"), var], 401.375
        )
        self.assertAlmostEqual(
            self.timeseries.at[pd.Timestamp("2018-03-18 23:59"), var], 401.4333336
        )


class StartOfSeasonTestCase(TestCase):
    def setUp(self):
        self.agrifield = mommy.make(Agrifield)

    @freeze_time("2018-01-01 13:00:01")
    def test_jan_1(self):
        self.assertEqual(self.agrifield.start_of_season, dt.datetime(2017, 3, 15, 0, 0))

    @freeze_time("2018-03-14 13:00:01")
    def test_mar_14(self):
        self.assertEqual(self.agrifield.start_of_season, dt.datetime(2017, 3, 15, 0, 0))

    @freeze_time("2018-03-15 13:00:01")
    def test_mar_15(self):
        self.assertEqual(self.agrifield.start_of_season, dt.datetime(2018, 3, 15, 0, 0))

    @freeze_time("2018-12-31 13:00:01")
    def test_dec_31(self):
        self.assertEqual(self.agrifield.start_of_season, dt.datetime(2018, 3, 15, 0, 0))


_locmemcache = "django.core.cache.backends.locmem.LocMemCache"
_in_covered_area = "aira.models.Agrifield.in_covered_area"


@override_settings(CACHES={"default": {"BACKEND": _locmemcache}})
class NeedsIrrigationTestCase(TestCase):
    def setUp(self):
        self.agrifield = mommy.make(Agrifield, id=1)

    def _set_needed_irrigation_amount(self, amount):
        atimeseries = pd.Series(data=[amount], index=pd.DatetimeIndex(["2020-01-15"]))
        mock_model_run = {
            "forecast_start_date": "2020-01-15",
            "timeseries": {"ifinal": atimeseries},
        }
        cache.set("model_run_1", mock_model_run)

    @patch(_in_covered_area, new_callable=PropertyMock, return_value=True)
    def test_true(self, m):
        self._set_needed_irrigation_amount(42.0)
        self.assertTrue(self.agrifield.needs_irrigation)

    @patch(_in_covered_area, new_callable=PropertyMock, return_value=True)
    def test_false(self, m):
        self._set_needed_irrigation_amount(0)
        self.assertFalse(self.agrifield.needs_irrigation)

    @patch(_in_covered_area, new_callable=PropertyMock, return_value=False)
    def test_not_in_covered_area(self, m):
        self.assertIsNone(self.agrifield.needs_irrigation)

    @patch(_in_covered_area, new_callable=PropertyMock, return_value=True)
    def test_not_in_cache(self, m):
        cache.delete("model_run_1")
        self.assertIsNone(self.agrifield.needs_irrigation)


@freeze_time("2018-03-18 13:00:01")
class DefaultFieldCapacityTestCase(DataTestCase):
    def test_value(self):
        with override_settings(AIRA_DATA_SOIL=self.tempdir):
            self.assertAlmostEqual(self.agrifield.default_field_capacity, 1)

    @patch(_in_covered_area, new_callable=PropertyMock, return_value=False)
    def test_not_in_covered_area(self, m):
        with override_settings(AIRA_DATA_SOIL=self.tempdir):
            self.assertIsNone(self.agrifield.default_field_capacity)


@freeze_time("2018-03-18 13:00:01")
class DefaultWiltingPointTestCase(DataTestCase):
    def test_value(self):
        with override_settings(AIRA_DATA_SOIL=self.tempdir):
            self.assertAlmostEqual(self.agrifield.default_wilting_point, 0.1)

    @patch(_in_covered_area, new_callable=PropertyMock, return_value=False)
    def test_not_in_covered_area(self, m):
        with override_settings(AIRA_DATA_SOIL=self.tempdir):
            self.assertIsNone(self.agrifield.default_wilting_point)


@freeze_time("2018-03-18 13:00:01")
class DefaultThetaSTestCase(DataTestCase):
    def test_value(self):
        with override_settings(AIRA_DATA_SOIL=self.tempdir):
            self.assertAlmostEqual(self.agrifield.default_theta_s, 0.5)

    @patch(_in_covered_area, new_callable=PropertyMock, return_value=False)
    def test_not_in_covered_area(self, m):
        with override_settings(AIRA_DATA_SOIL=self.tempdir):
            self.assertIsNone(self.agrifield.default_theta_s)
