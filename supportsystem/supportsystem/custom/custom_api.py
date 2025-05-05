from email.utils import format_datetime
import json
import frappe
import requests
from frappe.utils import now_datetime, add_days



@frappe.whitelist()
def received_comment(doc):	
	for d in frappe.get_all("Issue",{'custom_reference_ticket_id': doc['reference_name']}):
		issueticket = frappe.get_doc("Issue", d.name)

		cmt = frappe.new_doc("Comment")
		cmt.comment_type = "Comment"
		cmt.reference_doctype = "Issue"
		cmt.reference_name = issueticket.name
		cmt.comment_email = doc['comment_email']
		cmt.comment_by = doc['comment_by']
		cmt.content = doc['content']
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
    doc["via_customer_portal"] = bool(frappe.session.user)

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
    return d



@frappe.whitelist()
def trigger_n8n_webhook(title, description):
	# n8n Webhook URL
	webhook_url = "http://localhost:5678/webhook/get-issue"
	# Payload for n8n
	payload = {
		"title": title,
		"description": description
	}
	
	headers = {
        # "Authorization": "Bearer be355f6a4d1d3c5:a14859a0c933867"  # Replace with your actual API key
        "Authorization": "Bearer be355f6a4d1d3c5:a14859a0c933867"  # Replace with your actual API key
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