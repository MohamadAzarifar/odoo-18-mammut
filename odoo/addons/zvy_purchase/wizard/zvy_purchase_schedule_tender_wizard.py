from odoo import _, fields, models
from odoo.exceptions import UserError


class ZvyPurchaseScheduleTenderWizard(models.TransientModel):
    _name = "zvy.purchase.schedule.tender.wizard"
    _description = "Schedule"

    tender_id = fields.Many2one(
        comodel_name="zvy.purchase.tender",
        string="Tender",
        required=True,
        readonly=True,
    )
    end_date = fields.Datetime(
        string="End Date",
        required=True,
    )

    def action_schedule(self):
        self.ensure_one()
        tender = self.tender_id
        tender._zvy_check_assigned_commission_expert()
        if tender.state != "assigned":
            raise UserError(
                _("A tender can only be scheduled when it is Assigned.")
            )
        if not self.end_date:
            raise UserError(_("End Date is required."))
        if self.end_date <= fields.Datetime.now():
            raise UserError(_("End Date must be in the future."))
        tender.write(
            {
                "end_date": self.end_date,
                "state": "scheduled",
            }
        )
        return {"type": "ir.actions.act_window_close"}
