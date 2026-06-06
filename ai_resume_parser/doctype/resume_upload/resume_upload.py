# Copyright (c) 2026, Tejas and contributors
# MIT License

import frappe
from frappe.model.document import Document


class ResumeUpload(Document):
	pass


@frappe.whitelist()
def parse_resume(docname: str):
	"""Parse resume and save all data into Parsed Resume Data."""
	from ai_resume_parser.api.parse import run_parse

	return run_parse(docname)
