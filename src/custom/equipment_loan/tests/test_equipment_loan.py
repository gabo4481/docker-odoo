from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestEquipmentLoan(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.equipment = cls.env["maintenance.equipment"].create({
            "name": "Equipment Loan Test",
        })

    def _create_loan(self, **values):
        today = fields.Date.context_today(self.env.user)
        loan_values = {
            "equipment_id": self.equipment.id,
            "expected_return_date": today + timedelta(days=1),
        }
        loan_values.update(values)
        return self.env["equipment.loan"].create(loan_values)

    def test_deliver_and_return_flow(self):
        loan = self._create_loan()

        self.assertEqual(loan.state, "draft")
        self.assertEqual(loan.recipient_id, self.env.user)
        self.assertEqual(loan.delivery_date, fields.Date.context_today(loan))

        loan.action_deliver()
        self.assertEqual(loan.state, "loaned")

        loan.action_return()
        self.assertEqual(loan.state, "returned")
        self.assertEqual(loan.actual_return_date, fields.Date.context_today(loan))

    def test_equipment_cannot_have_two_active_loans(self):
        self._create_loan(state="loaned")

        with self.assertRaisesRegex(ValidationError, "otro préstamo activo"):
            self._create_loan(state="loaned")

    def test_overdue_only_for_past_due_active_loans(self):
        yesterday = fields.Date.context_today(self.env.user) - timedelta(days=1)
        day_before_yesterday = yesterday - timedelta(days=1)
        overdue_loan = self._create_loan(
            state="loaned",
            delivery_date=day_before_yesterday,
            expected_return_date=yesterday,
        )
        draft_loan = self._create_loan(
            delivery_date=day_before_yesterday,
            expected_return_date=yesterday,
        )

        self.assertTrue(overdue_loan.is_overdue)
        self.assertFalse(draft_loan.is_overdue)

    def test_cron_schedules_one_activity_for_overdue_loan(self):
        today = fields.Date.context_today(self.env.user)
        loan = self._create_loan(
            state="loaned",
            delivery_date=today - timedelta(days=2),
            expected_return_date=today - timedelta(days=1),
        )

        self.env["equipment.loan"]._cron_schedule_overdue_activities()
        self.env["equipment.loan"]._cron_schedule_overdue_activities()

        self.assertTrue(loan.overdue_activity_created)
        self.assertEqual(len(loan.activity_ids), 1)
        self.assertEqual(loan.activity_ids.user_id, loan.recipient_id)
        self.assertEqual(loan.activity_ids.summary, "Préstamo vencido")

    def test_expected_return_cannot_precede_delivery(self):
        today = fields.Date.context_today(self.env.user)

        with self.assertRaisesRegex(ValidationError, "no puede ser anterior"):
            self._create_loan(
                delivery_date=today,
                expected_return_date=today - timedelta(days=1),
            )

    def test_equipment_smart_button_shows_loan_count_and_action_domain(self):
        self._create_loan()
        self._create_loan()

        self.assertEqual(self.equipment.equipment_loan_count, 2)
        action = self.equipment.action_view_equipment_loans()
        self.assertEqual(action["res_model"], "equipment.loan")
        self.assertEqual(action["domain"], [("equipment_id", "=", self.equipment.id)])
