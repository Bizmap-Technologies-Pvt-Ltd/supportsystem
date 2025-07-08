from email.utils import format_datetime
import json
import frappe
import requests
from frappe.utils import now_datetime, add_days
import re
from frappe.query_builder import DocType
from frappe.query_builder.functions import Concat_ws
import base64



@frappe.whitelist()
def received_comment(doc):	
	for d in frappe.get_all("Issue",{'custom_reference_ticket_id': doc['reference_name']}):
		issueticket = frappe.get_doc("Issue", d.name)
        # customer = frappe.db.get_value("Issue", issueticket.name, "customer")

		cmt = frappe.new_doc("Comment")
		cmt.comment_type = "Comment"
		cmt.reference_doctype = "Issue"
		cmt.reference_name = issueticket.name
		cmt.comment_email = doc['comment_email']
		cmt.comment_by = doc['comment_by']
		cmt.content = doc['content']+f"\n{doc['comment_by']} from {issueticket.customer}."
		cmt.custom_is_system_generated = 1

		frappe.logger().debug(f"Current User: {frappe.session.user}, Roles: {frappe.get_roles()}")
		cmt.save()

		frappe.db.set_value("Comment", cmt.name, "owner", doc['comment_by'])
		frappe.db.commit()
    
    
    
@frappe.whitelist(allow_guest=True)
def custom_new(doc=None, attachments=None):

    if isinstance(doc, str):
        doc = json.loads(doc)

    # frappe.throw("custom_new")
    doc["doctype"] = "Issue"
    # doc["via_customer_portal"] = bool(frappe.session.user)

    d = frappe.get_doc(doc)
    d.save(ignore_permissions=True)
    for file_data in attachments:
        if isinstance(file_data, dict) and file_data.get("file_url"):
            # frappe.throw('sdcs')
            file_url = file_data["file_url"]
            file_name = file_data.get("file_name", file_url.split("/")[-1])
            
            # Get the File document
            file_doc = frappe.get_doc("File", {"file_url": file_url})

            # Attach it to the Issue
            file_doc.attached_to_doctype = "Issue"
            file_doc.attached_to_name = d.name
            file_doc.save(ignore_permissions=True)

    # d.create_communication_via_contact(d.description, attachments)
    # frappe.delete_doc("Communication", {'reference_name': d.name})
    # frappe.db.commit()
    return d



@frappe.whitelist()
def trigger_n8n_webhook(title, description):
	# n8n Webhook URL
	webhook_url = "http://159.65.158.127:5678/webhook/get-issue"
	# Payload for n8n
	payload = {
		"title": title,
		"description": description
	}
	
	headers = {
        # "Authorization": "Bearer be355f6a4d1d3c5:a14859a0c933867"  # Replace with your actual API key
        "Authorization": "Bearer 5e03df551ab107a:51ea0fbb65e765b"  # Replace with your actual API key
    }
	# Send the data to the n8n webhook
	response = requests.post(webhook_url, headers=headers, json=payload)

	if response.ok:
		frappe.logger().info({
			"webhook_url": webhook_url,
			"payload": payload,
			"response": response.json()
		})
		return response.json().get("message", "Webhook triggered successfully!")
	else:
		# Log and throw an error if the response is not OK
		frappe.logger().error({
			"webhook_url": webhook_url,
			"payload": payload,
			"status_code": response.status_code,
			"response_text": response.text
		})
		frappe.throw(f"Failed to trigger n8n: {response.text}")

@frappe.whitelist()
def build_timeline_graph(docname):
    doc = frappe.get_doc("Issue", docname)

    timeline = sorted(doc.ticket_timeline, key=lambda x: x.timestamp)

    html = ""
    for row in timeline:
        html += f"""
        <div style="display:inline-block; text-align:center; margin:10px;">
            <div style="padding:6px 12px; border-radius:20px; background-color:{get_status_color(row.status)}; color:white;">
                {row.status}
            </div>
            <div style="font-size:12px; margin-top:4px;">
                {format_datetime(row.timestamp)}
            </div>
            <div style="font-size:12px; color:#888;">
                {row.added_by}
            </div>
        </div>
        <span style="font-size:20px;">➡️</span>
        """

    # remove last arrow
    if html.endswith("➡️</span>"):
        html = html.rsplit('<span', 1)[0]

    doc.timeline_graph = html
    doc.save()

