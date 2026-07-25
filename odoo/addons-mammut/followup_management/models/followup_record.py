# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class FollowupRecord(models.Model):
    _name = 'followup.record'
    _description = 'Follow Up Record'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(
        string='Reference',
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: _('New'),
    )
    followup_type_id = fields.Many2one(
        'followup.type',
        string='Follow-up Type',
        required=True,
        tracking=True,
    )
    followup_type_code = fields.Char(
        related='followup_type_id.code',
        store=True,
        readonly=True,
    )
    status = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('answered', 'Answered'),
            ('no_answer', 'No Answer'),
            ('wrong_number', 'Wrong Number'),
            ('not_cooperative', 'Not Cooperative'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )

    # Customer Information
    customer_name = fields.Char(string='Customer Full Name', required=True)
    customer_phone = fields.Char(string='Customer Phone', required=True)
    customer_email = fields.Char(string='Customer Email', required=True)

    # Vehicle Information
    vin_chassis = fields.Char(string='VIN / Chassis Number')
    vehicle_type = fields.Char(string='Vehicle Type')

    # Dealer Information
    dealer_code = fields.Char(string='Dealer Code')
    dealer_name = fields.Char(string='Dealer Name')
    dealer_address = fields.Text(string='Dealer Address')

    # Call History
    call_history_ids = fields.One2many(
        'followup.call.history',
        'followup_id',
        string='Call History',
    )

    # Delivery tab
    vehicle_delivery_date = fields.Date(string='Vehicle Delivery Date')
    contract_vehicle_delivery_date = fields.Date(string='Contract Vehicle Delivery Date')
    includes_participation_profit = fields.Boolean(string='Includes Participation Profit')
    includes_late_delivery_compensation = fields.Boolean(string='Includes Late Delivery Compensation')

    # On-site Service tab
    work_order_number = fields.Char(string='Work Order Number')
    kilometer_number = fields.Float(string='Kilometer Number')
    reception_date = fields.Date(string='Reception Date')
    reception_time = fields.Datetime(string='Reception Time')
    release_time = fields.Datetime(string='Release Time')
    warranty_status = fields.Char(string='Warranty Status')
    vehicle_stop_duration_days = fields.Integer(string='Vehicle Stop Duration at Dealer in Days')
    customer_statement = fields.Text(string='Customer Statement')
    used_parts_description = fields.Text(string='Used Parts Description')
    paid_cost_replaced_parts = fields.Float(string='Paid Cost for Replaced Parts')
    services_provided_description = fields.Text(string='Services Provided Description')
    service_labor_cost = fields.Float(string='Service Labor Cost')
    standard_repair_time = fields.Float(string='Standard Repair Time')

    # Remote Service tab
    customer_call_time = fields.Datetime(string='Customer Call Time')
    average_arrival_time = fields.Datetime(string='Average Arrival Time')
    repair_end_time = fields.Datetime(string='Repair End Time')
    arrival_time = fields.Datetime(string='Arrival Time')
    average_repair_time = fields.Datetime(string='Average Repair Time')
    average_return_time = fields.Datetime(string='Average Return Time')
    customer_type = fields.Selection(
        selection=[
            ('individual', 'Individual'),
            ('company', 'Company'),
        ],
        string='Customer Type',
    )

    # Survey
    partner_id = fields.Many2one('res.partner', string='Customer Partner', readonly=True)
    survey_user_input_id = fields.Many2one(
        'survey.user_input',
        string='Survey Response',
        readonly=True,
        copy=False,
    )
    survey_completed = fields.Boolean(
        string='Survey Completed',
        compute='_compute_survey_completed',
        store=True,
    )
    survey_score = fields.Float(
        string='Survey Score (%)',
        related='survey_user_input_id.scoring_percentage',
        readonly=True,
    )
    survey_scoring_success = fields.Boolean(
        string='Survey Passed',
        related='survey_user_input_id.scoring_success',
        readonly=True,
    )
    survey_completed_date = fields.Datetime(
        string='Survey Completed On',
        related='survey_user_input_id.end_datetime',
        store=True,
        readonly=True,
    )
    followup_count = fields.Integer(string='Count', default=1, store=True)
    survey_submitted_date = fields.Datetime(
        string='Survey Submitted Date',
        related='survey_user_input_id.end_datetime',
        store=True,
        readonly=True,
    )

    @api.depends('survey_user_input_id.state')
    def _compute_survey_completed(self):
        for record in self:
            record.survey_completed = (
                record.survey_user_input_id.state == 'done'
                if record.survey_user_input_id
                else False
            )

    @api.model
    def _init_column(self, column_name):
        if column_name == 'status':
            self.env.cr.execute(
                "UPDATE followup_record SET status = 'draft' WHERE status IS NULL"
            )
        if column_name == 'customer_name':
            self.env.cr.execute(
                "UPDATE followup_record SET customer_name = 'Unknown' "
                "WHERE customer_name IS NULL OR customer_name = ''"
            )
        if column_name == 'customer_phone':
            self.env.cr.execute(
                "UPDATE followup_record SET customer_phone = '-' "
                "WHERE customer_phone IS NULL OR customer_phone = ''"
            )
        if column_name == 'customer_email':
            self.env.cr.execute(
                "UPDATE followup_record SET customer_email = 'unknown@example.com' "
                "WHERE customer_email IS NULL OR customer_email = ''"
            )
        return super()._init_column(column_name)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('followup.record') or _('New')
        return super().create(vals_list)

    def _get_or_create_partner(self):
        self.ensure_one()
        if not self.customer_email:
            raise UserError(_('Customer email is required to start the survey.'))
        partner = self.env['res.partner'].search(
            [('email', '=ilike', self.customer_email.strip())],
            limit=1,
        )
        if not partner:
            partner = self.env['res.partner'].create({
                'name': self.customer_name or self.customer_email,
                'phone': self.customer_phone,
                'email': self.customer_email.strip(),
            })
        return partner

    def _validate_survey_template(self):
        self.ensure_one()
        if not self.followup_type_id.survey_template_id:
            raise UserError(_(
                'The follow-up type "%(type)s" is not connected to a survey template. '
                'Please configure a survey under Follow Up > Configuration > Follow-up Types.',
                type=self.followup_type_id.name,
            ))

    def action_start_survey(self):
        self.ensure_one()
        if self.survey_user_input_id:
            raise UserError(_('A survey has already been started for this follow-up record.'))
        self._validate_survey_template()
        survey = self.followup_type_id.survey_template_id
        partner = self._get_or_create_partner()
        answer = survey._create_answer(
            partner=partner,
            email=partner.email,
            check_attempts=False,
            followup_id=self.id,
        )
        self.write({
            'partner_id': partner.id,
            'survey_user_input_id': answer.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'name': _('Start Survey'),
            'target': 'new',
            'url': answer.get_start_url(),
        }

    def action_retire_survey(self):
        self.ensure_one()
        if not self.survey_user_input_id:
            raise UserError(_('No survey is linked to this follow-up record.'))
        user_input = self.survey_user_input_id.sudo()
        self.write({'survey_user_input_id': False})
        user_input.unlink()
        return self.action_start_survey()

    def action_view_survey_answers(self):
        self.ensure_one()
        if not self.survey_user_input_id:
            raise UserError(_('No survey response is linked to this follow-up record.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Survey Answers'),
            'res_model': 'survey.user_input',
            'res_id': self.survey_user_input_id.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }

    def unlink(self):
        linked_inputs = self.env['survey.user_input'].search([
            ('followup_id', 'in', self.ids),
        ])
        blocked = self.filtered(
            lambda record: record.survey_user_input_id
            or record.id in linked_inputs.mapped('followup_id').ids
        )
        if blocked:
            raise UserError(_(
                'You cannot delete follow-up record(s) linked to a survey response: %s. '
                'Use "Retire Survey" first to remove the survey, then delete the record.',
                ', '.join(blocked.mapped('name')),
            ))
        return super().unlink()

    def unlink(self):
        for record in self:
            linked_inputs = self.env['survey.user_input'].sudo().search([
                '|',
                ('id', '=', record.survey_user_input_id.id),
                ('followup_id', '=', record.id),
            ])
            if linked_inputs:
                raise UserError(_(
                    'You cannot delete follow-up record "%(reference)s" because it has '
                    'linked survey response(s). Use "Retire Survey" first to remove them.',
                    reference=record.name,
                ))
        return super().unlink()
