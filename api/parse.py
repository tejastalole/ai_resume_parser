# Copyright (c) 2026, Tejas and contributors
# MIT License

import json
import os

import frappe
from frappe.utils import get_files_path
from frappe.utils.file_manager import get_file_path

from ai_resume_parser.parser.resume_parser import ResumeParser

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}
MAX_FILE_SIZE_MB = 10


def run_parse(docname: str) -> dict:
	"""Parse resume from Resume Upload and create/update Parsed Resume Data."""
	doc = frappe.get_doc("Resume Upload", docname)

	if not doc.resume_file:
		frappe.throw("Please attach a resume file before parsing.")

	if not doc.applicant_name:
		frappe.throw("Please enter Applicant Name before parsing.")

	doc.status = "Parsing"
	doc.error_message = ""
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	try:
		file_path = _get_resume_path(doc.resume_file)
		_validate_file(file_path)

		parser = ResumeParser(file_path)
		parsed = parser.parse()

		parsed_doc = _get_or_create_parsed_record(doc, parsed)
		parsed_doc.save(ignore_permissions=True)

		doc.status = "Parsed"
		doc.parsed_data = parsed_doc.name
		doc.error_message = ""
		doc.save(ignore_permissions=True)
		frappe.db.commit()

		return {
			"status": "success",
			"parsed_data": parsed_doc.name,
			"message": f"Resume parsed successfully. Data saved in {parsed_doc.name}",
		}

	except Exception as e:
		frappe.log_error(title="Resume Parse Failed", message=frappe.get_traceback())
		doc.reload()
		doc.status = "Failed"
		doc.error_message = str(e)[:500]
		doc.save(ignore_permissions=True)
		frappe.db.commit()
		frappe.throw(str(e))


def _get_resume_path(file_url: str) -> str:
	path = get_file_path(file_url)
	if path and os.path.exists(path):
		return path
	# fallback: files/ folder
	fname = file_url.split("/")[-1]
	alt = os.path.join(get_files_path(), fname)
	if os.path.exists(alt):
		return alt
	frappe.throw(f"Resume file not found: {file_url}")


def _validate_file(file_path: str) -> None:
	ext = os.path.splitext(file_path)[1].lower()
	if ext not in ALLOWED_EXTENSIONS:
		frappe.throw(f"Unsupported format {ext}. Allowed: PDF, DOCX, TXT")

	size_mb = os.path.getsize(file_path) / (1024 * 1024)
	if size_mb > MAX_FILE_SIZE_MB:
		frappe.throw(f"File too large ({size_mb:.1f} MB). Max {MAX_FILE_SIZE_MB} MB.")


def _get_or_create_parsed_record(upload_doc, parsed: dict):
	if upload_doc.parsed_data and frappe.db.exists("Parsed Resume Data", upload_doc.parsed_data):
		doc = frappe.get_doc("Parsed Resume Data", upload_doc.parsed_data)
	else:
		doc = frappe.new_doc("Parsed Resume Data")

	doc.applicant_name = upload_doc.applicant_name
	doc.resume_upload = upload_doc.name
	doc.resume_file = upload_doc.resume_file
	doc.full_name = parsed.get("full_name") or upload_doc.applicant_name
	doc.email = parsed.get("email")
	doc.phone = parsed.get("phone")
	gender = parsed.get("gender")
	doc.gender = gender if gender in ("Male", "Female", "Other") else ""
	doc.skills = parsed.get("skills")
	exp = parsed.get("experience_years")
	doc.experience_years = exp if exp else None
	doc.education = parsed.get("education")
	doc.current_company = parsed.get("current_company")
	doc.current_designation = parsed.get("current_designation")
	doc.linkedin_url = parsed.get("linkedin_url")
	doc.github_url = parsed.get("github_url")
	doc.portfolio_url = parsed.get("portfolio_url")
	doc.resume_text = parsed.get("resume_text")
	doc.parsed_json = parsed.get("parsed_json") or json.dumps(parsed, indent=2, default=str)

	return doc
