/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Layout } from "@web/search/layout";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { Component, onWillStart, useState } from "@odoo/owl";

export class PurchaseDashboardCard extends Component {
    static template = "zvy_purchase.PurchaseDashboardCard";
    static props = {
        card: Object,
        onCheck: Function,
    };

    setup() {
        this.checkLabel = _t("Check");
    }

    onCheckClick() {
        this.props.onCheck(this.props.card);
    }
}

export class PurchaseDashboard extends Component {
    static template = "zvy_purchase.PurchaseDashboard";
    static components = { Layout, PurchaseDashboardCard };
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.emptyLabel = _t("No work queues for your role.");
        this.state = useState({
            cards: [],
        });

        onWillStart(async () => {
            this.state.cards = await this.orm.call(
                "zvy.purchase.dashboard",
                "get_dashboard_cards",
                []
            );
        });
    }

    get display() {
        return {
            controlPanel: {},
        };
    }

    async openCard(card) {
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: card.title,
            res_model: card.res_model,
            views: [
                [false, "list"],
                [false, "form"],
            ],
            domain: card.domain,
            context: { create: false },
        });
    }
}

registry.category("actions").add("zvy_purchase.dashboard", PurchaseDashboard);
