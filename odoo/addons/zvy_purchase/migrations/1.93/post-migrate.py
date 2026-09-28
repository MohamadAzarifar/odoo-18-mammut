def migrate(cr, version):
    """Soften Approvals multi-company rules for purchase-linked records."""
    cr.execute(
        """
        UPDATE ir_rule
           SET domain_force = %s
         WHERE id IN (
            SELECT res_id FROM ir_model_data
             WHERE module = 'approvals' AND name = 'approval_request_rule'
         )
        """,
        (
            "['|', ('company_id', 'in', company_ids), ('zvy_purchase_request_id', '!=', False)]",
        ),
    )
    cr.execute(
        """
        UPDATE ir_rule
           SET domain_force = %s
         WHERE id IN (
            SELECT res_id FROM ir_model_data
             WHERE module = 'approvals' AND name = 'approval_product_line_rule'
         )
        """,
        (
            "['|', ('company_id', 'in', company_ids), ('approval_request_id.zvy_purchase_request_id', '!=', False)]",
        ),
    )
    cr.execute(
        """
        UPDATE ir_rule
           SET domain_force = %s
         WHERE id IN (
            SELECT res_id FROM ir_model_data
             WHERE module = 'approvals' AND name = 'approval_approver_rule'
         )
        """,
        (
            "['|', ('company_id', 'in', company_ids), ('request_id.zvy_purchase_request_id', '!=', False)]",
        ),
    )
