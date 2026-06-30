/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, onWillStart, onMounted, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";

export class PriceChartWidget extends Component {
    static template = "polymarket_bot.PriceChartWidget";

    setup() {
        this.orm = useService("orm");
        this.canvasRef = useRef("canvas");
        this.chart = null;

        onWillStart(async () => {
            await loadJS("https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js");
        });

        onMounted(async () => {
            const resId = this.props.record.resId;
            if (!resId) return;
            const data = await this.orm.call(
                "polymarket_bot.market",
                "get_price_chart_data",
                [[resId]]
            );
            this.renderChart(data);
        });
    }

    renderChart(data) {
        const ctx = this.canvasRef.el.getContext("2d");
        if (this.chart) {
            this.chart.destroy();
        }
        this.chart = new window.Chart(ctx, {
            type: "line",
            data: {
                labels: data.labels,
                datasets: [
                    {
                        label: "Up ask",
                        data: data.yes_ask,
                        borderColor: "#378ADD",
                        borderWidth: 2,
                        pointRadius: 0,
                        tension: 0.15,
                        fill: false,
                    },
                    {
                        label: "Down ask",
                        data: data.no_ask,
                        borderColor: "#D85A30",
                        borderWidth: 2,
                        pointRadius: 0,
                        tension: 0.15,
                        fill: false,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { ticks: { maxTicksLimit: 8, maxRotation: 0 } },
                    y: { min: 0, max: 1 },
                },
                plugins: {
                    legend: { display: true, position: "top" },
                },
            },
        });
    }
}

registry.category("view_widgets").add("price_chart_widget", { component: PriceChartWidget });
