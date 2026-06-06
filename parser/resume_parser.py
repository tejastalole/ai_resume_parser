# Copyright (c) 2026, Tejas and contributors
# MIT License

import json
import os
import re
from datetime import datetime
from typing import Any

import frappe


class ResumeParser:
	"""Extract text and candidate fields from resume files."""

	EMAIL_RE = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+", re.I)
	PHONE_RE = re.compile(r"(?:\+91[\s-]?)?[6-9]\d{9}|(?:\+\d{1,3}[\s-]?)?\d{10,14}")
	# Only match explicit "Gender: Male" / "Sex: Female" — never guess; no M/F shorthand.
	GENDER_LABEL_RE = re.compile(r"(?<![a-z])(?:gender|sex)(?![a-z])", re.I)
	GENDER_VALUE_RE = re.compile(
		r"(?<![a-z])(?:gender|sex)(?![a-z])\s*"
		r"(?:[:\-–|]\s*|\s+)(male|female)\b",
		re.I,
	)
	LINKEDIN_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/in/[\w\-/]+", re.I)
	GITHUB_RE = re.compile(r"https?://(?:www\.)?github\.com/[\w\-/]+", re.I)
	URL_RE = re.compile(r"https?://[\w\.\-/]+", re.I)
	EXPERIENCE_HEADER_RE = re.compile(
		r"^\s*(?:(?:work\s+)?experience|professional\s+experience|employment(?:\s+history)?|"
		r"career\s+(?:history|summary)|internships?|work\s+history)\s*:?\s*$",
		re.I | re.M,
	)
	EXPERIENCE_STOP_RE = re.compile(
		r"^\s*(?:education|academic|skills|technical\s+skills|projects|certifications?|"
		r"achievements|summary|objective|personal|contact|references)\s*:?\s*$",
		re.I | re.M,
	)
	JOB_DATE_RANGE_RE = re.compile(
		r"(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*)?"
		r"((?:19|20)\d{2})\s*[-–—~to]+\s*"
		r"(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*)?"
		r"((?:19|20)\d{2}|present|current|now|ongoing|till\s+date)",
		re.I,
	)
	JOB_DATE_RANGE_SLASH_RE = re.compile(
		r"(?:\d{1,2}[/\-.])?((?:19|20)\d{2})\s*[-–—~to]+\s*"
		r"(?:(?:\d{1,2}[/\-.])?)?((?:19|20)\d{2}|present|current|now|ongoing)",
		re.I,
	)
	EDUCATION_HEADER_RE = re.compile(
		r"^\s*(education|academic(?:\s+background|\s+qualification)?|qualifications?|educational\s+background)\s*:?\s*$",
		re.I | re.M,
	)
	SECTION_STOP_RE = re.compile(
		r"^\s*(experience|work\s+experience|employment(?:\s+history)?|professional\s+experience|"
		r"skills|technical\s+skills|core\s+competencies|projects|certifications?|"
		r"achievements|summary|objective|personal\s+details|contact|references)\s*:?\s*$",
		re.I | re.M,
	)
	YEAR_RE = re.compile(
		r"(?:\(?(19|20)\d{2}\s*[-–—to]+\s*(?:19|20)\d{2}\)?|(?:19|20)\d{2}|"
		r"(?:passed|completed|graduated)\s*(?:in)?\s*:?\s*(19|20)\d{2})",
		re.I,
	)
	DEGREE_RE = re.compile(
		r"\b("
		r"B\.?\s*Tech(?:nology)?(?:\s*\([^)]+\))?|M\.?\s*Tech(?:nology)?(?:\s*\([^)]+\))?|"
		r"B\.?\s*E\.?(?:\s*\([^)]+\))?|M\.?\s*E\.?(?:\s*\([^)]+\))?|"
		r"B\.?\s*Sc(?:\.|\s*Science)?(?:\s*\([^)]+\))?|M\.?\s*Sc(?:\.|\s*Science)?(?:\s*\([^)]+\))?|"
		r"B\.?\s*Com(?:\.|\s*Commerce)?|M\.?\s*Com(?:\.|\s*Commerce)?|"
		r"\bB\.?\s*A\.?\b(?![a-z])|"
		r"\bM\.?\s*A\.?\b(?![a-z])|"
		r"BCA|MCA|MBA|BBA|MBBS|B\.?\s*Pharm|Ph\.?\s*D\.?|PGDM|PGDBM|"
		r"Bachelor(?:\'s)?\s+(?:of\s+)?(?:Engineer(?:ing)?|Technology|Science|Arts|Commerce|"
		r"Business(?:\s+Administration)?|Computer(?:\s+Applications?)?|Pharmacy|"
		r"Architecture|Law|Education)[^\n,;|]{0,50}|"
		r"Master(?:\'s)?\s+(?:of\s+)?(?:Technology|Engineering|Science|Arts|Commerce|"
		r"Business(?:\s+Administration)?|Computer(?:\s+Applications?)?|Pharmacy|"
		r"Architecture|Law|Education)[^\n,;|]{0,50}|"
		r"Diploma\s+(?:in\s+)?[^\n,;|]{3,55}|"
		r"HSC|SSC|XII(?:th)?|X(?:th)?|10\+2|12th|10th|"
		r"Intermediate|Higher\s+Secondary|Senior\s+Secondary|Secondary\s+School"
		r")\b",
		re.I,
	)
	INSTITUTION_RE = re.compile(
		r"\b([A-Z][\w\s&\.\-]{0,80}?(?:University|College|Institute|Campus|Polytechnic|"
		r"School|IIT\s+[\w\s]+|NIT\s+[\w\s]+|IIIT\s+[\w\s]+|BITS[\w\s]*|"
		r"VIT[\w\s]*|Anna\s+University|Delhi\s+University|IGNOU)"
		r"[\w\s&\.\-,]{0,40})\b",
		re.I,
	)
	INSTITUTION_LINE_RE = re.compile(
		r"^(.+?(?:College|University|Institute|Campus|Polytechnic|School))"
		r"([\w\s&\.\-,]{0,60})?\s*((?:19|20)\d{2}\s*[-–—]\s*(?:19|20)\d{2})\s*$",
		re.I,
	)
	BULLET_LINE_RE = re.compile(
		r"^[\-\•\*●○▪]\s*|^(?:graduated|participated|actively|developed|served|"
		r"completed|achieved|awarded)\b",
		re.I,
	)

	def __init__(self, file_path: str):
		self.file_path = file_path
		self.text = ""
		self.ext = os.path.splitext(file_path)[1].lower()

	def parse(self) -> dict[str, Any]:
		self.text = self.extract_text()
		if not self.text or not self.text.strip():
			frappe.throw("Could not extract any text from the resume file.")

		data = {
			"resume_text": self.text.strip(),
			"email": self.extract_email(),
			"phone": self.extract_phone(),
			"full_name": self.extract_name(),
			"gender": self.extract_gender(),
			"skills": self.extract_skills(),
			"experience_years": self.extract_experience(),
			"education": self.extract_education(),
			"current_company": self.extract_current_company(),
			"current_designation": self.extract_current_designation(),
			"linkedin_url": self.extract_linkedin(),
			"github_url": self.extract_github(),
			"portfolio_url": self.extract_portfolio(),
		}
		data["parsed_json"] = json.dumps(data, indent=2, default=str)
		return data

	def extract_text(self) -> str:
		if self.ext == ".pdf":
			return self._extract_pdf()
		if self.ext in (".docx", ".doc"):
			return self._extract_docx()
		if self.ext == ".txt":
			return self._read_txt()
		frappe.throw(f"Unsupported file format: {self.ext}. Use PDF, DOCX, or TXT.")

	def _extract_pdf(self) -> str:
		text_parts = []
		try:
			import pdfplumber

			with pdfplumber.open(self.file_path) as pdf:
				for page in pdf.pages:
					page_text = page.extract_text()
					if page_text:
						text_parts.append(page_text)
		except Exception:
			pass

		if text_parts:
			return "\n".join(text_parts)

		try:
			import PyPDF2

			with open(self.file_path, "rb") as f:
				reader = PyPDF2.PdfReader(f)
				for page in reader.pages:
					page_text = page.extract_text()
					if page_text:
						text_parts.append(page_text)
		except Exception as e:
			frappe.throw(f"Failed to read PDF: {e}")

		return "\n".join(text_parts)

	def _extract_docx(self) -> str:
		try:
			import docx
		except ImportError as e:
			frappe.throw("python-docx is required. Run: pip install python-docx")

		doc = docx.Document(self.file_path)
		return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

	def _read_txt(self) -> str:
		with open(self.file_path, encoding="utf-8", errors="ignore") as f:
			return f.read()

	def extract_email(self) -> str | None:
		m = self.EMAIL_RE.search(self.text)
		return m.group(0) if m else None

	def extract_phone(self) -> str | None:
		m = self.PHONE_RE.search(self.text)
		return m.group(0).strip() if m else None

	def extract_gender(self) -> str | None:
		"""Return Male/Female only if resume has explicit Gender/Sex label; else None."""
		match = self.GENDER_VALUE_RE.search(self.text)
		if match:
			return self._normalize_gender(match.group(1))

		for line in self.text.splitlines()[:40]:
			line = line.strip()
			if not line or len(line) > 200:
				continue
			if not self.GENDER_LABEL_RE.search(line):
				continue
			label_match = self.GENDER_VALUE_RE.search(line)
			if label_match:
				return self._normalize_gender(label_match.group(1))

		return None

	@staticmethod
	def _normalize_gender(value: str) -> str | None:
		val = (value or "").lower().strip()
		if val == "male":
			return "Male"
		if val == "female":
			return "Female"
		return None

	def extract_name(self) -> str | None:
		lines = [ln.strip() for ln in self.text.splitlines() if ln.strip()]
		for line in lines[:8]:
			if self.EMAIL_RE.search(line) or self.PHONE_RE.search(line):
				continue
			if len(line) < 60 and 2 <= len(line.split()) <= 5:
				if not re.search(r"resume|curriculum|cv|objective|summary", line, re.I):
					return line
		return lines[0] if lines else None

	def extract_skills(self) -> str | None:
		keywords = [
			"python", "java", "javascript", "react", "angular", "vue", "node",
			"sql", "mysql", "postgresql", "mongodb", "aws", "azure", "docker",
			"kubernetes", "django", "flask", "frappe", "erpnext", "excel",
			"communication", "leadership", "project management", "html", "css",
		]
		found = []
		lower = self.text.lower()
		for kw in keywords:
			if kw in lower:
				found.append(kw.title() if kw.islower() else kw)
		return ", ".join(dict.fromkeys(found)) if found else None

	def extract_experience(self) -> float | None:
		explicit = self._extract_explicit_experience_years()
		from_jobs = self._extract_experience_from_job_dates()

		if explicit is not None and from_jobs is not None:
			return round(max(explicit, from_jobs), 2)
		if explicit is not None:
			return round(explicit, 2)
		if from_jobs is not None:
			return round(from_jobs, 2)
		return None

	def _extract_explicit_experience_years(self) -> float | None:
		patterns = [
			r"(?:total\s+)?(?:work\s+)?experience\s*[:\-–|]\s*(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)",
			r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:professional\s+)?(?:work\s+)?(?:experience|exp)\b",
			r"experience\s*[:\-–|]\s*(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)",
			r"(\d+(?:\.\d+)?)\s*(?:years?|yrs?)\s+(?:of\s+)?(?:work\s+)?experience\b",
			r"(\d+(?:\.\d+)?)\s*\+\s*years?\s+(?:of\s+)?experience\b",
		]
		for pattern in patterns:
			match = re.search(pattern, self.text, re.I)
			if match:
				return float(match.group(1))
		return None

	def _extract_experience_section(self) -> str | None:
		match = self.EXPERIENCE_HEADER_RE.search(self.text)
		if not match:
			return None
		start = match.end()
		stop = self.EXPERIENCE_STOP_RE.search(self.text, start)
		end = stop.start() if stop else len(self.text)
		block = self.text[start:end].strip()
		return block if len(block) > 10 else None

	def _extract_experience_from_job_dates(self) -> float | None:
		section = self._extract_experience_section()
		if section:
			intervals = self._parse_job_date_intervals(section)
			if intervals:
				return self._total_years_from_intervals(intervals)

		intervals = []
		for line in self.text.splitlines():
			line = line.strip()
			if not line or len(line) < 8:
				continue
			if re.search(
				r"\b(?:university|college|institute|campus|bachelor|diploma|b\.?tech|m\.?tech|"
				r"education|school|hsc|ssc|cgpa|%\s*in\s+diploma)\b",
				line,
				re.I,
			):
				continue
			intervals.extend(self._parse_job_date_intervals(line))

		if intervals:
			return self._total_years_from_intervals(intervals)
		return None

	def _parse_job_date_intervals(self, text: str) -> list[tuple[int, int]]:
		intervals = []
		for pattern in (self.JOB_DATE_RANGE_RE, self.JOB_DATE_RANGE_SLASH_RE):
			for match in pattern.finditer(text):
				start = int(match.group(1))
				end = self._parse_end_year(match.group(2))
				if start and end and end >= start:
					intervals.append((start, end))
		return intervals

	@staticmethod
	def _parse_end_year(token: str) -> int | None:
		if not token:
			return None
		val = token.lower().strip()
		if val in ("present", "current", "now", "ongoing", "till date"):
			return datetime.now().year
		year_match = re.search(r"(19|20)\d{2}", val)
		return int(year_match.group(0)) if year_match else None

	@staticmethod
	def _total_years_from_intervals(intervals: list[tuple[int, int]]) -> float:
		intervals.sort(key=lambda x: x[0])
		merged: list[tuple[int, int]] = []
		for start, end in intervals:
			if merged and start <= merged[-1][1]:
				merged[-1] = (merged[-1][0], max(merged[-1][1], end))
			else:
				merged.append((start, end))

		total = 0.0
		for start, end in merged:
			years = end - start
			total += max(years, 0.5) if years == 0 else float(years)
		return total

	def extract_education(self) -> str | None:
		entries = []
		section_text = self._extract_education_section()

		if section_text:
			entries.extend(self._parse_education_lines(section_text.splitlines()))

		if not entries:
			source_lines = section_text.splitlines() if section_text else self.text.splitlines()
			for group in self._group_education_lines(source_lines):
				entry = self._build_college_first_entry(group)
				if entry:
					entries.append(entry)

		entries = self._dedupe_education_entries(entries)
		if not entries:
			return None
		return "\n".join(entries[:6])

	def _extract_education_section(self) -> str | None:
		match = self.EDUCATION_HEADER_RE.search(self.text)
		if not match:
			return None

		start = match.end()
		stop = self.SECTION_STOP_RE.search(self.text, start)
		end = stop.start() if stop else len(self.text)
		block = self.text[start:end].strip()
		return block if len(block) > 10 else None

	def _parse_education_lines(self, lines: list[str]) -> list[str]:
		entries = []
		cleaned = []
		for raw in lines:
			line = re.sub(r"\s+", " ", raw.strip())
			if not line or len(line) < 4:
				continue
			if self.SECTION_STOP_RE.match(line):
				break
			cleaned.append(line)

		for group in self._group_education_lines(cleaned):
			entry = self._build_college_first_entry(group)
			if entry:
				entries.append(entry)
		return entries

	def _is_bullet_line(self, line: str) -> bool:
		return bool(self.BULLET_LINE_RE.match(line))

	def _is_institution_line(self, line: str) -> bool:
		if not self.YEAR_RE.search(line):
			return False
		return bool(
			self.INSTITUTION_LINE_RE.match(line)
			or re.search(
				r"(?:college|university|institute|campus|polytechnic|school)",
				line,
				re.I,
			)
		)

	def _is_degree_line(self, line: str) -> bool:
		if self._is_bullet_line(line) or self._is_institution_line(line):
			return False
		return bool(self._extract_degree_phrase(line))

	def _build_college_first_entry(self, lines: list[str]) -> str | None:
		if not lines:
			return None

		inst_line = lines[0]
		degree_line = lines[1] if len(lines) > 1 else None

		year_match = self.YEAR_RE.search(inst_line)
		year_str = year_match.group(0).strip() if year_match else None
		if year_str:
			year_str = year_str.strip("()")

		institution = inst_line
		if year_match:
			institution = inst_line[: year_match.start()].strip(" ,-|")
		institution = re.sub(r"\s+", " ", institution).strip()

		degree = None
		if degree_line:
			degree = self._extract_degree_phrase(degree_line) or degree_line.strip()

		grade = self._extract_grade_from_text(" ".join(lines))

		parts = []
		if degree:
			parts.append(degree)
		if institution:
			parts.append(institution)
		if not parts:
			return None

		result = " - ".join(parts)
		if grade:
			result = f"{result} ({grade})"
		elif year_str:
			result = f"{result} ({year_str})"
		return result

	def _extract_grade_from_text(self, text: str) -> str | None:
		cgpa = re.search(r"(\d+\.\d{1,2})\s*CGPA", text, re.I)
		if cgpa:
			return f"CGPA {cgpa.group(1)}"
		percent = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", text)
		if percent:
			return f"{percent.group(1)}%"
		return None

	def _group_education_lines(self, lines: list[str]) -> list[list[str]]:
		groups: list[list[str]] = []
		current: list[str] = []
		for raw in lines:
			line = re.sub(r"\s+", " ", raw.strip())
			if not line or len(line) < 4:
				continue
			if self._is_institution_line(line):
				if current:
					groups.append(current)
				current = [line]
			elif current and (self._is_degree_line(line) or self._is_bullet_line(line)):
				current.append(line)
			elif self._is_degree_line(line) and not current:
				current = [line]
		if current:
			groups.append(current)
		return groups

	def _dedupe_education_entries(self, entries: list[str]) -> list[str]:
		unique = []
		for entry in entries:
			entry = entry.strip()
			if not entry or len(entry) < 8:
				continue
			norm = re.sub(r"\s+", " ", entry.lower())
			if any(norm in u.lower() or u.lower() in norm for u in unique):
				continue
			unique.append(entry)
		return unique

	def _build_education_entry(self, text_or_lines: str | list[str]) -> str | None:
		if isinstance(text_or_lines, list):
			lines = [re.sub(r"\s+", " ", ln).strip() for ln in text_or_lines if ln.strip()]
			if not lines:
				return None
			degree_line = next((ln for ln in lines if self._extract_degree_phrase(ln)), lines[0])
			degree = self._extract_degree_phrase(degree_line)
			year_line = next((ln for ln in lines if self.YEAR_RE.search(ln)), None)
			inst_lines = [
				ln
				for ln in lines
				if ln != degree_line
				and ln != year_line
				and not self._extract_degree_phrase(ln)
			]
			year_str = None
			if year_line:
				ym = self.YEAR_RE.search(year_line)
				if ym:
					year_str = ym.group(0).strip().strip("()")
					if not re.search(r"(19|20)\d{2}", year_str):
						year_str = None
			institution = None
			for ln in inst_lines:
				im = self.INSTITUTION_RE.search(ln)
				if im:
					institution = im.group(0).strip()
					city = re.search(r",\s*([A-Za-z\s]{2,30})$", ln)
					if city:
						city_name = city.group(1).strip()
						if city_name.lower() not in institution.lower():
							institution = f"{institution}, {city_name}"
					break
				elif len(ln) > 4:
					institution = ln
			parts = [p for p in [degree, institution] if p]
			result = " - ".join(parts) if parts else lines[0][:200]
			if year_str:
				result = f"{result} ({year_str})"
			return result

		text = re.sub(r"\s+", " ", str(text_or_lines)).strip()
		if not text:
			return None

		degree = self._extract_degree_phrase(text)
		if not degree and not self.INSTITUTION_RE.search(text):
			return None

		remainder = text.replace(degree, "", 1) if degree else text
		year_match = self.YEAR_RE.search(remainder) or self.YEAR_RE.search(text)
		year_str = None
		if year_match:
			year_str = year_match.group(0).strip().strip("()")
			remainder = remainder.replace(year_match.group(0), "")
			if not re.search(r"(19|20)\d{2}", year_str):
				year_str = None

		institution = None
		inst_match = self.INSTITUTION_RE.search(remainder)
		if inst_match:
			institution = inst_match.group(0).strip().strip(" ,-|")
			city = re.search(r",\s*([A-Za-z\s]{2,30})$", remainder)
			if city:
				city_name = city.group(1).strip()
				if city_name.lower() not in institution.lower():
					institution = f"{institution}, {city_name}"
		else:
			remainder = re.sub(r"^[\s,\.\-]+|[\s,\.\-]+$", "", remainder)
			if remainder and 4 < len(remainder) < 100 and not self.DEGREE_RE.match(remainder):
				institution = remainder

		parts = [p for p in [degree, institution] if p]
		result = " - ".join(parts) if parts else text[:200]
		if year_str:
			result = f"{result} ({year_str})"
		return result

	def _extract_degree_phrase(self, text: str) -> str | None:
		if self._is_bullet_line(text):
			return None

		patterns = [
			r"\bBachelor(?:'s)?\s+of\s+Engineer(?:ing)?\s*[–\-]\s*[\w\s&\.\-,]+",
			r"\bBachelor(?:'s)?\s+(?:of\s+)?(?:Engineering|Technology|Science|Arts|Commerce|"
			r"Business(?:\s+Administration)?|Computer(?:\s+Applications)?)"
			r"(?:\s*[–\-]\s*[\w\s&\.\-,]+)?",
			r"\bMaster(?:'s)?\s+(?:of\s+)?(?:Engineering|Technology|Science|Arts|Commerce|"
			r"Business(?:\s+Administration)?|Computer(?:\s+Applications)?|Data\s+Science)"
			r"(?:\s*[–\-]\s*[\w\s&\.\-,]+)?",
			r"\bDiploma\s*[–\-]\s*[\w\s&\.\-,]+",
			r"\bDiploma\s+in\s+[\w\s&\.\-,]+",
			r"\bB\.?\s*Tech(?:nology)?(?:\s+in\s+[\w\s&\.\-,]+)?",
			r"\bM\.?\s*Tech(?:nology)?(?:\s+in\s+[\w\s&\.\-,]+)?",
			r"\bM\.?\s*Sc\.?\s+[\w\s&\.\-,]+",
			r"\bB\.?\s*Sc\.?\s+[\w\s&\.\-,]+",
			r"\b(?:B\.?\s*E\.?|M\.?\s*E\.?|B\.?\s*Com\.?|M\.?\s*Com\.?)(?:\s+in\s+[\w\s&\.\-,]+)?",
			r"\b(?:BCA|MCA|MBA|BBA|Ph\.?\s*D\.?|PGDM)(?:\s+in\s+[\w\s&\.\-,]+)?",
			r"\b(?:HSC|SSC|10\+2|12th|10th|Intermediate)\b",
		]
		for pat in patterns:
			m = re.search(pat, text, re.I)
			if m:
				return re.sub(r"\s+", " ", m.group(0).strip())

		m = self.DEGREE_RE.search(text)
		if m:
			val = m.group(0).strip()
			if len(val) > 3 and val.lower() not in ("ba", "ma", "be", "me"):
				return val
			if len(val) > 4:
				return val
		return None

	def extract_current_company(self) -> str | None:
		m = re.search(
			r"(?:current(?:ly)?\s+at|working\s+at|employer)\s*[:\-]?\s*([A-Za-z0-9\s&\.\-]{2,60})",
			self.text,
			re.I,
		)
		return m.group(1).strip() if m else None

	def extract_current_designation(self) -> str | None:
		m = re.search(
			r"(?:designation|position|job\s+title|title)\s*[:\-]\s*([A-Za-z0-9\s&\.\-/]{3,60})",
			self.text,
			re.I,
		)
		if m:
			val = m.group(1).strip()
			if len(val.split()) >= 2 and not re.search(r"^(based|access|with|the)\b", val, re.I):
				return val
		return None

	def extract_linkedin(self) -> str | None:
		m = self.LINKEDIN_RE.search(self.text)
		return m.group(0) if m else None

	def extract_github(self) -> str | None:
		m = self.GITHUB_RE.search(self.text)
		return m.group(0) if m else None

	def extract_portfolio(self) -> str | None:
		for m in self.URL_RE.finditer(self.text):
			url = m.group(0)
			if "linkedin" not in url.lower() and "github" not in url.lower():
				return url
		return None
