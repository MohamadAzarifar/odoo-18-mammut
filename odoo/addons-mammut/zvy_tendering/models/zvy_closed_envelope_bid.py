# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ZvyClosedEnvelopeBid(models.Model):
    _name = 'zvy.closed.envelope.bid'
    _description = 'Closed Envelope Bid'
    _order = 'id'

    _SEALED_FIELDS = ('amount', 'notes', 'attachment_ids')

    envelope_id = fields.Many2one(
        'zvy.closed.envelope',
        string='Closed Envelope',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        related='envelope_id.company_id',
        store=True,
        index=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Supplier',
        required=True,
        ondelete='restrict',
        index=True,
    )
    currency_id = fields.Many2one(
        related='envelope_id.currency_id',
    )
    amount = fields.Monetary(
        string='Bid Amount',
        currency_field='currency_id',
        required=True,
        default=0.0,
    )
    notes = fields.Text()
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'zvy_ce_bid_ir_attachment_rel',
        'bid_id',
        'attachment_id',
        string='Attachments',
    )
    submitted_at = fields.Datetime(
        string='Submitted At',
        default=fields.Datetime.now,
        required=True,
    )
    source = fields.Selection(
        selection=[
            ('manual', 'Manual'),
            ('portal', 'Portal'),
        ],
        default='manual',
        required=True,
    )

    @api.constrains('partner_id', 'envelope_id')
    def _check_partner_invited(self):
        for bid in self:
            if bid.partner_id not in bid.envelope_id.invite_partner_ids:
                raise ValidationError(_(
                    'Bid partner must be on the closed-envelope invite list.'
                ))

    def _user_can_see_sealed(self):
        """Whether current user may see sealed bid content."""
        self.ensure_one()
        if self.env.su:
            return True
        user = self.env.user
        if user.has_group('zvy_tendering.group_zvy_tendering_admin'):
            return True
        if user.has_group('zvy_tendering.group_zvy_commission_manager'):
            return True
        if self.envelope_id.state in ('opened', 'awarded'):
            if user.has_group('zvy_tendering.group_zvy_commercial_manager'):
                return True
            if user.has_group('zvy_tendering.group_zvy_commercial_expert'):
                return True
            if user.has_group('zvy_tendering.group_zvy_commission_expert'):
                return True
        # Portal / partner check (Phase 5); allow commercial users linked to partner.
        if user.partner_id and user.partner_id == self.partner_id:
            return True
        return False

    def read(self, fields=None, load='_classic_read'):
        records = super().read(fields=fields, load=load)
        if self.env.su:
            return records
        sealed_names = set(self._SEALED_FIELDS)
        field_set = set(fields) if fields else None
        for values, bid in zip(records, self):
            if bid._user_can_see_sealed():
                continue
            for fname in sealed_names:
                if field_set is not None and fname not in field_set:
                    continue
                if fname not in values:
                    continue
                if fname == 'attachment_ids':
                    values[fname] = []
                elif fname == 'notes':
                    values[fname] = False
                else:
                    values[fname] = 0.0
        return records

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            envelope = self.env['zvy.closed.envelope'].browse(
                vals.get('envelope_id')
            )
            if envelope and envelope.state not in ('portal_open', 'opened'):
                raise UserError(_(
                    'Bids can only be entered when the envelope is open for bidding '
                    'or already opened.'
                ))
            if not self.env.su:
                is_mgr = self.env.user.has_group(
                    'zvy_tendering.group_zvy_commission_manager'
                )
                is_admin = self.env.user.has_group(
                    'zvy_tendering.group_zvy_tendering_admin'
                )
                if not (is_mgr or is_admin):
                    raise UserError(_(
                        'Only Commission Managers can enter sealed bids manually.'
                    ))
            vals.setdefault('source', 'manual')
            vals.setdefault('submitted_at', fields.Datetime.now())
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and set(vals) & set(self._SEALED_FIELDS):
            for bid in self:
                if bid.envelope_id.state not in ('portal_open', 'opened'):
                    raise UserError(_(
                        'Sealed bid content cannot be changed in this envelope state.'
                    ))
                is_mgr = self.env.user.has_group(
                    'zvy_tendering.group_zvy_commission_manager'
                )
                is_admin = self.env.user.has_group(
                    'zvy_tendering.group_zvy_tendering_admin'
                )
                if not (is_mgr or is_admin):
                    raise UserError(_(
                        'Only Commission Managers can edit sealed bid content.'
                    ))
        return super().write(vals)
