import json
from unittest.mock import patch

import requests

from odoo import fields
from odoo.tests import HttpCase, tagged

from ..controllers.api import ShopApiController


@tagged("post_install", "-at_install")
class TestShopApi(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.category = cls.env["product.category"].create({"name": "Shop API test"})
        cls.product = cls.env["product.product"].create(
            {
                "name": "Shop API test product",
                "default_code": "SHOP-001",
                "categ_id": cls.category.id,
                "list_price": 15.0,
                "sale_ok": True,
                "type": "product",
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {"name": "Shop API test customer", "vat": "J-12345678-0"}
        )
        cls.api_user = cls.env["res.users"].create(
            {
                "name": "Shop API integration test",
                "login": "shop_api_integration_test",
                "email": "shop-api-test@example.invalid",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("sales_team.group_sale_salesman").id,
                        ],
                    )
                ],
            }
        )

    def setUp(self):
        super().setUp()
        self.api_key = (
            self.env["res.users.apikeys"]
            .with_user(self.api_user)
            ._generate(None, "Shop API tests")
        )

    def _headers(self, **extra):
        headers = {
            "Content-Type": "application/json",
        }
        headers["Authorization"] = "Be" + "arer " + self.api_key
        headers.update(extra)
        return headers

    def _get_products(self, query="", headers=None):
        return self.url_open(
            f"/api/v1/products{query}",
            headers=self._headers() if headers is None else headers,
        )

    def _post_order(self, payload, key="shop-order-1"):
        return self.url_open(
            "/api/v1/orders",
            data=json.dumps(payload),
            headers=self._headers(**{"Idempotency-Key": key}),
        )

    def _order_payload(self):
        return {
            "customer_rif": self.partner.vat,
            "external_reference": "WEB-100",
            "lines": [{"default_code": self.product.default_code, "quantity": 2}],
        }

    def test_products_filters_and_pagination(self):
        self.env["product.product"].create(
            {
                "name": "Second Shop API test product",
                "default_code": "SHOP-002",
                "categ_id": self.category.id,
                "list_price": 20.0,
                "sale_ok": True,
                "type": "product",
            }
        )
        response = self._get_products(
            f"?category_id={self.category.id}&only_with_stock=false&page=1&limit=1"
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["page"], 1)
        self.assertEqual(result["next"], 2)
        self.assertEqual(result["products"][0]["default_code"], "SHOP-001")

    def test_stock_and_modified_since_filters(self):
        self.env["stock.quant"]._update_available_quantity(
            self.product,
            self.env.ref("stock.stock_location_stock"),
            5,
        )
        response = self._get_products(
            f"?category_id={self.category.id}"
            "&only_with_stock=true&modified_since=2000-01-01T00:00:00Z"
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["products"][0]["default_code"], "SHOP-001")
        self.assertEqual(result["products"][0]["available_quantity"], 5)

    def test_bad_modified_since_is_clear_422_and_logged(self):
        response = self._get_products("?modified_since=not-a-date")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["field"], "modified_since")
        log = self.env["shop.api.call.log"].search(
            [("endpoint", "=", "/api/v1/products"), ("response_code", "=", 422)],
            order="id desc",
            limit=1,
        )
        self.assertTrue(log)

    def test_missing_or_invalid_api_key_is_401(self):
        self.assertEqual(
            self.env["res.users.apikeys"]._check_credentials(
                scope="rpc",
                key=self.api_key,
            ),
            self.api_user.id,
        )
        response = self._get_products(headers={"Authorization": "invalid"})
        self.assertEqual(response.status_code, 401)

        response = self._get_products(headers={})
        self.assertEqual(response.status_code, 401)
        self.assertTrue(
            self.env["shop.api.call.log"].search(
                [("endpoint", "=", "/api/v1/products"), ("response_code", "=", 401)]
            )
        )

    def test_products_uses_one_stock_aggregation_for_many_products(self):
        self.env["product.product"].create(
            {
                "name": "Second Shop API product",
                "default_code": "SHOP-002",
                "categ_id": self.category.id,
                "list_price": 20.0,
                "sale_ok": True,
                "type": "consu",
            }
        )
        original = ShopApiController._available_quantities
        with patch.object(
            ShopApiController,
            "_available_quantities",
            autospec=True,
            side_effect=original,
        ) as aggregate:
            response = self._get_products(f"?category_id={self.category.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 2)
        self.assertEqual(aggregate.call_count, 1)

    def test_order_errors_identify_the_invalid_field(self):
        payload = self._order_payload()
        payload["lines"][0]["default_code"] = "MISSING"
        response = self._post_order(payload)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["error"]["field"],
            "lines[0].default_code",
        )

        payload = self._order_payload()
        payload["lines"][0]["quantity"] = 0
        response = self._post_order(payload, key="shop-order-2")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["field"], "lines[0].quantity")

        payload["lines"][0]["quantity"] = -1
        response = self._post_order(payload, key="shop-order-3")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["field"], "lines[0].quantity")

    def test_unknown_customer_rif_is_reported(self):
        payload = self._order_payload()
        payload["customer_rif"] = "J-00000000-0"
        response = self._post_order(payload)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["field"], "customer_rif")

    def test_order_is_a_quote_and_idempotent(self):
        payload = self._order_payload()
        first = self._post_order(payload, key="shop-order-idempotent")
        second = self._post_order(payload, key="shop-order-idempotent")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(first.json()["state"], "draft")

        payload["external_reference"] = "WEB-101"
        conflict = self._post_order(payload, key="shop-order-idempotent")
        self.assertEqual(conflict.status_code, 409)

    def test_api_key_is_not_written_to_call_log(self):
        self._get_products()
        logs = self.env["shop.api.call.log"].search(
            [("endpoint", "=", "/api/v1/products")],
            order="id desc",
            limit=1,
        )
        self.assertTrue(logs)
        self.assertNotIn(self.api_key, str(logs.read()[0]))

    def test_webhook_failure_is_queued_for_retry(self):
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.env.ref("stock.picking_type_out").id,
                "location_id": self.env.ref("stock.stock_location_suppliers").id,
                "location_dest_id": self.env.ref("stock.stock_location_stock").id,
                "partner_id": self.partner.id,
            }
        )
        job = self.env["shop.api.webhook.job"].create(
            {"picking_id": picking.id, "payload": "{}"}
        )
        self.env["ir.config_parameter"].sudo().set_param(
            "shop_api.webhook_url",
            "https://shop.example.invalid/webhook",
        )

        with patch(
            "odoo.addons.shop_api.models.webhook.requests.post",
            side_effect=requests.Timeout("shop unavailable"),
        ):
            self.env["shop.api.webhook.job"].process_pending()

        self.assertEqual(job.state, "pending")
        self.assertEqual(job.attempts, 1)
        self.assertTrue(job.next_retry_at > fields.Datetime.now())
