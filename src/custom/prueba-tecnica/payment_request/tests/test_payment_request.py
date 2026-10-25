from unittest.mock import patch

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPaymentRequest(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.requester_group = cls.env.ref(
            "payment_request.group_payment_request_requester"
        )
        cls.approver_group = cls.env.ref(
            "payment_request.group_payment_request_approver"
        )
        cls.treasury_group = cls.env.ref(
            "payment_request.group_payment_request_treasury"
        )
        cls.partner = cls.env["res.partner"].create(
            {"name": "Payment Request Test Supplier", "supplier_rank": 1}
        )
        cls.requester = cls._create_user(
            "payment_request_test_requester",
            cls.requester_group,
        )
        cls.approver = cls._create_user(
            "payment_request_test_approver",
            cls.approver_group,
        )
        cls.high_amount_approver = cls._create_user(
            "payment_request_test_high_amount_approver",
            cls.approver_group,
        )
        cls.treasury = cls._create_user(
            "payment_request_test_treasury",
            cls.treasury_group,
        )
        cls.env["payment.approval.level"].create(
            {
                "name": "Test approval level",
                "min_amount": 0,
                "currency_id": cls.env.company.currency_id.id,
                "company_id": cls.env.company.id,
                "approver_id": cls.approver.id,
            }
        )
        cls.env["payment.approval.level"].create(
            {
                "name": "High amount test approval level",
                "min_amount": 200,
                "currency_id": cls.env.company.currency_id.id,
                "company_id": cls.env.company.id,
                "approver_id": cls.high_amount_approver.id,
            }
        )

    @classmethod
    def _create_user(cls, login, group, company=None):
        values = {
            "name": login,
            "login": login,
            "email": f"{login}@example.invalid",
            "groups_id": [(6, 0, [cls.env.ref("base.group_user").id, group.id])],
        }
        if company:
            values.update({
                "company_id": company.id,
                "company_ids": [(6, 0, [company.id])],
            })
        return cls.env["res.users"].create(values)

    def _create_request(self, requester=None, amount=100):
        requester = requester or self.requester
        return self.env["payment.request"].with_user(requester).create(
            {
                "partner_id": self.partner.id,
                "amount": amount,
                "currency_id": self.env.company.currency_id.id,
                "date": "2026-01-15",
                "concept": "Prueba de solicitud",
            }
        )

    def test_create_defaults_and_sequence(self):
        request = self._create_request()

        self.assertEqual(request.requester_id, self.requester)
        self.assertEqual(request.state, "draft")
        self.assertTrue(request.name.startswith("SP/"))
        self.assertTrue(request.name.endswith("/0001") or request.name[-4:].isdigit())

    def test_requester_can_submit_and_cannot_edit_afterward(self):
        request = self._create_request()

        request.with_user(self.requester).action_submit()

        self.assertEqual(request.state, "sent")
        with self.assertRaises(UserError):
            request.with_user(self.requester).write({"concept": "Cambio posterior"})

    def test_only_owner_can_submit(self):
        request = self._create_request()

        with self.assertRaises(AccessError):
            request.with_user(self.approver).action_submit()

        self.assertEqual(request.state, "draft")

    def test_cannot_change_request_data_in_the_submission_write(self):
        request = self._create_request()

        with self.assertRaises(UserError):
            request.with_user(self.requester).write(
                {"state": "sent", "amount": 200}
            )

        self.assertEqual(request.state, "draft")
        self.assertEqual(request.amount, 100)

    def test_approval_records_approver_and_time(self):
        request = self._create_request()
        request.with_user(self.requester).action_submit()

        request.with_user(self.approver).action_approve()

        self.assertEqual(request.state, "approved")
        self.assertEqual(request.approved_by_id, self.approver)
        self.assertTrue(request.approved_at)

    def test_submit_assigns_approver_and_activity(self):
        request = self._create_request()

        request.with_user(self.requester).action_submit()

        self.assertEqual(request.approver_id, self.approver)
        self.assertTrue(
            request.activity_ids.filtered(
                lambda activity: activity.user_id == self.approver
            )
        )

    def test_submit_selects_level_by_amount(self):
        request = self._create_request(amount=250)

        request.with_user(self.requester).action_submit()

        self.assertEqual(request.approver_id, self.high_amount_approver)

    def test_only_assigned_approver_can_approve(self):
        other_approver = self._create_user(
            "payment_request_test_other_approver",
            self.approver_group,
        )
        request = self._create_request()
        request.with_user(self.requester).action_submit()

        with self.assertRaises(AccessError):
            request.with_user(other_approver).action_approve()

        self.assertEqual(request.state, "sent")

    def test_requester_cannot_approve_by_direct_write(self):
        request = self._create_request()
        request.with_user(self.requester).action_submit()

        with self.assertRaises(AccessError):
            request.with_user(self.requester).write(
                {
                    "state": "approved",
                    "approved_by_id": self.requester.id,
                    "approved_at": "2026-01-15 12:00:00",
                }
            )

        self.assertEqual(request.state, "sent")

    def test_approver_cannot_approve_own_request(self):
        request = self._create_request(requester=self.approver)
        request.with_user(self.approver).action_submit()

        with self.assertRaises(AccessError):
            request.with_user(self.approver).action_approve()

        self.assertEqual(request.state, "sent")

    def test_cannot_skip_states_or_edit_immutable_fields(self):
        request = self._create_request()

        with self.assertRaises(UserError):
            request.with_user(self.requester).write({"state": "approved"})

        request.with_user(self.requester).action_submit()
        with self.assertRaises(UserError):
            request.with_user(self.requester).write({"partner_id": self.partner.id})

    def test_amount_must_be_positive(self):
        with self.assertRaises(ValidationError):
            self._create_request().write({"amount": 0})

    def test_rejection_requires_reason_and_posts_to_chatter(self):
        request = self._create_request()
        request.with_user(self.requester).action_submit()
        wizard_model = self.env["payment.request.reject.wizard"].with_user(
            self.approver
        )

        empty_reason_wizard = wizard_model.create(
            {"request_id": request.id, "reason": "   "}
        )
        with self.assertRaises(UserError):
            empty_reason_wizard.action_confirm()

        rejection_reason = "Falta la documentación de respaldo"
        wizard = wizard_model.create(
            {"request_id": request.id, "reason": rejection_reason}
        )
        wizard.action_confirm()

        self.assertEqual(request.state, "rejected")
        self.assertEqual(request.rejection_reason, rejection_reason)
        self.assertTrue(
            any(rejection_reason in message.body for message in request.message_ids)
        )

    def test_direct_rejection_requires_reason(self):
        request = self._create_request()
        request.with_user(self.requester).action_submit()

        with self.assertRaises(ValidationError):
            request.with_user(self.approver).write(
                {"state": "rejected", "rejection_reason": " "}
            )

        self.assertEqual(request.state, "sent")

    def test_treasury_payment_is_linked_and_cannot_be_repeated(self):
        request = self._create_request()
        request.with_user(self.requester).action_submit()
        request.with_user(self.approver).action_approve()
        journal = self.env["account.journal"].create(
            {
                "name": "Payment Request Test Bank",
                "type": "bank",
                "code": "PRTB",
                "company_id": self.env.company.id,
            }
        )
        wizard_model = self.env["payment.request.payment.wizard"].with_user(
            self.treasury
        )
        wizard = wizard_model.create(
            {
                "request_id": request.id,
                "journal_id": journal.id,
                "date": "2026-01-16",
            }
        )

        wizard.action_confirm()

        self.assertEqual(request.state, "paid")
        self.assertTrue(request.payment_id)
        self.assertEqual(request.payment_id.partner_id, self.partner)
        self.assertEqual(request.payment_id.state, "posted")
        with self.assertRaises(UserError):
            wizard.action_confirm()

    def test_usd_request_is_paid_in_journal_currency_at_payment_date(self):
        usd = self.env["res.currency"].search([("name", "=", "USD")], limit=1)
        ves = self.env["res.currency"].with_context(active_test=False).search(
            [("name", "=", "VES")],
            limit=1,
        )
        self.assertTrue(usd, "USD currency must be installed for this test.")
        if not ves:
            ves = self.env["res.currency"].create({
                "name": "VES",
                "symbol": "Bs.",
                "rounding": 0.01,
                "decimal_places": 2,
                "position": "after",
            })
        usd.active = True
        ves.active = True
        payment_date = "2099-01-16"
        for currency, initial_rate, payment_rate in (
            (usd, 2.0, 3.0),
            (ves, 10.0, 30.0),
        ):
            self.env["res.currency.rate"].create([
                {
                    "name": "2099-01-01",
                    "rate": initial_rate,
                    "currency_id": currency.id,
                    "company_id": self.env.company.id,
                },
                {
                    "name": payment_date,
                    "rate": payment_rate,
                    "currency_id": currency.id,
                    "company_id": self.env.company.id,
                },
            ])

        self.env["payment.approval.level"].create({
            "name": "USD test approval level",
            "min_amount": 0,
            "currency_id": usd.id,
            "company_id": self.env.company.id,
            "approver_id": self.approver.id,
        })
        request = self._create_request()
        request.currency_id = usd
        request.with_user(self.requester).action_submit()
        request.with_user(self.approver).action_approve()
        journal = self.env["account.journal"].create({
            "name": "Payment Request VES Test Bank",
            "type": "bank",
            "code": "PRTV",
            "company_id": self.env.company.id,
            "currency_id": ves.id,
        })
        wizard = self.env["payment.request.payment.wizard"].with_user(
            self.treasury
        ).create({
            "request_id": request.id,
            "journal_id": journal.id,
            "date": payment_date,
        })
        expected_amount = usd._convert(
            request.amount,
            ves,
            request.company_id,
            payment_date,
        )

        wizard.action_confirm()

        self.assertEqual(request.state, "paid")
        self.assertEqual(request.payment_id.currency_id, ves)
        self.assertEqual(request.payment_id.date.isoformat(), payment_date)
        self.assertEqual(
            ves.compare_amounts(request.payment_id.amount, expected_amount),
            0,
        )
        self.assertNotEqual(request.payment_id.amount, request.amount)

    def test_payment_posting_failure_keeps_request_approved(self):
        request = self._create_request()
        request.with_user(self.requester).action_submit()
        request.with_user(self.approver).action_approve()
        journal = self.env["account.journal"].create({
            "name": "Payment Request Failing Test Bank",
            "type": "bank",
            "code": "PRTF",
            "company_id": self.env.company.id,
        })
        wizard = self.env["payment.request.payment.wizard"].with_user(
            self.treasury
        ).create({
            "request_id": request.id,
            "journal_id": journal.id,
            "date": "2026-01-16",
        })

        with patch.object(
            type(self.env["account.payment"]),
            "action_post",
            side_effect=UserError("Fallo de prueba"),
        ):
            with self.assertRaises(UserError):
                wizard.action_confirm()

        self.assertEqual(request.state, "approved")
        self.assertFalse(request.payment_id)

    def test_company_rules_hide_other_company_requests_and_levels(self):
        company_b = self.env["res.company"].create({
            "name": "Payment Request Company B",
            "currency_id": self.env.company.currency_id.id,
        })
        user_b = self._create_user(
            "payment_request_test_company_b",
            self.treasury_group,
            company=company_b,
        )
        request_a = self.env["payment.request"].create({
            "partner_id": self.partner.id,
            "amount": 100,
            "currency_id": self.env.company.currency_id.id,
            "date": "2026-01-15",
            "concept": "Compañía A",
        })
        level_a = self.env["payment.approval.level"].create({
            "name": "Company A test level",
            "min_amount": 0,
            "currency_id": self.env.company.currency_id.id,
            "company_id": self.env.company.id,
            "approver_id": self.approver.id,
        })

        requests_b = self.env["payment.request"].with_user(user_b)
        levels_b = self.env["payment.approval.level"].with_user(user_b)
        self.assertFalse(requests_b.search([("id", "=", request_a.id)]))
        self.assertFalse(levels_b.search([("id", "=", level_a.id)]))

    def test_report_includes_approval_details(self):
        request = self._create_request()
        request.with_user(self.requester).action_submit()
        request.with_user(self.approver).action_approve()
        report = self.env.ref("payment_request.action_report_payment_request")

        report_service = self.env["ir.actions.report"]
        html, _ = report_service._render_qweb_html(report.report_name, request.ids)
        pdf, _ = report_service.with_context(force_report_rendering=True)._render_qweb_pdf(
            "payment_request.action_report_payment_request",
            request.ids,
        )

        self.assertIn(self.approver.name.encode(), html)
        self.assertIn(str(request.approved_at.year).encode(), html)
        self.assertEqual(report.report_type, "qweb-pdf")
        self.assertIn(b"%PDF", pdf[:10])
