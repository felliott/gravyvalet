import json
import unittest
from http import HTTPStatus

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from addon_service import models as db
from addon_service.internal_resource.views import InternalResourceViewSet
from addon_service.tests import _factories
from addon_service.tests._helpers import get_test_request


class TestInternalResourceAPI(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls._resource = _factories.InternalResourceFactory()

    @property
    def _detail_path(self):
        return reverse("internal-resources-detail", kwargs={"pk": self._resource.pk})

    @property
    def _list_path(self):
        return reverse("internal-resources-list")

    @property
    def _related_configured_storage_addons_path(self):
        return reverse(
            "internal-resources-related",
            kwargs={
                "pk": self._resource.pk,
                "related_field": "configured_storage_addons",
            },
        )

    def test_get(self):
        _resp = self.client.get(self._detail_path)
        self.assertEqual(_resp.status_code, HTTPStatus.OK)
        self.assertEqual(_resp.data["resource_uri"], self._resource.resource_uri)

    def test_methods_not_allowed(self):
        _methods_not_allowed = {
            self._detail_path: {"patch", "put", "post"},
            # TODO: self._list_path: {'get', 'patch', 'put', 'post'},
            self._related_configured_storage_addons_path: {"patch", "put", "post"},
        }
        for _path, _methods in _methods_not_allowed.items():
            for _method in _methods:
                with self.subTest(path=_path, method=_method):
                    _client_method = getattr(self.client, _method)
                    _resp = _client_method(_path)
                    self.assertEqual(_resp.status_code, HTTPStatus.METHOD_NOT_ALLOWED)


# unit-test data model
class TestInternalResourceModel(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls._resource = _factories.InternalResourceFactory()

    def test_can_load(self):
        _resource_from_db = db.InternalResource.objects.get(id=self._resource.id)
        self.assertEqual(self._resource.resource_uri, _resource_from_db.resource_uri)

    def test_configured_storage_addons__empty(self):
        self.assertEqual(
            list(self._resource.configured_storage_addons.all()),
            [],
        )

    def test_configured_storage_addons__several(self):
        _accounts = set(
            _factories.ConfiguredStorageAddonFactory.create_batch(
                size=3,
                authorized_resource=self._resource,
            )
        )
        self.assertEqual(
            set(self._resource.configured_storage_addons.all()),
            _accounts,
        )

    def test_validation(self):
        self._resource.resource_uri = "not a uri"
        with self.assertRaises(ValidationError):
            self._resource.clean_fields(exclude=["modified"])


# unit-test viewset (call the view with test requests)
class TestInternalResourceViewSet(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls._resource = _factories.InternalResourceFactory()
        cls._view = InternalResourceViewSet.as_view({"get": "retrieve"})

    def test_get(self):
        _resp = self._view(
            get_test_request(),
            pk=self._resource.pk,
        )
        self.assertEqual(_resp.status_code, HTTPStatus.OK)
        _content = json.loads(_resp.rendered_content)
        self.assertEqual(
            set(_content["data"]["attributes"].keys()),
            {
                "resource_uri",
            },
        )
        self.assertEqual(
            set(_content["data"]["relationships"].keys()),
            {
                "configured_storage_addons",
            },
        )

    @unittest.expectedFailure  # TODO
    def test_unauthorized(self):
        _anon_resp = self._view(get_test_request(), pk=self._user.pk)
        self.assertEqual(_anon_resp.status_code, HTTPStatus.UNAUTHORIZED)

    @unittest.expectedFailure  # TODO
    def test_wrong_user(self):
        _another_user = _factories.InternalUserFactory()
        _resp = self._view(
            get_test_request(user=_another_user),
            pk=self._user.pk,
        )
        self.assertEqual(_resp.status_code, HTTPStatus.FORBIDDEN)


class TestInternalResourceRelatedView(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls._resource = _factories.InternalResourceFactory()
        cls._related_view = InternalResourceViewSet.as_view(
            {"get": "retrieve_related"},
        )

    def test_get_related__empty(self):
        _resp = self._related_view(
            get_test_request(),
            pk=self._resource.pk,
            related_field="configured_storage_addons",
        )
        self.assertEqual(_resp.status_code, HTTPStatus.OK)
        self.assertEqual(_resp.data, [])

    def test_get_related__several(self):
        _addons = _factories.ConfiguredStorageAddonFactory.create_batch(
            size=5,
            authorized_resource=self._resource,
        )
        _resp = self._related_view(
            get_test_request(),
            pk=self._resource.pk,
            related_field="configured_storage_addons",
        )
        self.assertEqual(_resp.status_code, HTTPStatus.OK)
        _content = json.loads(_resp.rendered_content)
        self.assertEqual(
            {_datum["id"] for _datum in _content["data"]},
            {str(_addon.pk) for _addon in _addons},
        )
