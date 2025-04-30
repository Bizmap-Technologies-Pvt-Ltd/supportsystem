from frappe.utils import today
from frappe.utils.user import get_user_fullname
from helpdesk.helpdesk.doctype.hd_ticket.hd_ticket import HDTicket
import frappe
import requests

def after_insert(doc=None, method=None):
        # frappe.throw('custom_hd_ticket after_insert')
        if not doc.custom_ticket_timeline:
            doc.append("custom_ticket_timeline", {
                "timestamp": frappe.utils.now_datetime(),
                "date": today(),
                "status": doc.custom_ticket_status,
                "note": "Ticket created with status Open",
                "added_by": doc.custom_created_by_name
            })
            doc.save()


def validate(doc=None, method=None):

        previous = doc.get_doc_before_save() or {}

        if(previous.get('resolution_details') != doc.resolution_details):
            doc.custom_ticket_status = 'Resolved'
            # self.send_resolution()
        update_status(doc)

def update_status(doc=None, method=None):
    if doc.custom_ticket_status == 'Open':				
        return
    elif doc.custom_ticket_status == 'Resolved':			
        status = 'Resolved'
        if not doc.resolution_details:
            frappe.throw(("Resolution Details is required"))
        doc_dict = {'resolution_details': doc.resolution_details,'status':doc.custom_ticket_status,'client_ticket': doc.custom_reference_ticket_id}      # {'status': 'Closed'}

    elif doc.custom_ticket_status == 'Replied':
        status ='Replied'		
        doc_dict = {'status': status, 'client_ticket': doc.custom_reference_ticket_id}      # {'status': 'Closed'}

    else:
        status = 'Closed'
        return
    previous = doc.get_doc_before_save()
    if(previous and doc.custom_ticket_status != previous.custom_ticket_status):
        try:
            doc.append("custom_ticket_timeline", {
                        "timestamp": frappe.utils.now_datetime().isoformat(),
                        "date": today(),
                        "status": status,
                        "note": f"Status changed from {previous.custom_ticket_status} to {status}",
                        "added_by": get_user_fullname(frappe.session.user)
                    })
            frappe.db.commit()
            timeline_entry = doc.custom_ticket_timeline[-1] if doc.custom_ticket_timeline else None
            if timeline_entry:
                sync_timeline_to_support_system(doc, timeline_entry=timeline_entry)
        except Exception as e:
            frappe.log_error(f"Timeline sync error:\n\n {str(e)}")
    
    headers = {
    "Authorization": f"token {doc.get_password('custom_reference_ticket_token')}"
    }
    frappe.log_error(f"\nHeaders: {headers}\nURL: {doc.custom_client_url}", "Debug Info")

    payload = {
        "doc": doc_dict  
    }
    api_url = f"{doc.custom_client_url}/api/method/genie.utils.support.set_status"

    response = requests.post(
        url=api_url,
        headers=headers,
        json=payload,
        timeout=10  
    )
    
@frappe.whitelist()
def set_status(doc):
	for d in frappe.get_all("HD Ticket",{'custom_reference_ticket_id': doc['custom_reference_ticket_id']}):
		hdTicket = frappe.get_doc("HD Ticket", d.name)

		hdTicket.custom_ticket_status = doc['status']
		if doc['status'] == 'Closed':
			hdTicket.feedback_text = doc.get('feedback_option')
			hdTicket.feedback_extra = doc.get('feedback_extra')
			hdTicket.feedback_rating = doc.get('rating')
		hdTicket.save()
            


def sync_timeline_to_support_system(doc = None, method = None, timeline_entry = None):
    session = requests.Session()
    try:
        
        headers = {
            "Authorization": f"token {doc.get_password('custom_reference_ticket_token')}"
        }
        data = {
            "doctype": "Ticket Timeline Entry",
            "timestamp": timeline_entry.timestamp,  
            "date": today(),
            "status": timeline_entry.status,
            "note": timeline_entry.note,
            "added_by": timeline_entry.added_by,
            "parent": doc.custom_reference_ticket_id,  # Should match client-side ticket name
            "parenttype": "Ticket Details",
            "parentfield": "ticket_timeline",
        }
        # response = session.post(self.custom_client_url, headers=headers, json=data)
        response = session.post(
            url = f"{doc.custom_client_url}/api/resource/Ticket Timeline Entry",
            headers=headers,
            json=data,
            timeout=10  
        )
        response.raise_for_status()  # Will raise HTTPError for bad responses
    except Exception as e:
        frappe.log_error(f"Timeline sync error: {str(e)}")

@frappe.whitelist(allow_guest=False)
def make_timeline_entry(**kwargs):
    data = frappe._dict(kwargs)

    # Validate required fields
    if not data.parent:
        frappe.throw("Parent ticket ID is required.")

    # Load the parent HD Ticket
    ticket = frappe.get_doc("HD Ticket", data.parent)
    # frappe.throw(f"Ticket: {ticket.name}")
    # Append a new entry to the timeline
    ticket.append("custom_ticket_timeline", {
        "timestamp": data.timestamp,
        "date": data.date,
        "status": data.status,
        "note": data.note,
        "added_by": data.added_by,
    })

    # Save with permission bypass if required
    ticket.save(ignore_permissions=True)

    return {"message": "Timeline entry synced successfully"}