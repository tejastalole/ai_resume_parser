frappe.ui.form.on("Resume Upload", {
	refresh(frm) {
		if (frm.doc.__islocal) return;

		frm.add_custom_button(__("Parse Resume"), () => parse_resume(frm), __("Actions"));

		if (frm.doc.parsed_data) {
			frm.add_custom_button(__("View Parsed Data"), () => {
				frappe.set_route("Form", "Parsed Resume Data", frm.doc.parsed_data);
			});
		}

		set_status_indicator(frm);
	},
});

function parse_resume(frm) {
	if (!frm.doc.resume_file) {
		frappe.msgprint(__("Please upload a resume file first."));
		return;
	}
	if (!frm.doc.applicant_name) {
		frappe.msgprint(__("Please enter Applicant Name first."));
		return;
	}

	frappe.confirm(
		__("Parse this resume and save all extracted data?"),
		() => {
			frappe.call({
				method: "ai_resume_parser.ai_resume_parser.doctype.resume_upload.resume_upload.parse_resume",
				args: { docname: frm.doc.name },
				freeze: true,
				freeze_message: __("Parsing resume..."),
				callback(r) {
					if (r.message && r.message.status === "success") {
						frappe.show_alert({
							message: r.message.message,
							indicator: "green",
						});
						frm.reload_doc();
					}
				},
			});
		}
	);
}

function set_status_indicator(frm) {
	const colors = {
		Draft: "grey",
		Parsing: "orange",
		Parsed: "green",
		Failed: "red",
	};
	if (frm.doc.status) {
		frm.dashboard.set_headline_alert(
			`<span class="indicator ${colors[frm.doc.status] || "blue"}">${frm.doc.status}</span>`
		);
	}
}
