import json
from odoo import models


class IrActionReport(models.Model):
    _inherit = 'ir.actions.report'

    def render_and_send(self, devices, res_ids, data=None, print_id=0, websocket=True):
        """
            Send the dictionary in message to the iot_box via websocket, or return the data to be sent by longpolling.
        """
        # only override the method for delivery_iot reports
        if self.report_name not in ['delivery_iot.report_shipping_labels', 'delivery_iot.report_shipping_docs']:
            return super().render_and_send(devices, res_ids, data=data, print_id=print_id, websocket=websocket)

        # set the default printer id in the system parameters for auto printing
        icp_sudo = self.env['ir.config_parameter'].sudo()
        res_user_printers = json.loads(icp_sudo.get_param('delivery_iot.res_user_printers', '{}'))

        for device in devices:
            res_user_printers[str(self.env.user.id)] = device['identifier']
        icp_sudo.set_param('delivery_iot.res_user_printers', json.dumps(res_user_printers))

        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'stock.picking'),
            ('res_id', 'in', res_ids),
            '|', ('name', 'ilike', '%.zplii'), ('name', 'ilike', '%.zpl'),
        ], order='id desc', limit=1)
        if not attachment:
            return []

        iot_identifiers = {device["iotIdentifier"] for device in devices}
        if not websocket:
            return [
                [
                    self.env["iot.box"].search([("identifier", "=", device["iotIdentifier"])]).ip,
                    device["identifier"],
                    device['name'],
                    attachment.datas,
                ]
                for device in devices
            ]

        self._send_websocket({
            "iotDevice": {
                "iotIdentifiers": list(iot_identifiers),
                "identifiers": [{
                    "identifier": device["identifier"],
                    "id": device["id"]
                } for device in devices],
            },
            "print_id": print_id,
            "document": attachment.datas
        })
