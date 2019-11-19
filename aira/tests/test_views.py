import datetime as dt
import os
import shutil
import tempfile
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

import numpy as np
from hspatial.test import setup_test_raster
from model_mommy import mommy

from aira.models import Agrifield, IrrigationLog
from aira.tests import RandomMediaRootMixin


class TestDataMixin:
    def setUp(self):
        super().setUp()
        self.tempdir = tempfile.mkdtemp()
        self.settings_overrider = override_settings(AIRA_DATA_SOIL=self.tempdir)
        self.settings_overrider.__enter__()
        self._create_rasters()
        self._create_user()
        self._create_agrifield()

    def _create_user(self):
        self.alice = User.objects.create_user(
            username="alice", password="topsecret", is_active=True
        )

    def _create_agrifield(self):
        self.agrifield = mommy.make(
            Agrifield,
            name="hello",
            location=Point(22.01, 37.99),
            owner=self.alice,
            irrigation_type__efficiency=0.85,
            crop_type__max_allowed_depletion=0.40,
            crop_type__root_depth_max=0.50,
            crop_type__root_depth_min=0.30,
        )

    def tearDown(self):
        self.settings_overrider.__exit__(None, None, None)
        shutil.rmtree(self.tempdir)

    def _create_rasters(self):
        self._create_fc()
        self._create_pwp()
        self._create_theta_s()

    def _create_fc(self):
        setup_test_raster(
            os.path.join(self.tempdir, "fc.tif"),
            np.array([[0.20, 0.23, 0.26], [0.29, 0.32, 0.35], [0.38, 0.41, 0.44]]),
        )

    def _create_pwp(self):
        setup_test_raster(
            os.path.join(self.tempdir, "pwp.tif"),
            np.array([[0.06, 0.07, 0.08], [0.09, 0.10, 0.11], [0.12, 0.13, 0.14]]),
        )

    def _create_theta_s(self):
        setup_test_raster(
            os.path.join(self.tempdir, "theta_s.tif"),
            np.array([[0.38, 0.39, 0.40], [0.41, 0.42, 0.43], [0.44, 0.45, 0.46]]),
        )


class TestFrontPageView(TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.settings_overrider = override_settings(AIRA_DATA_HISTORICAL=self.tempdir)
        self.settings_overrider.__enter__()
        open(os.path.join(self.tempdir, "daily_rain-2018-04-19.tif"), "w").close()
        self.user = mommy.make(User, username="batman", is_active=True)
        self.user.set_password("thegoatandthesheep")
        self.user.save()

    def tearDown(self):
        self.settings_overrider.__exit__(None, None, None)
        shutil.rmtree(self.tempdir)

    def test_front_page_view(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)

    def test_registration_link_when_anonymous_on_front_page_view(self):
        resp = self.client.get("/")
        self.assertContains(resp, "Register")

    def test_no_registration_link_when_logged_on_front_page_view(self):
        resp = self.client.login(username="batman", password="thegoatandthesheep")
        self.assertTrue(resp)
        resp = self.client.get("/")
        self.assertTemplateUsed(resp, "aira/frontpage/main.html")
        self.assertNotContains(resp, "Register")

    def test_start_and_end_dates(self):
        response = self.client.get("/")
        self.assertContains(
            response,
            (
                'Time Period: <span class="text-success">2018-04-19</span> : '
                '<span class="text-success">2018-04-18</span>'
            ),
            html=True,
        )


class TestAgrifieldListView(TestCase):
    def setUp(self):
        self.user = mommy.make(User, username="batman", is_active=True)
        # mommy.make is not hashing the password
        self.user.set_password("thegoatandthesheep")
        self.user.save()

    def test_home_view_denies_anynomous(self):
        resp = self.client.get("/home/", follow=True)
        self.assertRedirects(resp, "/accounts/login/?next=/home/")

    def test_home_view_loads_user(self):
        self.client.login(username="batman", password="thegoatandthesheep")
        resp = self.client.get("/home/")
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "aira/home/main.html")


