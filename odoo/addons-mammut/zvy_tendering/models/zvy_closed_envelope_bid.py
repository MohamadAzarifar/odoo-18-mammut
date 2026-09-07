# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ZvyClosedEnvelopeBid(models.Model):
    _name = 'zvy.closed.envelope.bid'
    _description = 'Closed Envelope Bid'
    _order = 'id'
    _sql_constraints = [
        (
            'envelope_partner_uniq',
            'unique(envelope_id, partner_id)',
            'Only one bid per supplier is allowed on a closed envelope.',
        ),
    ]

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
    holding_company_id = fields.Many2one(
        related='envelope_id.holding_company_id',
        store=True,
        index=True,
        string='Holding Company',
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
    request_id = fields.Many2one(
        related='envelope_id.request_id',
    )
    line_ids = fields.One2many(
        'zvy.closed.envelope.bid.line',
        'bid_id',
        string='Bid Lines',
    )
    amount = fields.Monetary(
        string='Bid Amount',
        currency_field='currency_id',
        compute='_compute_amount',
        store=True,
        help='Sum of unit price × quantity across bid lines (before discount).',
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

    @api.depends('line_ids.price_unit', 'line_ids.product_uom_qty')
    def _compute_amount(self):
        for bid in self:
            bid.amount = sum(
                (line.price_unit or 0.0) * (line.product_uom_qty or 0.0)
                for line in bid.line_ids
            )

    @api.constrains('partner_id', 'envelope_id')
    def _check_partner_invited(self):
        for bid in self:
            if bid.partner_id not in bid.envelope_id.invite_partner_ids:
                raise ValidationError(_(
                    'Bid partner must be on the closed-envelope invite list.'
                ))
            others = self.search([
                ('id', '!=', bid.id),
                ('envelope_id', '=', bid.envelope_id.id),
                ('partner_id', '=', bid.partner_id.id),
            ], limit=1)
            if others:
                raise ValidationError(_(
                    'Only one bid per supplier is allowed on a closed envelope.'
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
        # Portal / partner check: bidder may always read own bid.
        if user.partner_id and (
            user.partner_id == self.partner_id
            or user.partner_id.commercial_partner_id
            == self.partner_id.commercial_partner_id
        ):
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

    @api.model
    def _portal_bidding_open(self, envelope):
        """True when portal suppliers may submit/update/withdraw bids."""
        if not envelope or envelope.state != 'portal_open':
            return False
        now = fields.Datetime.now()
        if envelope.bid_deadline and now > envelope.bid_deadline:
            return False
        return True

    def _sync_lines_from_amount(self, amount):
        """Create or update a single bid line so header amount matches `amount`."""
        self.ensure_one()
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            raise UserError(_('Please provide a valid bid amount.')) from None
        if amount <= 0:
            raise UserError(_('Bid amount must be greater than zero.'))
        scope = self.envelope_id.line_ids or self.envelope_id.request_id.line_ids
        if not scope:
            raise UserError(_('This tender has no purchase request lines to bid on.'))
        request_line = scope[:1]
        qty = request_line.product_uom_qty or 1.0
        price_unit = amount / qty
        BidLine = self.env['zvy.closed.envelope.bid.line'].sudo()
        existing = self.line_ids[:1]
        if existing:
            existing.sudo().write({
                'request_line_id': request_line.id,
                'price_unit': price_unit,
            })
        else:
            BidLine.create({
                'bid_id': self.id,
                'request_line_id': request_line.id,
                'price_unit': price_unit,
            })

    def _upsert_portal_lines(self, line_vals):
        """Replace portal bid lines from a list of dicts (sudo)."""
        self.ensure_one()
        BidLine = self.env['zvy.closed.envelope.bid.line'].sudo()
        scope = self.envelope_id.line_ids or self.envelope_id.request_id.line_ids
        scope_ids = set(scope.ids)
        kept = self.env['zvy.closed.envelope.bid.line']
        for vals in line_vals or []:
            request_line_id = int(vals.get('request_line_id') or 0)
            if not request_line_id or request_line_id not in scope_ids:
                raise UserError(_(
                    'A bid line refers to an item that is not part of this tender.'
                ))
            line_vals_write = {
                'price_unit': float(vals.get('price_unit') or 0.0),
                'delivery_time': vals.get('delivery_time') or False,
                'payment_type': vals.get('payment_type') or False,
                'payment_duration': vals.get('payment_duration') or False,
                'comments': vals.get('comments') or False,
            }
            if 'proforma' in vals:
                line_vals_write['proforma'] = vals.get('proforma') or False
                line_vals_write['proforma_filename'] = (
                    vals.get('proforma_filename') or False
                )
            existing = self.line_ids.filtered(
                lambda l, rid=request_line_id: l.request_line_id.id == rid
            )[:1]
            if existing:
                existing.sudo().write(line_vals_write)
                kept |= existing
            else:
                line_vals_write.update({
                    'bid_id': self.id,
                    'request_line_id': request_line_id,
                })
                kept |= BidLine.create(line_vals_write)
        extra = self.line_ids - kept
        if extra:
            extra.sudo().unlink()

    @api.model
    def _portal_upsert_bid(
        self,
        envelope,
        partner,
        amount=None,
        notes=None,
        attachment_ids=None,
        line_vals=None,
    ):
        """Create or update a sealed portal bid (call under sudo from controllers)."""
        if not envelope._portal_partner_matches(partner):
            raise UserError(_('You are not invited to this tender.'))
        if not self._portal_bidding_open(envelope):
            raise UserError(_(
                'Bidding is closed for this tender (deadline passed or bids opened).'
            ))
        invite_partner = envelope._portal_invite_partner(partner)
        if not invite_partner:
            raise UserError(_('You are not invited to this tender.'))
        if not line_vals and (amount is None or amount == '' or amount is False):
            raise UserError(_('Please provide a valid bid amount.'))
        Bid = self.sudo()
        bid = Bid.search([
            ('envelope_id', '=', envelope.id),
            ('partner_id', '=', invite_partner.id),
        ], limit=1)
        vals = {
            'notes': notes or False,
            'source': 'portal',
            'submitted_at': fields.Datetime.now(),
        }
        if attachment_ids is not None:
            vals['attachment_ids'] = [(6, 0, list(attachment_ids))]
        if bid:
            bid.write(vals)
        else:
            vals.update({
                'envelope_id': envelope.id,
                'partner_id': invite_partner.id,
            })
            bid = Bid.create(vals)
        if line_vals:
            bid._upsert_portal_lines(line_vals)
        else:
            bid._sync_lines_from_amount(amount)
        return bid

    @api.model
    def _portal_withdraw_bid(self, envelope, partner):
        """Withdraw (unlink) the supplier's own portal bid while bidding is open."""
        if not envelope._portal_partner_matches(partner):
            raise UserError(_('You are not invited to this tender.'))
        if not self._portal_bidding_open(envelope):
            raise UserError(_(
                'Bids can only be withdrawn while the tender is open for bidding.'
            ))
        invite_partner = envelope._portal_invite_partner(partner)
        bid = self.sudo().search([
            ('envelope_id', '=', envelope.id),
            ('partner_id', '=', invite_partner.id),
        ], limit=1)
        if not bid:
            raise UserError(_('No bid found to withdraw.'))
        bid.unlink()
        return True

    def _user_is_commission_manager_or_admin(self):
        return (
            self.env.su
            or self.env.user.has_group(
                'zvy_tendering.group_zvy_commission_manager'
            )
            or self.env.user.has_group(
                'zvy_tendering.group_zvy_tendering_admin'
            )
        )

    @api.model_create_multi
    def create(self, vals_list):
        amounts = []
        for vals in vals_list:
            amounts.append(vals.pop('amount', None))
            envelope = self.env['zvy.closed.envelope'].browse(
                vals.get('envelope_id')
            )
            if envelope and envelope.state not in ('portal_open', 'opened'):
                raise UserError(_(
                    'Bids can only be entered when the envelope is open for bidding '
                    'or already opened.'
                ))
            if not self.env.su:
                if not self._user_is_commission_manager_or_admin():
                    raise UserError(_(
                        'Only Commission Managers can enter sealed bids manually.'
                    ))
            if vals.get('envelope_id') and vals.get('partner_id'):
                duplicate = self.sudo().search([
                    ('envelope_id', '=', vals['envelope_id']),
                    ('partner_id', '=', vals['partner_id']),
                ], limit=1)
                if duplicate:
                    raise ValidationError(_(
                        'Only one bid per supplier is allowed on a closed envelope.'
                    ))
            vals.setdefault('source', 'manual')
            vals.setdefault('submitted_at', fields.Datetime.now())
        bids = super().create(vals_list)
        for bid, amount in zip(bids, amounts):
            if amount is not None and amount != '' and not bid.line_ids:
                bid.sudo()._sync_lines_from_amount(amount)
        return bids

    def write(self, vals):
        amount = vals.pop('amount', None) if 'amount' in vals else None
        if not self.env.su and set(vals) & set(self._SEALED_FIELDS):
            for bid in self:
                if bid.envelope_id.state not in ('portal_open', 'opened'):
                    raise UserError(_(
                        'Sealed bid content cannot be changed in this envelope state.'
                    ))
                if not self._user_is_commission_manager_or_admin():
                    raise UserError(_(
                        'Only Commission Managers can edit sealed bid content.'
                    ))
        res = super().write(vals)
        if amount is not None:
            for bid in self:
                bid.sudo()._sync_lines_from_amount(amount)
        return res
