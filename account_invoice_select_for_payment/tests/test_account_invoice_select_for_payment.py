from odoo.tests import TransactionCase


class TestAccountMoveAndPayment(TransactionCase):
    def setUp(cls):
        super().setUp()

        # Create sample records for account.move
        cls.invoice_1 = cls.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": cls.env.ref("base.res_partner_1").id,
                "selected_for_payment": False,
            }
        )

        cls.invoice_2 = cls.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": cls.env.ref("base.res_partner_2").id,
                "selected_for_payment": True,
            }
        )

    def test_action_toggle_select_for_payment(self):
        """Test the action_toggle_select_for_payment method"""
        # Call the toggle method
        self.invoice_1.action_toggle_select_for_payment()
        self.invoice_2.action_toggle_select_for_payment()

        # Check the "selected_for_payment" status of the invoices
        self.assertTrue(
            self.invoice_1.selected_for_payment,
            "Invoice 1 should be selected for payment.",
        )
        self.assertFalse(
            self.invoice_2.selected_for_payment,
            "Invoice 2 should not be selected for payment.",
        )

    def test_action_register_payment(self):
        """Test the action_register_payment method with multiple invoices"""
        # Create sample payments
        payment = self.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "partner_type": "customer",
                "partner_id": self.env.ref("base.res_partner_1").id,
                "amount": 100,
            }
        )

        # Ensure initial selected_for_payment statuses
        self.assertFalse(
            self.invoice_1.selected_for_payment,
            "Invoice 1 should not be selected initially.",
        )
        self.assertTrue(
            self.invoice_2.selected_for_payment,
            "Invoice 2 should be selected initially.",
        )

        # Add context with active_ids including both invoices
        self.env.context = dict(
            self.env.context, active_ids=[self.invoice_1.id, self.invoice_2.id]
        )
        payment.action_register_payment()

        # Validate that selected_for_payment is reset after payment
        self.env.invalidate_all()
        self.assertFalse(
            self.invoice_1.selected_for_payment,
            "Invoice 1 should not be selected after payment.",
        )
        self.assertFalse(
            self.invoice_2.selected_for_payment,
            "Invoice 2 should not be selected after payment.",
        )

    def test_register_payment_with_no_active_ids(self):
        """Test the action_register_payment method when no active_ids are provided"""
        # Create a payment without setting active_ids in context
        payment = self.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "partner_type": "customer",
                "partner_id": self.env.ref("base.res_partner_1").id,
                "amount": 100,
            }
        )

        # Call register payment with no active_ids
        self.env.context = dict(self.env.context)
        payment.action_register_payment()

        # Ensure that no changes occurred to selected_for_payment
        self.env.invalidate_all()
        self.assertFalse(
            self.invoice_1.selected_for_payment, "Invoice 1 should remain unselected."
        )
        self.assertTrue(
            self.invoice_2.selected_for_payment, "Invoice 2 should remain selected."
        )
