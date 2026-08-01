# -*- coding: utf-8 -*-
import base64

from odoo import _, http
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.http import request
from odoo.addons.portal.controllers import portal
from odoo.addons.portal.controllers.portal import pager as portal_pager

class TenderingCustomerPortal(portal.CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'tender_count' in counters:
            Envelope = request.env['zvy.closed.envelope']
            values['tender_count'] = (
                Envelope.search_count(Envelope._get_portal_domain())
                if Envelope.has_access('read') else 0
            )
        return values

    def _tender_get_page_view_values(self, envelope, access_token, **kwargs):
        partner = request.env.user.partner_id
        invite_partner = envelope._portal_invite_partner(partner)
        Bid = request.env['zvy.closed.envelope.bid']
        own_bid = Bid.search([
            ('envelope_id', '=', envelope.id),
            ('partner_id', '=', invite_partner.id),
        ], limit=1) if invite_partner else Bid
        bidding_open = Bid._portal_bidding_open(envelope)
        # Line summary via sudo — portal has no PR ACL (Architecture §5).
        lines = envelope.sudo().request_id.line_ids
        values = {
            'envelope': envelope,
            'page_name': 'tender',
            'own_bid': own_bid,
            'bidding_open': bidding_open,
            'lines': lines,
            'published_documents': envelope.published_document_ids,
            'error': kwargs.get('error'),
            'success': kwargs.get('success'),
        }
        return self._get_page_view_values(
            envelope, access_token, values, 'my_tenders_history', False, **kwargs
        )

    def _ensure_tender_invite_access(self, envelope):
        partner = request.env.user.partner_id
        if request.env.user._is_public() or not envelope._portal_partner_matches(partner):
            raise AccessError(_('You are not invited to this tender.'))

    @http.route(['/my/tenders', '/my/tenders/page/<int:page>'], type='http', auth='user', website=True)
    def portal_my_tenders(self, page=1, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        Envelope = request.env['zvy.closed.envelope']
        domain = Envelope._get_portal_domain()

        searchbar_sortings = {
            'date': {'label': _('Newest'), 'order': 'id desc'},
            'name': {'label': _('Reference'), 'order': 'name asc'},
            'deadline': {'label': _('Bid Deadline'), 'order': 'bid_deadline asc'},
        }
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        total = Envelope.search_count(domain)
        pager = portal_pager(
            url='/my/tenders',
            url_args={'sortby': sortby},
            total=total,
            page=page,
            step=self._items_per_page,
        )
        tenders = Envelope.search(
            domain,
            order=order,
            limit=self._items_per_page,
            offset=pager['offset'],
        )
        request.session['my_tenders_history'] = tenders.ids[:100]

        values.update({
            'tenders': tenders,
            'page_name': 'tender',
            'pager': pager,
            'default_url': '/my/tenders',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
        })
        return request.render('zvy_tendering.portal_my_tenders', values)

    @http.route(['/my/tenders/<int:envelope_id>'], type='http', auth='public', website=True)
    def portal_my_tender(self, envelope_id, access_token=None, **kw):
        try:
            envelope_sudo = self._document_check_access(
                'zvy.closed.envelope', envelope_id, access_token=access_token
            )
        except (AccessError, MissingError):
            return request.redirect('/my')

        # Logged-in portal users must be invited; token-only public access still
        # requires a matching portal user for bidding actions (POST routes).
        user = request.env.user
        if not user._is_public():
            try:
                self._ensure_tender_invite_access(envelope_sudo)
            except AccessError:
                return request.redirect('/my')

        values = self._tender_get_page_view_values(envelope_sudo, access_token, **kw)
        return request.render('zvy_tendering.portal_my_tender', values)

    @http.route(
        ['/my/tenders/<int:envelope_id>/bid'],
        type='http',
        auth='user',
        methods=['POST'],
        website=True,
    )
    def portal_my_tender_bid(self, envelope_id, access_token=None, **post):
        try:
            envelope_sudo = self._document_check_access(
                'zvy.closed.envelope', envelope_id, access_token=access_token
            )
            self._ensure_tender_invite_access(envelope_sudo)
        except (AccessError, MissingError):
            return request.redirect('/my')

        partner = request.env.user.partner_id
        amount = post.get('amount')
        notes = post.get('notes')
        attachment_ids = self._portal_save_bid_attachments(envelope_sudo, post)

        error = None
        success = None
        try:
            request.env['zvy.closed.envelope.bid']._portal_upsert_bid(
                envelope_sudo,
                partner,
                amount,
                notes=notes,
                attachment_ids=attachment_ids,
            )
            success = _('Your sealed bid has been submitted.')
        except UserError as exc:
            error = str(exc.args[0]) if exc.args else str(exc)

        values = self._tender_get_page_view_values(
            envelope_sudo, access_token, error=error, success=success
        )
        return request.render('zvy_tendering.portal_my_tender', values)

    @http.route(
        ['/my/tenders/<int:envelope_id>/withdraw'],
        type='http',
        auth='user',
        methods=['POST'],
        website=True,
    )
    def portal_my_tender_withdraw(self, envelope_id, access_token=None, **post):
        try:
            envelope_sudo = self._document_check_access(
                'zvy.closed.envelope', envelope_id, access_token=access_token
            )
            self._ensure_tender_invite_access(envelope_sudo)
        except (AccessError, MissingError):
            return request.redirect('/my')

        error = None
        success = None
        try:
            request.env['zvy.closed.envelope.bid']._portal_withdraw_bid(
                envelope_sudo, request.env.user.partner_id
            )
            success = _('Your bid has been withdrawn.')
        except UserError as exc:
            error = str(exc.args[0]) if exc.args else str(exc)

        values = self._tender_get_page_view_values(
            envelope_sudo, access_token, error=error, success=success
        )
        return request.render('zvy_tendering.portal_my_tender', values)

    def _portal_save_bid_attachments(self, envelope, post):
        """Create ir.attachment records from multipart upload; None keeps existing."""
        uploaded = request.httprequest.files.getlist('attachments')
        real_files = [f for f in uploaded if f and f.filename]
        if not real_files:
            return None
        Attachment = request.env['ir.attachment'].sudo()
        ids = []
        for ufile in real_files:
            data = ufile.read()
            if not data:
                continue
            att = Attachment.create({
                'name': ufile.filename,
                'datas': base64.b64encode(data),
                'res_model': 'zvy.closed.envelope',
                'res_id': envelope.id,
                'type': 'binary',
            })
            ids.append(att.id)
        return ids
    @http.route(
        ['/my/tenders/<int:envelope_id>/document/<int:attachment_id>'],
        type='http',
        auth='public',
        website=True,
    )
    def portal_my_tender_document(self, envelope_id, attachment_id, access_token=None, **kw):
        try:
            envelope_sudo = self._document_check_access(
                'zvy.closed.envelope', envelope_id, access_token=access_token
            )
        except (AccessError, MissingError):
            return request.redirect('/my')

        if not request.env.user._is_public():
            try:
                self._ensure_tender_invite_access(envelope_sudo)
            except AccessError:
                return request.redirect('/my')

        attachment = request.env['ir.attachment'].sudo().browse(attachment_id).exists()
        if not attachment or attachment not in envelope_sudo.published_document_ids:
            return request.redirect(envelope_sudo.get_portal_url())

        return request.env['ir.binary']._get_stream_from(
            attachment
        ).get_response(as_attachment=True)
