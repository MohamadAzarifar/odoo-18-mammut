# -*- coding: utf-8 -*-


def migrate(cr, version):
    """Copy Phase 3 meeting M2M/MOM data onto FR-42 fields."""
    cr.execute("""
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'zvy_commission_meeting_case'
    """)
    has_junction = bool(cr.fetchone())
    cr.execute("""
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'zvy_commission_meeting_case_rel'
    """)
    has_rel = bool(cr.fetchone())
    if has_junction and has_rel:
        cr.execute("""
            INSERT INTO zvy_commission_meeting_case
                (meeting_id, case_id, request_id, company_id, review_status,
                 decision, create_uid, write_uid, create_date, write_date)
            SELECT
                rel.meeting_id,
                rel.case_id,
                c.request_id,
                m.company_id,
                'pending',
                'undecided',
                1, 1,
                NOW() AT TIME ZONE 'UTC',
                NOW() AT TIME ZONE 'UTC'
            FROM zvy_commission_meeting_case_rel rel
            JOIN zvy_commission_case c ON c.id = rel.case_id
            JOIN zvy_commission_meeting m ON m.id = rel.meeting_id
            WHERE NOT EXISTS (
                SELECT 1 FROM zvy_commission_meeting_case j
                WHERE j.meeting_id = rel.meeting_id AND j.case_id = rel.case_id
            )
        """)

    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'zvy_commission_meeting'
          AND column_name = 'requesting_company_id'
    """)
    if cr.fetchone():
        cr.execute("""
            UPDATE zvy_commission_meeting m
            SET requesting_company_id = sub.company_id
            FROM (
                SELECT j.meeting_id, MIN(c.company_id) AS company_id
                FROM zvy_commission_meeting_case j
                JOIN zvy_commission_case c ON c.id = j.case_id
                GROUP BY j.meeting_id
            ) sub
            WHERE m.id = sub.meeting_id
              AND m.requesting_company_id IS NULL
        """)
        cr.execute("""
            UPDATE zvy_commission_meeting
            SET requesting_company_id = company_id
            WHERE requesting_company_id IS NULL
        """)
        cr.execute("""
            WITH RECURSIVE ancestors AS (
                SELECT id, parent_id, id AS origin
                FROM res_company
                UNION ALL
                SELECT p.id, p.parent_id, a.origin
                FROM res_company p
                JOIN ancestors a ON a.parent_id = p.id
            ),
            roots AS (
                SELECT origin, id AS root_id
                FROM ancestors
                WHERE parent_id IS NULL
            )
            UPDATE zvy_commission_meeting m
            SET company_id = COALESCE(r.root_id, m.requesting_company_id)
            FROM roots r
            WHERE r.origin = m.requesting_company_id
        """)
        cr.execute("""
            UPDATE zvy_commission_meeting_case j
            SET company_id = m.company_id
            FROM zvy_commission_meeting m
            WHERE m.id = j.meeting_id
        """)

    cr.execute("""
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'zvy_commission_meeting_ir_attachment_rel'
    """)
    has_mom_rel = bool(cr.fetchone())
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'zvy_commission_meeting'
          AND column_name = 'minutes_attachment_id'
    """)
    has_minutes = bool(cr.fetchone())
    if has_mom_rel and has_minutes:
        cr.execute("""
            UPDATE zvy_commission_meeting m
            SET minutes_attachment_id = sub.attachment_id
            FROM (
                SELECT meeting_id, MIN(attachment_id) AS attachment_id
                FROM zvy_commission_meeting_ir_attachment_rel
                GROUP BY meeting_id
            ) sub
            WHERE m.id = sub.meeting_id
              AND m.minutes_attachment_id IS NULL
        """)
