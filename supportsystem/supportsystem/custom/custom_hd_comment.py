import frappe
import requests

import json

@frappe.whitelist()
def after_insert(doc, method):
	if doc.reference_doctype == "Issue":
		if doc.custom_is_system_generated == 0:
			admin_comment(doc)

def admin_comment(doc):
	ticket = frappe.get_doc("Issue",doc.reference_name)

	headers = {
		"Authorization": f"token {ticket.get_password('custom_reference_ticket_token')}"
	}
	if isinstance(doc, str):
		doc = frappe.get_doc("Comment",doc)
	doc_dict = doc.as_dict()
	doc_dict['client_ticket'] = ticket.custom_reference_ticket_id
	
	frappe.log_error(f"Settings: {ticket.as_dict()}\nHeaders: {headers}\nURL: {ticket.custom_client_url}", "Debug Info")

	# Prepare payload
	payload = {
		"doc": doc_dict  # Assuming `doc` is correctly structured as required by the API
	}

	api_url = f"{ticket.custom_client_url}/api/method/genie.utils.support.received_host_comment"

	# Make the POST request
	response = requests.post(
		url=api_url,
		headers=headers,
		json=payload,
		timeout=10  
	)