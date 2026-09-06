# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

ZVY_BID_PAYMENT_TYPES = [
    ('cash', 'Cash'),
    ('credit', 'Credit'),
    ('lc', 'Letter of Credit'),
    ('other', 'Other'),
]


class ZvyClosedEnvelopeBidLine(models.Model):
    _name = 'zvy.closed.envelope.bid.line'
    _description = 'Closed Envelope Bid Line'
    _order = 'id'

    _sql_constraints = [
        (
            'bid_request_line_uniq',
            'unique(bid_id, request_line_id)',
            'A bid may only have one line per purchase request item.',
        ),
    ]

    _SEALED_FIELDS = (
        'price_unit',
        'final_price',
        'comments',
        'proforma',
        'delivery_time',
        'payment_type',
        'payment_duration',
    )

    bid_id = fields.Many2one(
        'zvy.closed.envelope.bid',
        string='Bid',
        required=True,
        ondelete='cascade',
        index=True,
    )
    envelope_id = fields.Many2one(
        related='bid_id.envelope_id',
        store=True,
        index=True,
    )
    partner_id = fields.Many2one(
        related='bid_id.partner_id',
        store=True,
        index=True,
    )
    company_id = fields.Many2one(
        related='bid_id.company_id',
        store=True,
        index=True,
    )
    currency_id = fields.Many2one(
        related='bid_id.currency_id',
    )
    request_line_id = fields.Many2one(
        'zvy.purchase.request.line',
        string='Request Line',
        required=True,
        ondelete='restrict',
        index=True,
    )
    product_id = fields.Many2one(
        related='request_line_id.product_id',
        store=True,
    )
    product_uom_qty = fields.Float(
        related='request_line_id.product_uom_qty',
        string='Quantity',
        digits='Product Unit of Measure',
    )
    product_uom_id = fields.Many2one(
        related='request_line_id.product_uom_id',
    )
    price_unit = fields.Monetary(
        string='Unit Price',
        currency_field='currency_id',
        default=0.0,
        help='Optional per-line unit price. Leave empty when not bidding on this item.',
    )
    delivery_time = fields.Char(string='Delivery Time')
    payment_type = fields.Selection(
        selection=ZVY_BID_PAYMENT_TYPES,
        string='Payment Type',
    )
    payment_duration = fields.Char(string='Payment Duration')
    comments = fields.Text()
    proforma = fields.Binary(string='Proforma')
    proforma_filename = fields.Char(string='Proforma Filename')
    discount_percent = fields.Float(
        string='Discount %',
        help='Commission Manager discount applied after bids are opened.',
    )
    final_price = fields.Monetary(
        string='Final Price',
        currency_field='currency_id',
        compute='_compute_final_price',
        store=True,
        help='Unit price × (1 − discount/100).',
    )
    is_winner = fields.Boolean(
        string='Winner',
        copy=False,
        help='Set by the Commission Manager after bids are opened.',
    )

    @api.depends('price_unit', 'discount_percent')
    def _compute_final_price(self):
        for line in self:
            disc = line.discount_percent or 0.0
            line.final_price = (line.price_unit or 0.0) * (1.0 - disc / 100.0)

    @api.constrains('discount_percent')
    def _check_discount_percent(self):
        for line in self:
            if line.discount_percent < 0.0 or line.discount_percent > 100.0:
                raise ValidationError(_(
                    'Discount percent must be between 0 and 100.'
                ))

    @api.constrains('request_line_id', 'bid_id')
    def _check_request_line_in_envelope(self):
        for line in self:
            envelope = line.bid_id.envelope_id
            scope = envelope.line_ids or envelope.request_id.line_ids
            if line.request_line_id not in scope:
                raise ValidationError(_(
                    'Bid line %(product)s is not in the closed-envelope scope.',
                    product=line.request_line_id.display_name,
                ))

    @api.constrains('is_winner', 'request_line_id', 'bid_id')
    def _check_unique_winner(self):
        for line in self.filtered('is_winner'):
            others = self.search([
                ('id', '!=', line.id),
                ('is_winner', '=', True),
                ('request_line_id', '=', line.request_line_id.id),
                ('envelope_id', '=', line.envelope_id.id),
            ], limit=1)
            if others:
                raise ValidationError(_(
                    'Only one winner is allowed per item on a closed envelope.'
                ))

    def _user_can_see_sealed(self):
        self.ensure_one()
        return self.bid_id._user_can_see_sealed()

    def read(self, fields=None, load='_classic_read'):
        records = super().read(fields=fields, load=load)
        if self.env.su:
            return records
        sealed_names = set(self._SEALED_FIELDS)
        field_set = set(fields) if fields else None
        for values, line in zip(records, self):
            if line._user_can_see_sealed():
                continue
            for fname in sealed_names:
                if field_set is not None and fname not in field_set:
                    continue
                if fname not in values:
                    continue
                if fname in ('comments', 'proforma', 'delivery_time',
                             'payment_type', 'payment_duration'):
                    values[fname] = False
                else:
                    values[fname] = 0.0
        return records

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
        for vals in vals_list:
            bid = self.env['zvy.closed.envelope.bid'].browse(vals.get('bid_id'))
            envelope = bid.envelope_id
            if envelope and envelope.state not in ('portal_open', 'opened'):
                raise UserError(_(
                    'Bid lines can only be entered when the envelope is open '
                    'for bidding or already opened.'
                ))
            if not self.env.su and not self._user_is_commission_manager_or_admin():
                raise UserError(_(
                    'Only Commission Managers can enter sealed bid lines manually.'
                ))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            sealed_changed = set(vals) & set(self._SEALED_FIELDS)
            discount_changed = 'discount_percent' in vals
            winner_changed = 'is_winner' in vals
            if sealed_changed or discount_changed or winner_changed:
                if not self._user_is_commission_manager_or_admin():
                    raise UserError(_(
                        'Only Commission Managers can edit sealed bid lines, '
                        'discounts, or winners.'
                    ))
            for line in self:
                state = line.envelope_id.state
                if sealed_changed and state not in ('portal_open', 'opened'):
                    raise UserError(_(
                        'Sealed bid line content cannot be changed in this '
                        'envelope state.'
                    ))
                if discount_changed and state not in ('opened', 'awarded'):
                    raise UserError(_(
                        'Discount can only be applied after bids are opened.'
                    ))
                if winner_changed and state != 'opened':
                    raise UserError(_(
                        'Winners can only be marked after bids are opened.'
                    ))
        old_discounts = {}
        if 'discount_percent' in vals:
            old_discounts = {
                line.id: line.discount_percent for line in self
            }
        res = super().write(vals)
        if old_discounts:
            for line in self:
                if old_discounts.get(line.id) != line.discount_percent:
                    line._post_discount_chatter()
        return res

    def _post_discount_chatter(self):
        self.ensure_one()
        product = self.product_id.display_name or self.request_line_id.display_name
        vendor = self.partner_id.display_name
        envelope = self.envelope_id.sudo()
        envelope.message_post(body=_(
            'Discount on %(product)s / %(vendor)s: %(discount)s%% → final %(price)s',
            product=product,
            vendor=vendor,
            discount=self.discount_percent,
            price=self.currency_id.format(self.final_price)
            if self.currency_id else self.final_price,
        ))
