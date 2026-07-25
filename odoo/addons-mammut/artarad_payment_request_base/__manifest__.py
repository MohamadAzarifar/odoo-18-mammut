# -*- coding: utf-8 -*-
{
    "name": "Artarad Payment Request Base",

    "summary": 
        """
            Payment Request Base
        """,

    "description":
        """
            This module adds a basement app for in order to requesting payments.
        """,

    'author': "Artarad Team",

    'license': 'LGPL-3',

    'website': "https://www.artadoo.ir",

    'category': "Web",

    'version': "1.0",

    "depends": ["base", "web", "account", "hr"],

    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/default_data.xml",
        "views/account_payment_request_views.xml",
        "views/hr_employee_views.xml",
        "views/res_config_settings_views.xml",
        "views/menus.xml",
    ],
    
    "installable": True,
    "application": True,
    "auto_install": False,
}