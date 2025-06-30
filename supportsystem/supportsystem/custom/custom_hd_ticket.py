from frappe.utils import today
from frappe.utils.user import get_user_fullname
import frappe
import requests
import json
from pytz import UTC
from dateutil.parser import isoparse

def after_insert(doc=None, method=None):
        # frappe.throw('custom_hd_ticket after_insert')
        if not doc.custom_ticket_timeline:
            doc.append("custom_ticket_timeline", {
                "timestamp": frappe.utils.now_datetime(),
                "date": today(),
                "status": doc.custom_ticket_status,
                "note": "Ticket created with status Open",
                "added_by": doc.custom_created_byname
            })
            doc.save()


def validate(doc=None, method=None):

        if not doc.customer and doc.custom_client_url:
            customer_name = frappe.db.get_value('Customer', {'website': doc.custom_client_url}, 'customer_name')
            if customer_name:
                doc.customer = customer_name
                frappe.logger().info(f"Customer set to: {customer_name}")
            else:
                frappe.throw(_("No customer found with the given client URL.")) 


@frappe.whitelist()
def set_status(doc):
    for d in frappe.get_all("Issue",{'custom_reference_ticket_id': doc['custom_reference_ticket_id']}):
        hdTicket = frappe.get_doc("Issue", d.name)

        hdTicket.custom_ticket_status = doc.get('custom_ticket_status') 
        hdTicket.custom_category = doc.get('custom_category') 

        # if doc['custom_ticket_status'] == 'Closed':
        hdTicket.custom_feedback =    doc.get('custom_feedback') or None
        hdTicket.custom_feedback_extra = doc.get('custom_feedback_extra') or None

        if doc.get('custom_feedback'):
            fb = frappe.get_doc("Issue Feedback Option", doc.get('custom_feedback'))
            hdTicket.custom_rating = fb.rating

        hdTicket.save()  
        frappe.db.commit()
        frappe.log_error(f'hd ticket new: f{hdTicket}')
        return {"message": "Status updated successfully"}



from datetime import datetime

@frappe.whitelist(allow_guest=True)
def make_timeline_entry(**kwargs):
    data = frappe._dict(kwargs)

    ticket = frappe.get_doc("Issue", data.parent)

    ticket.append("custom_ticket_timeline", {
        "timestamp": datetime.now(),
        "date": data.date,
        "status": data.status,
        "note": data.note,
        "added_by": data.added_by,
    })

    ticket.save(ignore_permissions=True)

    return {"message": "Timeline entry synced successfully"}