class UpdateAgrifieldViewTestCase(TestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        self._make_request()

    def _make_request(self):
        self.client.login(username="alice", password="topsecret")
        self.response = self.client.get(
            "/update_agrifield/{}/".format(self.agrifield.id)
        )

    def test_response_contains_agrifield_name(self):
        self.assertContains(self.response, "hello")

    def test_default_irrigation_efficiency(self):
        self.assertContains(
            self.response,
            '<span id="default-irrigation-efficiency">0.85</span>',
            html=True,
        )

    def test_default_max_allowed_depletion(self):
        self.assertContains(
            self.response,
            '<span id="default-max_allowed_depletion">0.40</span>',
            html=True,
        )

    def test_default_root_depth_max(self):
        self.assertContains(
            self.response, '<span id="default-root_depth_max">0.5</span>', html=True
        )

    def test_default_root_depth_min(self):
        self.assertContains(
            self.response, '<span id="default-root_depth_min">0.3</span>', html=True
        )

    def test_default_irrigation_optimizer(self):
        self.assertContains(
            self.response,
            '<span id="default-irrigation-optimizer">0.5</span>',
            html=True,
        )

    def test_default_field_capacity(self):
        self.assertContains(
            self.response, '<span id="default-field-capacity">0.32</span>', html=True
        )

    def test_default_wilting_point(self):
        self.assertContains(
            self.response, '<span id="default-wilting-point">0.10</span>', html=True
        )

    def test_default_theta_s(self):
        self.assertContains(
            self.response, '<span id="default-theta_s">0.42</span>', html=True
        )


class CreateAgrifieldViewTestCase(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="topsecret")
        self.client.login(username="alice", password="topsecret")
        self.response = self.client.get("/create_agrifield/alice/")

    def test_status_code(self):
        self.assertEqual(self.response.status_code, 200)


class AgrifieldTimeseriesViewTestCase(TestCase):
    def setUp(self):
        self._create_stuff()
        self._login()
        self._get_response()

    def _create_stuff(self):
        self._create_tempdir()
        self._override_settings()
        self._create_user()
        self._create_agrifield()
        self._create_dummy_result_file()

    def _create_tempdir(self):
        self.tempdir = tempfile.mkdtemp()

    def _override_settings(self):
        self.settings_overrider = override_settings(
            AIRA_TIMESERIES_CACHE_DIR=self.tempdir
        )
        self.settings_overrider.__enter__()

    def _create_dummy_result_file(self):
        self.dummy_result_pathname = os.path.join(
            settings.AIRA_TIMESERIES_CACHE_DIR,
            "agrifield{}-temperature.hts".format(self.agrifield.id),
        )
        with open(self.dummy_result_pathname, "w") as f:
            f.write("These are the dummy result file contents")

    def _create_user(self):
        self.alice = User.objects.create_user(username="alice", password="topsecret")

    def _create_agrifield(self):
        self.agrifield = mommy.make(
            Agrifield, name="hello", location=Point(23, 38), owner=self.alice
        )

    def _login(self):
        self.client.login(username="alice", password="topsecret")

    def _get_response(self):
        patcher = patch(
            "aira.views.PointTimeseries",
            **{"return_value.get_cached.return_value": self.dummy_result_pathname},
        )
        with patcher as m:
            self.mock_point_timeseries = m
            self.response = self.client.get(
                "/agrifield/{}/timeseries/temperature/".format(self.agrifield.id)
            )

    def tearDown(self):
        self.settings_overrider.__exit__(None, None, None)
        shutil.rmtree(self.tempdir)

    def test_status_code(self):
        self.assertEqual(self.response.status_code, 200)

    def test_response_contents(self):
        content = b""
        for chunk in self.response.streaming_content:
            content += chunk
        self.assertEqual(content, b"These are the dummy result file contents")

    def test_called_point_timeseries(self):
        self.mock_point_timeseries.assert_called_once_with(
            point=self.agrifield.location,
            prefix=os.path.join(settings.AIRA_DATA_HISTORICAL, "daily_temperature"),
        )

    def test_called_get_cached(self):
        self.mock_point_timeseries.return_value.get_cached.assert_called_once_with(
            self.dummy_result_pathname, version=2
        )


class DownloadSoilAnalysisViewTestCase(TestCase, RandomMediaRootMixin):
    def setUp(self):
        self.override_media_root()
        self.alice = User.objects.create_user(username="alice", password="topsecret")
        self.agrifield = mommy.make(Agrifield, id=1, owner=self.alice)
        self.agrifield.soil_analysis.save("somefile", ContentFile("hello world"))
        self.client.login(username="alice", password="topsecret")
        self.response = self.client.get("/agrifield/1/soil_analysis/")

    def tearDown(self):
        self.end_media_root_override()

    def test_status_code(self):
        self.assertEqual(self.response.status_code, 200)

    def test_content(self):
        content = b""
        for x in self.response.streaming_content:
            content += x
        self.assertEqual(content, b"hello world")


class RecommendationViewTestCase(TestDataMixin, TestCase):
    def _make_request(self):
        self.client.login(username="alice", password="topsecret")
        self.response = self.client.get("/recommendation/{}/".format(self.agrifield.id))

    def _update_agrifield(self, **kwargs):
        for key in kwargs:
            if not hasattr(self.agrifield, key):
                raise KeyError("Agrifield doesn't have key {}".format(key))
            setattr(self.agrifield, key, kwargs[key])
        self.agrifield.save()

    def test_response_contains_custom_parameters_notice(self):
        self._update_agrifield(use_custom_parameters=True)
        self._make_request()
        self.assertContains(self.response, "using custom parameters")

    def test_response_not_contains_custom_parameters_notice(self):
        self._update_agrifield(use_custom_parameters=False)
        self._make_request()
        self.assertNotContains(self.response, "using custom parameters")

    def test_response_contains_default_root_depth(self):
        self._update_agrifield(use_custom_parameters=False)
        self._make_request()
        self.assertContains(self.response, "<b>Estimated root depth (max):</b> 0.4 m")

    def test_response_contains_custom_root_depth(self):
        self._update_agrifield(
            use_custom_parameters=True,
            custom_root_depth_min=0.1,
            custom_root_depth_max=0.3,
        )
        self._make_request()
        self.assertContains(self.response, "<b>Estimated root depth (max):</b> 0.2 m")

    def test_response_contains_default_field_capacity(self):
        self._update_agrifield(use_custom_parameters=False)
        self._make_request()
        self.assertContains(self.response, "<b>Field Capacity:</b> 32.0%")

    def test_response_contains_custom_field_capacity(self):
        self._update_agrifield(use_custom_parameters=True, custom_field_capacity=0.321)
        self._make_request()
        self.assertContains(self.response, "<b>Field Capacity:</b> 32.1%")

    def test_response_contains_default_theta_s(self):
        self._update_agrifield(use_custom_parameters=False)
        self._make_request()
        self.assertContains(
            self.response, "<b>Soil moisture at saturation (Θ<sub>s</sub>):</b> 42.0%"
        )

    def test_response_contains_custom_theta_s(self):
        self._update_agrifield(use_custom_parameters=True, custom_thetaS=0.424)
        self._make_request()
        self.assertContains(
            self.response, "<b>Soil moisture at saturation (Θ<sub>s</sub>):</b> 42.4%"
        )

    def test_response_contains_default_pwp(self):
        self._update_agrifield(use_custom_parameters=False)
        self._make_request()
        self.assertContains(self.response, "<b>Permanent Wilting Point:</b> 10.0%")

    def test_response_contains_custom_pwp(self):
        self._update_agrifield(use_custom_parameters=True, custom_wilting_point=0.117)
        self._make_request()
        self.assertContains(self.response, "<b>Permanent Wilting Point:</b> 11.7%")

    def test_response_contains_default_irrigation_efficiency(self):
        self._update_agrifield(use_custom_parameters=False)
        self._make_request()
        self.assertContains(self.response, "<b>Irrigation efficiency factor:</b> 0.85")

    def test_response_contains_custom_irrigation_efficiency(self):
        self._update_agrifield(use_custom_parameters=True, custom_efficiency=0.88)
        self._make_request()
        self.assertContains(self.response, "<b>Irrigation efficiency factor:</b> 0.88")

    def test_response_contains_default_irrigation_optimizer(self):
        self._update_agrifield(use_custom_parameters=False)
        self._make_request()
        self.assertContains(self.response, "<b>Irrigation Optimizer:</b> 0.5")

    def test_response_contains_custom_irrigation_optimizer(self):
        self._update_agrifield(
            use_custom_parameters=True, custom_irrigation_optimizer=0.55
        )
        self._make_request()
        self.assertContains(self.response, "<b>Irrigation Optimizer:</b> 0.55")

    def test_response_contains_no_last_irrigation(self):
        self._make_request()
        self.assertContains(self.response, "<b>Last recorded irrigation:</b> None")

    def test_response_contains_last_irrigation_with_specified_applied_water(self):
        mommy.make(
            IrrigationLog,
            agrifield=self.agrifield,
            time=dt.datetime(2019, 9, 11, 17, 23),
            applied_water=100.5,
        )
        self._make_request()
        self.assertContains(
            self.response, "<b>Last recorded irrigation:</b> 11/09/2019 17:00"
        )
        self.assertContains(self.response, "<b>Applied water (m³):</b> 100.5")

    def test_response_contains_last_irrigation_with_unspecified_applied_water(self):
        mommy.make(
            IrrigationLog,
            agrifield=self.agrifield,
            time=dt.datetime(2019, 9, 11, 17, 23),
            applied_water=None,
        )
        self._update_agrifield(area=653.7)
        self._make_request()
        self.assertContains(
            self.response, "<b>Last recorded irrigation:</b> 11/09/2019 17:00 <br>"
        )
        self.assertContains(
            self.response,
            "<b>Applied water (m³):</b> 23.0 "
            "(Irrigation water is estimated using system&#39;s "
            "default parameters.)<br>",
        )


class RemoveSupervisedUserTestCase(TestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.bob = User.objects.create_user(username="bob", password="topsecret")
        self.bob.profile.first_name = "Bob"
        self.bob.profile.last_name = "Brown"
        self.bob.profile.supervisor = self.alice
        self.bob.profile.save()
        self.charlie = User.objects.create_user(
            username="charlie", password="topsecret"
        )

    def test_supervised_users_list_contains_bob(self):
        self.client.login(username="alice", password="topsecret")
        response = self.client.get("/home/")
        self.assertContains(
            response,
            '<a href="/home/bob/">bob (Bob Brown)</a>'.format(self.bob.id),
            html=True,
        )

    def test_remove_bob_from_supervised(self):
        assert User.objects.get(username="bob").profile.supervisor is not None
        self.client.login(username="alice", password="topsecret")
        response = self.client.post(
            "/supervised_user/remove/", data={"supervised_user_id": self.bob.id}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(User.objects.get(username="bob").profile.supervisor)

    def test_attempting_to_remove_bob_when_not_logged_in_returns_404(self):
        response = self.client.post(
            "/supervised_user/remove/", data={"supervised_user_id": self.bob.id}
        )
        self.assertEqual(response.status_code, 404)
        self.assertIsNotNone(User.objects.get(username="bob").profile.supervisor)

    def test_attempting_to_remove_bob_when_logged_in_as_charlie_returns_404(self):
        self.client.login(username="charlie", password="topsecret")
        response = self.client.post(
            "/supervised_user/remove/", data={"supervised_user_id": self.bob.id}
        )
        self.assertEqual(response.status_code, 404)
        self.assertIsNotNone(User.objects.get(username="bob").profile.supervisor)

    def test_attempting_to_remove_when_already_removed_returns_404(self):
        self.client.login(username="alice", password="topsecret")
        response = self.client.post(
            "/supervised_user/remove/", data={"supervised_user_id": self.charlie.id}
        )
        self.assertEqual(response.status_code, 404)

    def test_attempting_to_remove_garbage_id_returns_404(self):
        self.client.login(username="alice", password="topsecret")
        response = self.client.post(
            "/supervised_user/remove/", data={"supervised_user_id": "garbage"}
        )
        self.assertEqual(response.status_code, 404)

    def test_posting_without_parameters_returns_404(self):
        self.client.login(username="alice", password="topsecret")
        response = self.client.post("/supervised_user/remove/")
        self.assertEqual(response.status_code, 404)
