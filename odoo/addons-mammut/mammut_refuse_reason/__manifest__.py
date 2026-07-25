# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Approval Refuse Reason',
    'version': '1.0',
    'depends': ['mail', 'hr', 'product', 'approvals'],
    'data': [
    'security/ir.model.access.csv',

    'views/refuse_reason_wizard_views.xml',],
    'installable': True,
}