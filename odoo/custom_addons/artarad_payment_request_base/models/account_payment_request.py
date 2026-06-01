# -*- coding: utf-8 -*-
from odoo import models, fields, api, exceptions, _


class ArtaradAccountPaymentRequestRejectReason(models.TransientModel):
    _name = "artarad.account.payment.request.reject.reason"
    _description = "Account Payment Request Reject Reason"
    
    
    reject_reason = fields.Text(required=True)
    
    
    def action_register_reject_reason(self):
        request_id = self.env["artarad.account.payment.request"].browse(self.env.context["request_id"])
        request_id.write({"state": "rejected", "reject_reason": self.reject_reason})
    

class ArtaradAccountPaymentRequest(models.Model):
    _name = "artarad.account.payment.request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Account Payment Request"
    _order = "id desc"

    
    name = fields.Char(string="Number", required=True, copy=False, readonly=True, index=True, default=lambda self: _("New"))
    state = fields.Selection([("draft", "Draft"), ("submitted", "Submitted"), ("approved", "Approved"), ("scheduled", "Scheduled"), ("done", "Done"), ("rejected", "Rejected")], default="draft", copy=False, tracking=True)
    request_for = fields.Selection([("miscellaneous", "Miscellaneous")], string="For", default="miscellaneous", required=True, tracking=True)
    method = fields.Selection([("cash", "Cash"), ("cheque", "Cheque")], default="cash", required=True, tracking=True)
    employee_id = fields.Many2one("hr.employee", required=True, default=lambda self: self.env.user.employee_id.id)

    recipient_id = fields.Many2one("res.partner", default=lambda self: self.env.user.partner_id.id, required=True, tracking=True)
    recipient_bank_account_id = fields.Many2one("res.partner.bank", required=True, tracking=True)
    amount = fields.Monetary(currency_field="currency_id", required=True, tracking=True)
    due_date = fields.Date(required=True, tracking=True)
    scheduled_amount = fields.Monetary(currency_field="currency_id", tracking=True)
    scheduled_due_date = fields.Date(tracking=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one("res.currency", default= lambda self: self.env.company.currency_id.id, required=True)

    unpaid_scheduled_amount = fields.Monetary(currency_field="currency_id", compute="_compute_unpaid_scheduled_amount", store=True)
    related_documents_name = fields.Char(string="Related Documents", compute="_compute_related_documents_name")

    description = fields.Text(required=True, tracking=True)

    journal_id = fields.Many2one("account.journal", domain=[("type", "in", ["bank", "cash", "pdc"])], tracking=True)
    responsible_id = fields.Many2one("res.users", tracking=True)
    payment_ids = fields.One2many("account.payment", "request_id", string="Payments", tracking=True)

    reject_reason = fields.Text()


    @api.depends("scheduled_amount", "payment_ids")
    def _compute_unpaid_scheduled_amount(self):
        for rec in self:
            rec.unpaid_scheduled_amount = rec.scheduled_amount - sum(rec.payment_ids.mapped("amount"))
    
    def _compute_related_documents_name(self):
        for rec in self:
            value = False
            for field_name in rec._fields:
                if field_name[:8] == "related_" and field_name[-3:] == "ids" and rec[field_name]:
                   value = ', '.join(rec[field_name].sudo().mapped("display_name"))
                   break
            rec.sudo().related_documents_name = value

    @api.onchange("request_for")
    def onchange_request_for(self):
        if self.ids: # if the record is editing (not creating for first time)
            for field_name in self._fields:
                if field_name[:8] == "related_" and field_name[-3:] == "ids":
                    self[field_name] = [(5, 0)]
            
    @api.onchange("amount", "due_date")
    def onchange_amount_and_due_date(self):
        self.scheduled_amount = self.amount
        self.scheduled_due_date = self.due_date

    @api.model
    def create(self, vals_list):
        rec = super(ArtaradAccountPaymentRequest, self).create(vals_list)
        rec.name = self.env['ir.sequence'].sudo().next_by_code('artarad.payment.request')
        return rec

    def write(self, vals):
        for rec in self:
            if rec.state == "paid":
                raise exceptions.ValidationError(_("Paid requests can not be modified!"))
            if rec.state == "scheduled" and vals.get("state") == "rejected" and rec.payment_ids:
                raise exceptions.ValidationError(_("Scheduled requests that have payments can not be rejected!"))
        res = super(ArtaradAccountPaymentRequest, self).write(vals)
        return res

    def unlink(self):
        for rec in self:
            if rec.state != "draft":
                raise exceptions.ValidationError(_("Only draft requests can be deleted!"))
        return super().unlink()

    @api.constrains("payment_ids", "scheduled_amount")
    def check_amounts(self):
        for rec in self:
            if rec.payment_ids and sum(rec.payment_ids.mapped("amount")) != rec.scheduled_amount:
                raise exceptions.ValidationError(_("Sum of payment amounts must be equal to request scheduled amount!"))

    def action_submit(self):
        self.state = "submitted"

    def action_approve(self):
        for rec in self:
            rec.state = "approved"

    def action_schedule(self):
        for rec in self:
            rec.state = "scheduled"
            rec.activity_schedule("artarad_payment_request_base.mail_activity_payment_request",
                                    user_id=rec.responsible_id.id,
                                    date_deadline=rec.scheduled_due_date,
                                    note=_(f"The <a href=# data-oe-model=artarad.account.payment.request data-oe-id={rec.id}>{rec.name}</a> requires your action."))

    def action_done(self):
        self.state = "done"
        self.activity_feedback(["artarad_payment_request_base.mail_activity_payment_request"])

    def action_reject(self):
        return {
            "name": "Payment Request Reject Reason",
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "artarad.account.payment.request.reject.reason",
            "target": "new",
            "context": {"request_id": self.id}
        }

    def action_draft(self):
        self.reject_reason = False
        self.state = "draft"


    def upgrade_field_changes(self):
        for rec in self:
            for field_name in rec._fields:
                if field_name[:8] == "related_" and field_name[-2:] == "id" and rec[field_name]:
                    rec[field_name + "s"] = [(4, rec[field_name].id)]
                    rec[field_name] = False