def get_status_color(status):
    return {
        "Open": "#1E90FF",
        "Replied": "#FFD700",
        "Resolved": "#32CD32",
        "Closed": "#FF6347",
        "Re-Opened": "#A020F0"
    }.get(status, "#555")


def auto_close_ticket():
    # Find tickets in 'Open' status older than 5 days
    settings = frappe.get_cached_doc("Genie Settings")

    cutoff_date = add_days(now_datetime(), settings.close_ticket_after_days)

    tickets = frappe.get_all("Ticket Details",  # or your Doctype name
        filters={
            "status": "Open",
            "creation": ["<", cutoff_date]
        },
        fields=["name"]
    )
    
    for ticket in tickets:
        doc = frappe.get_doc("Ticket Details", ticket.name)
        doc.status = "Closed"
        doc.save(ignore_permissions=True)
        frappe.db.commit() 
        
@frappe.whitelist()
def send_details_to_client(doc=None, method=None):
    try:
            doc = json.loads(doc)
            session = requests.Session()
            status = doc.get('custom_ticket_status')
            resolution_details = doc.get('resolution_details')

            idoc = frappe.get_doc("Issue", doc.get('name')) 

            url = f"{idoc.custom_client_url}/api/resource/Ticket Details/{doc.get('custom_reference_ticket_id')}"
            headers = {
                "Authorization": f"token {idoc.get_password('custom_reference_ticket_token')}"
            }
            data = {
                "status": status,
                "resolution_details": resolution_details,
                "category": doc.get("custom_category")
            }

            response = requests.put(url, headers=headers, json=data)
            frappe.log_error(f"URL: {url}\nHEADERS: {headers}\nDATA: {data}\nResponse: {response}","PUT Data info")
 
    except Exception as e:
        frappe.log_error(f"set_status error:\n\n {str(e)}")

@frappe.whitelist()
def sync_timeline_to_support_system(doc):
    doc = json.loads(doc)
    idoc = frappe.get_doc("Issue", doc.get('name'))

    if(idoc and doc.get('custom_ticket_status') != idoc.custom_ticket_status):
        try:
            timeline_entry = idoc.get('custom_ticket_timeline')[-1] if idoc.get('custom_ticket_timeline') else None
            if timeline_entry:
                headers = {
                    "Authorization": f"token {idoc.get_password('custom_reference_ticket_token')}"
                }

                url = f"{idoc.custom_client_url}/api/resource/Ticket Timeline Entry"
                data = {
                    "parent": idoc.custom_reference_ticket_id,
                    "parenttype": "Ticket Details",
                    "parentfield": "ticket_timeline",
                    "date": frappe.utils.today(),       
                    "status": doc.get('custom_ticket_status'),
                    "notes": timeline_entry.notes,
                    "added_by": get_user_fullname(frappe.session.user),
                }
                frappe.log_error(f"URL: {url}\nHEADERS: {headers}\nDATA: {data}\nResponse: {response}","PUT Data info")
                response = requests.post(url, headers=headers, json=data)
        except Exception as e:
            frappe.log_error(f"timeline sync error:\n\n {str(e)}")

@frappe.whitelist(allow_guest=False)
def sync_attachment(file_name, attached_to_doctype, attached_to_name, content):
    import base64, os, frappe

    # Decode base64 content
    file_content = base64.b64decode(content)

    # Define public file path
    file_path = frappe.get_site_path("public", "files", file_name)

    # Write file to disk FIRST
    with open(file_path, "wb") as f:
        f.write(file_content)

    uploader_email = data["uploaded_by"]["email"]
	uploader_name = data["uploaded_by"]["full_name"]

    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": file_name,
        "attached_to_doctype": attached_to_doctype,
        "attached_to_name": attached_to_name,
        "file_url": f"/files/{file_name}",
        "is_private": 0,
        "decode": True,
		"attached_by": uploader_email
    })
    # Save after file is already on disk
    file_doc.save()

    return {"status": "success", "file_url": file_doc.file_url}


def get_user_fullname(user: str) -> str:
	user_doctype = DocType("User")
	return (
		frappe.get_value(
			user_doctype,	
			filters={"name": user},
			fieldname=Concat_ws(" ", user_doctype.first_name, user_doctype.last_name),
		)
		or ""
	)