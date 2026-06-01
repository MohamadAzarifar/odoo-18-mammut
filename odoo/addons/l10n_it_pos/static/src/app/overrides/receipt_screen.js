import { patch } from "@web/core/utils/patch";
import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { onMounted } from "@odoo/owl";
import { isFiscalPrinterActive } from "./helpers/utils";

patch(ReceiptScreen.prototype, {
    setup() {
        super.setup(...arguments);
        onMounted(async () => {
            const order = this.pos.get_order();
            if (isFiscalPrinterActive(this.pos.config) && !order.nb_print) {
                //make sure we only print the first time around
                await this.printReceipt({ order });
                if (this.pos.config.it_fiscal_cash_drawer) {
                    await this.pos.fiscalPrinter.openCashDrawer();
                }
            }
        });
    },

    //kept for stability purposes; code moved to pos_store
    async printReceipt({ order }) {
        this.pos.printReceipt({ order });
    },
});
