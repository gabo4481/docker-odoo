from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged
from psycopg2 import IntegrityError


@tagged("post_install", "-at_install")
class TestEquipmentLoan(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.equipment = cls.env["maintenance.equipment"].create({
            "name": "Equipment Loan Test",
        })
        cls.manager = new_test_user(
            cls.env,
            login="equipment_loan_manager",
            groups="equipment_loan.group_equipment_loan_manager",
            name="Equipment Loan Manager",
        )
        cls.employee = new_test_user(
            cls.env,
            login="equipment_loan_employee",
            groups="base.group_user",
            name="Equipment Loan Employee",
        )

    def _create_loan(self, **values):
        today = fields.Date.context_today(self.env.user)
        loan_values = {
            "equipment_id": self.equipment.id,
            "expected_return_date": today + timedelta(days=1),
        }
        loan_values.update(values)
        loan_model = self.env["equipment.loan"]
        if loan_values.get("state", "draft") != "draft":
            loan_model = loan_model.with_user(self.manager)
        return loan_model.create(loan_values)

    def test_deliver_and_return_flow(self):
        loan = self._create_loan()

        self.assertEqual(loan.state, "draft")
        self.assertEqual(loan.recipient_id, self.env.user)
        self.assertEqual(loan.delivery_date, fields.Date.context_today(loan))

        loan.with_user(self.manager).action_deliver()
        self.assertEqual(loan.state, "loaned")

        loan.with_user(self.manager).action_return()
        self.assertEqual(loan.state, "returned")
        self.assertEqual(loan.actual_return_date, fields.Date.context_today(loan))

    def test_equipment_cannot_have_two_active_loans(self):
        first_loan = self._create_loan()
        second_loan = self._create_loan()
        first_loan.with_user(self.manager).action_deliver()

        with self.assertRaisesRegex(ValidationError, "otro préstamo activo"):
            second_loan.with_user(self.manager).action_deliver()
        self.assertEqual(second_loan.state, "draft")

    def test_database_index_rejects_second_active_loan(self):
        self._create_loan(state="loaned")
        today = fields.Date.context_today(self.env.user)

        with self.assertRaises(IntegrityError):
            with self.cr.savepoint():
                self.cr.execute(
                    """
                    INSERT INTO equipment_loan (
                        id, equipment_id, recipient_id, delivery_date,
                        expected_return_date, state, create_uid, create_date,
                        write_uid, write_date
                    )
                    VALUES (
                        nextval(pg_get_serial_sequence('equipment_loan', 'id')),
                        %s, %s, %s, %s, 'loaned', %s, NOW(), %s, NOW()
                    )
                    """,
                    (
                        self.equipment.id,
                        self.env.user.id,
                        today,
                        today + timedelta(days=1),
                        self.env.user.id,
                        self.env.user.id,
                    ),
                )

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

        self.assertEqual(len(loan.activity_ids), 1)
        self.assertEqual(loan.activity_ids.user_id, self.manager)
        self.assertEqual(loan.activity_ids.summary, "Préstamo vencido")

    def test_cron_does_not_duplicate_existing_overdue_activity(self):
        today = fields.Date.context_today(self.env.user)
        loan = self._create_loan(
            state="loaned",
            delivery_date=today - timedelta(days=2),
            expected_return_date=today - timedelta(days=1),
        )
        loan.activity_schedule(
            "mail.mail_activity_data_todo",
            user_id=self.manager.id,
            summary="Préstamo vencido",
        )

        self.env["equipment.loan"]._cron_schedule_overdue_activities()

        self.assertEqual(len(loan.activity_ids), 1)

    def test_employee_only_sees_own_loans_and_cannot_change_state(self):
        own_loan = self._create_loan(recipient_id=self.employee.id)
        other_loan = self._create_loan(recipient_id=self.manager.id)
        employee_loans = self.env["equipment.loan"].with_user(self.employee).search([])

        self.assertIn(own_loan, employee_loans)
        self.assertNotIn(other_loan, employee_loans)
        with self.assertRaises(AccessError):
            own_loan.with_user(self.employee).action_deliver()
        with self.assertRaises(AccessError):
            own_loan.with_user(self.employee).write({"state": "loaned"})

        own_loan.with_user(self.manager).action_deliver()
        with self.assertRaises(AccessError):
            own_loan.with_user(self.employee).action_return()

    def test_equipment_loan_count_queries_do_not_grow_with_equipment_count(self):
        equipment_model = self.env["maintenance.equipment"]
        equipment_count = 25
        equipments = equipment_model.create([
            {"name": "Equipment Loan Performance %s" % index}
            for index in range(equipment_count)
        ])
        today = fields.Date.context_today(self.env.user)
        self.env["equipment.loan"].create([
            {
                "equipment_id": equipment.id,
                "recipient_id": self.manager.id,
                "expected_return_date": today + timedelta(days=1),
            }
            for equipment in equipments
        ])

        def measure_count_queries(equipment_ids):
            self.env.invalidate_all()
            query_start = self.cr.sql_log_count
            counts = equipment_model.browse(equipment_ids).mapped("equipment_loan_count")
            return counts, self.cr.sql_log_count - query_start

        one_equipment_counts, one_equipment_queries = measure_count_queries(equipments[:1].ids)
        many_equipment_counts, many_equipment_queries = measure_count_queries(equipments.ids)

        self.assertEqual(one_equipment_counts, [1])
        self.assertEqual(many_equipment_counts, [1] * equipment_count)
        self.assertGreater(one_equipment_queries, 0)
        self.assertEqual(one_equipment_queries, many_equipment_queries)

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
