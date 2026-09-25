from odoo import fields, models


class ApprovalRequest(models.Model):
    _inherit = "approval.request"

    zvy_purchase_request_id = fields.Many2one(
        comodel_name="zvy.purchase.request",
        string="Purchase Request",
        ondelete="set null",
        index=True,
        copy=False,
    )
