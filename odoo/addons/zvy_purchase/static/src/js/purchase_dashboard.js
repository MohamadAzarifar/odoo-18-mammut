/** @odoo-module **/

import { loadBundle } from "@web/core/assets";
import { getColor, hexToRGBA } from "@web/core/colors/colors";
import { cookie } from "@web/core/browser/cookie";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Layout } from "@web/search/layout";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { Component, onWillStart, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";

export class PurchaseDashboardCard extends Component {
    static template = "zvy_purchase.PurchaseDashboardCard";
    static props = {
        card: Object,
        onCheck: Function,
    };

    setup() {
        this.doughnutRef = useRef("doughnut");
        this.lineRef = useRef("line");
        this.doughnutChart = null;
        this.lineChart = null;
        this.ofLabel = _t("of");
        this.last14DaysLabel = _t("Last 14 days");
        this.checkLabel = _t("Check");
        const colorScheme = cookie.get("color_scheme");

        useEffect(
            () => {
                this.renderCharts(colorScheme);
                return () => this.destroyCharts();
            },
            () => [this.props.card]
        );

        onWillUnmount(() => this.destroyCharts());
    }

    destroyCharts() {
        if (this.doughnutChart) {
            this.doughnutChart.destroy();
            this.doughnutChart = null;
        }
        if (this.lineChart) {
            this.lineChart.destroy();
            this.lineChart = null;
        }
    }

    renderCharts(colorScheme) {
        this.destroyCharts();
        const card = this.props.card;
        const primary = getColor(0, colorScheme, "odoo");
        const secondary = getColor(4, colorScheme, "odoo");

        if (this.doughnutRef.el) {
            const values = card.doughnut.values;
            const hasData = values.some((v) => v > 0);
            this.doughnutChart = new Chart(this.doughnutRef.el, {
                type: "doughnut",
                data: {
                    labels: card.doughnut.labels,
                    datasets: [
                        {
                            data: hasData ? values : [1],
                            backgroundColor: hasData
                                ? [primary, hexToRGBA(secondary, 0.35)]
                                : [hexToRGBA(secondary, 0.2)],
                            borderWidth: 0,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: "65%",
                    plugins: {
                        legend: { display: false },
                        tooltip: { enabled: hasData },
                    },
                },
            });
        }

        if (this.lineRef.el) {
            this.lineChart = new Chart(this.lineRef.el, {
                type: "line",
                data: {
                    labels: card.line.labels,
                    datasets: [
                        {
                            data: card.line.values,
                            borderColor: primary,
                            backgroundColor: hexToRGBA(primary, 0.15),
                            fill: "start",
                            borderWidth: 2,
                            pointRadius: 0,
                            tension: 0.3,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: { intersect: false, mode: "index" },
                    },
                    scales: {
                        x: { display: false },
                        y: {
                            display: false,
                            beginAtZero: true,
                            suggestedMax: Math.max(1, ...card.line.values),
                        },
                    },
                },
            });
        }
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
            await loadBundle("web.chartjs_lib");
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
