{
    "name": "Purchase",
    "version": "1.36",
    "category": "Inventory/Purchase",
    "summary": "Purchase requests with items and vendor offers",
    "depends": ["product", "mail", "web"],
    "data": [
        "security/zvy_purchase_security.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence_data.xml",
        "views/zvy_purchase_request_views.xml",
        "views/zvy_purchase_avl_views.xml",
        "views/product_product_views.xml",
        "wizard/zvy_purchase_assign_expert_wizard_views.xml",
        "wizard/zvy_purchase_back_to_draft_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "zvy_purchase/static/src/js/purchase_item_one2many.js",
        ],
    },
    "application": True,
    "installable": True,
    "license": "LGPL-3",
}
