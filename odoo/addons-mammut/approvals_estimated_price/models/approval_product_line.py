from odoo import api, fields, models

class ApprovalProductLine(models.Model):
    _inherit = 'approval.product.line' 

   
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )

    estimated_cost = fields.Monetary(
        string="Estimated Cost", 
        currency_field='currency_id', 
        default=0.0
    )

    subtotal = fields.Monetary(
        string="Subtotal", 
        compute="_compute_subtotal", 
        currency_field='currency_id', 
        store=True
    )

    @api.depends('quantity', 'estimated_cost')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.estimated_cost
