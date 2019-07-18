# Copyright 2019 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
from datetime import date, timedelta

from odoo.tests import SavepointCase
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DATE_FORMAT


class TestPartnerAutoReconcile(SavepointCase):

    @classmethod
    def setUpClass(cls):
        super(TestPartnerAutoReconcile, cls).setUpClass()
        cls.acc_rec = cls.env['account.account'].search(
            [('user_type_id', '=', cls.env.ref(
                'account.data_account_type_receivable').id
              )], limit=1
        )
        cls.acc_pay = cls.env['account.account'].search(
            [('user_type_id', '=', cls.env.ref(
                'account.data_account_type_payable').id
              )], limit=1
        )
        cls.acc_rev = cls.env['account.account'].search(
            [('user_type_id', '=', cls.env.ref(
                'account.data_account_type_revenue').id
              )], limit=1
        )
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test partner',
            'customer': True,
            'property_account_receivable_id': cls.acc_rec.id,
            'property_account_payable_id': cls.acc_pay.id,
        })
        cls.payment_mode = cls.env.ref(
            'account_payment_mode.payment_mode_inbound_dd1'
        )
        # TODO check why it's not set from demo data
        cls.payment_mode.auto_reconcile_outstanding_credits = True
        cls.product = cls.env.ref('product.consu_delivery_02')
        cls.invoice = cls.env['account.invoice'].create({
            'partner_id': cls.partner.id,
            'type': 'out_invoice',
            'payment_term_id': cls.env.ref('account.account_payment_term').id,
            'account_id': cls.acc_rec.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': cls.product.id,
                'name': cls.product.name,
                'price_unit': 1000.0,
                'quantity': 1,
                'account_id': cls.acc_rev.id,
            })],
        })
        cls.invoice.action_invoice_open()
        bank_journal = cls.env['account.journal'].search(
            [('type', '=', 'bank')], limit=1
        )
        cls.invoice.pay_and_reconcile(bank_journal)
        cls.refund_wiz = cls.env['account.invoice.refund'].with_context(
            active_ids=cls.invoice.ids).create({
                'filter_refund': 'refund',
                'description': 'test'
            })
        refund_id = cls.refund_wiz.invoice_refund().get('domain')[1][2]
        cls.refund = cls.env['account.invoice'].browse(refund_id)
        cls.refund.action_invoice_open()
        cls.invoice_copy = cls.invoice.copy()
        cls.invoice_copy.write({
            'invoice_line_ids': [(0, 0, {
                'product_id': cls.product.id,
                'name': cls.product.name,
                'price_unit': 500.0,
                'quantity': 1,
                'account_id': cls.acc_rev.id,
            })]
        })
        cls.invoice_copy.action_invoice_open()

    def test_invoice_validate_auto_reconcile(self):
        auto_rec_invoice = self.invoice.copy({
            'payment_mode_id': self.payment_mode.id,
        })
        auto_rec_invoice.write({
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'name': self.product.name,
                'price_unit': 500.0,
                'quantity': 1,
                'account_id': self.acc_rev.id,
            })]
        })
        self.assertTrue(self.payment_mode.auto_reconcile_outstanding_credits)
        self.assertEqual(self.invoice_copy.residual, 1500)
        auto_rec_invoice.action_invoice_open()
        self.assertEqual(auto_rec_invoice.residual, 500)

    def test_invoice_onchange_auto_reconcile(self):
        self.assertEqual(self.invoice_copy.residual, 1500)
        self.invoice_copy.payment_mode_id = self.payment_mode
        self.invoice_copy.payment_mode_id_change()
        self.assertEqual(self.invoice_copy.residual, 500)
        self.invoice_copy.payment_mode_id = False
        self.invoice_copy.payment_mode_id_change()
        self.assertEqual(self.invoice_copy.residual, 1500)
        # Copy the refund so there's more outstanding credit than invoice total
        new_refund = self.refund.copy()
        new_refund.date = (date.today() + timedelta(days=1)).strftime(
            DATE_FORMAT
        )
        new_refund.invoice_line_ids.write({'price_unit': 1200})
        new_refund.action_invoice_open()
        # Set reconcile partial to False
        self.payment_mode.auto_reconcile_allow_partial = False
        self.assertFalse(self.payment_mode.auto_reconcile_allow_partial)
        self.invoice_copy.payment_mode_id = self.payment_mode
        self.invoice_copy.payment_mode_id_change()
        # Only the older move is used as payment
        self.assertEqual(self.invoice_copy.residual, 500)
        self.invoice_copy.payment_mode_id = False
        self.invoice_copy.payment_mode_id_change()
        self.assertEqual(self.invoice_copy.residual, 1500)
        # Set allow partial will reconcile both moves
        self.payment_mode.auto_reconcile_allow_partial = True
        self.invoice_copy.payment_mode_id = self.payment_mode
        self.invoice_copy.payment_mode_id_change()
        self.assertEqual(self.invoice_copy.state, 'paid')
        self.assertEqual(self.invoice_copy.residual, 0)

    def test_invoice_auto_unreconcile(self):
        # Copy the refund so there's more outstanding credit than invoice total
        new_refund = self.refund.copy()
        new_refund.date = (date.today() + timedelta(days=1)).strftime(
            DATE_FORMAT
        )
        new_refund.invoice_line_ids.write({'price_unit': 1200})
        new_refund.action_invoice_open()

        auto_rec_invoice = self.invoice.copy({
            'payment_mode_id': self.payment_mode.id,
        })
        auto_rec_invoice.invoice_line_ids.write({'price_unit': 800})
        auto_rec_invoice.action_invoice_open()
        self.assertEqual(auto_rec_invoice.state, 'paid')
        self.assertEqual(auto_rec_invoice.residual, 0)
        # As we had 2200 of outstanding credits and 800 was assigned, there's
        # 1400 left
        self.assertTrue(self.payment_mode.auto_reconcile_allow_partial)
        self.invoice_copy.payment_mode_id = self.payment_mode
        self.invoice_copy.payment_mode_id_change()
        self.assertEqual(self.invoice_copy.residual, 100)
        # Unreconcile of an invoice doesn't change the reconciliation of the
        # other invoice
        self.invoice_copy.payment_mode_id = False
        self.invoice_copy.payment_mode_id_change()
        self.assertEqual(self.invoice_copy.residual, 1500)
        self.assertEqual(auto_rec_invoice.state, 'paid')
        self.assertEqual(auto_rec_invoice.residual, 0)
