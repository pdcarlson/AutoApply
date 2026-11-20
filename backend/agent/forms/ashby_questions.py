"""Turns an Ashby job posting's application form into FormFields."""
from agent.forms.form_field import FieldKind, FormField

# Ashby field types the agent can fill. Others (scores, education history) are left for the
# person.
KINDS = {
    "String": FieldKind.TEXT,
    "Email": FieldKind.TEXT,
    "Phone": FieldKind.TEXT,
    "Number": FieldKind.TEXT,
    "Url": FieldKind.TEXT,
    "LongText": FieldKind.TEXTAREA,
    "File": FieldKind.FILE,
    "Boolean": FieldKind.SELECT,
    "ValueSelect": FieldKind.SELECT,
    "MultiValueSelect": FieldKind.MULTI_SELECT,
    "Location": FieldKind.LOCATION,
    "Date": FieldKind.DATE,
}
PROFILE_FIELDS = {
    "_systemfield_name": "full_name",
    "_systemfield_email": "email",
    "_systemfield_phone": "phone",
    "_systemfield_resume": "resume_path",
    "_systemfield_location": "location",
}


def fields_from_api(posting: dict) -> list[FormField]:
    """Turn an Ashby job posting's application form into FormFields."""
    fields = []
    for section in (posting.get("applicationForm") or {}).get("sections", []):
        for entry in section.get("fieldEntries", []):
            item = entry.get("field") or {}
            kind = KINDS.get(item.get("type"))
            if entry.get("isHidden") or item.get("isDeactivated") or kind is None:
                continue
            fields.append(_form_field(entry, item, kind))
    return fields


def _form_field(entry: dict, item: dict, kind: FieldKind) -> FormField:
    """Return the FormField for one entry of the form and the field it holds."""
    if item["type"] == "Boolean":
        options = ["Yes", "No"]
    else:
        options = [value["label"] for value in item.get("selectableValues") or []]
    path = item["path"]
    profile_key = PROFILE_FIELDS.get(path, "phone" if item["type"] == "Phone" else "")
    if item.get("locationTypes") == ["Country"]:
        # A location box that only lists countries, like ElevenLabs' "Location":
        # it's a search-and-pick list, answered with the profile's country
        kind, profile_key = FieldKind.SELECT, "country"
    return FormField(
        key=path,
        label=item.get("title", "").strip(),
        kind=kind,
        required=bool(entry.get("isRequired")),
        options=options,
        profile_key=profile_key,
    )
