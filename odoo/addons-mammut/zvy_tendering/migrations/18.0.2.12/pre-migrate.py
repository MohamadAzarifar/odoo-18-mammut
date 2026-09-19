# -*- coding: utf-8 -*-
"""Drop obsolete per-band user M2M tables; add HR job columns on res.company.

Keep column creates in sync with ``hooks.ensure_res_company_columns`` (do not
import the addon here: pre-migrate runs before ``load_openerp_module``).
"""
from odoo.tools.sql import column_exists, create_column, table_exists

_JOB_COLUMNS = (
    ('zvy_signatory_minor_job_id', 'int4'),
    ('zvy_signatory_medium_job_id', 'int4'),
    ('zvy_signatory_major_job_id', 'int4'),
    ('zvy_signatory_large_job_id', 'int4'),
    ('zvy_signatory_board_job_id', 'int4'),
    ('zvy_signatory_formalities_job_id', 'int4'),
)

_DROP_COLUMNS = (
    ('res_company', 'zvy_sole_source_job_id'),
    ('zvy_purchase_request', 'has_sole_source'),
    ('zvy_purchase_request_line', 'sole_source'),
)

_OBSOLETE_M2M_TABLES = (
    'zvy_company_signatory_minor_rel',
    'zvy_company_signatory_medium_rel',
    'zvy_company_signatory_major_rel',
    'zvy_company_signatory_large_rel',
    'zvy_company_signatory_board_rel',
    'zvy_company_signatory_formalities_rel',
    'zvy_company_sole_source_approver_rel',
)


def migrate(cr, version):
    for name, coltype in _JOB_COLUMNS:
        if not column_exists(cr, 'res_company', name):
            create_column(cr, 'res_company', name, coltype)
    for table, column in _DROP_COLUMNS:
        if column_exists(cr, table, column):
            cr.execute(f'ALTER TABLE "{table}" DROP COLUMN IF EXISTS "{column}"')
    for table in _OBSOLETE_M2M_TABLES:
        if table_exists(cr, table):
            cr.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
