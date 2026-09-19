# -*- coding: utf-8 -*-
"""Drop unused high-value threshold; routing uses purchase level Large."""
from odoo.tools.sql import column_exists


def migrate(cr, version):
    if column_exists(cr, 'res_company', 'zvy_high_value_threshold'):
        cr.execute(
            'ALTER TABLE "res_company" DROP COLUMN IF EXISTS "zvy_high_value_threshold"'
        )
