"""Regular expressions shared by the resume readers."""
import re

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE_RE = re.compile(r"(?:\+1[\s.-]?)?\(?\d{3}\)?[\s.-]{0,2}\d{3}[\s.-]{0,2}\d{4}(?!\d)")
URL_RE = re.compile(
    r"(?:https?://|www\.)[^\s|,;]+"
    r"|(?<![\w@.])(?:[\w-]+\.)+(?:com|io|dev|me|net|org|app|ai|co|us|edu|sh|design|studio|tech"
    r"|page|site|xyz|info)(?:/[^\s|,;\"]*)?(?![\w.])",
    re.I)
GPA_RE = re.compile(r"GPA:?\s*([0-4]\.\d+)", re.I)
SCHOOL_RE = re.compile(r"\b(?:Universit(?:y|é|ät|eit|ad|à|e)|College|Institute|School|Academy"
                       r"|Polytechnic|Conservatory|Seminary|ETH)\b")
_DEGREE_OF = (r"(?:\s+of\s+(?:Applied\s+Science|Science|Arts|Fine\s+Arts|Engineering"
              r"|Business\s+Administration|Accountancy|Public\s+(?:Policy|Health|Administration)"
              r"|Education|Laws|Philosophy|Architecture|Music|Social\s+Work|Nursing|Technology))?")
DEGREE_RE = re.compile(
    r"(?<![A-Za-z])(?:"
    # "Master's", "Master of Science" or "Masters in" — not a bare "Master" ("Master Black Belt")
    rf"(?:Bachelor|Master|Associate|Doctor)(?:['’]s{_DEGREE_OF}|s?{_DEGREE_OF[:-1]}"
    r"|s?(?=\s+(?:in|of|degree)\b))"
    r"|Graduate\s+Certificate|Ph\.?\s?D\.?|[BM]\.?\s?Arch\.?|B\.?Sc\.?|M\.?Sc\.?|M\.?B\.?A\.?"
    r"|M\.?P\.?[PAH]\.?|M\.?S\.?W\.?|M\.?Ed\.?|Ed\.?D\.?|J\.D\.|M\.D\.|B\.?S\.?N\.?|M\.?S\.?N\.?"
    r"|B\.?B\.?A\.?|[BM]\.?Eng\.?|M\.A\.|B\.?S\.?|B\.?A\.?|M\.?S\.?"
    r")(?![A-Za-z])")
BULLET_RE = re.compile(r"^\s*[•●▪◦‣∙·*\-–✓✔➢►▶→◆■□○❖➤]\s*")
COLUMNS_RE = re.compile(r"\s{3,}")
SEGMENT_RE = re.compile(r"\s*[|•·◆◇▪■●⋅✉☎⌂📍📞🔗]\s*|\s{3,}|\s+/\s+")
PROJECT_RE = re.compile(r"^(?P<name>[^()]+?)\s+[-–—]\s+(?P<rest>.+?)\s*\((?P<tech>[^)]+)\)\s*$")
LABEL_RE = re.compile(r"^(?P<label>[^:]{1,40}):\s*(?P<body>.*)$", re.S)
SKILL_PREFIX_RE = re.compile(r"^[A-Za-z][\w /&+-]{0,30}:\s*")
NAME_WORD_RE = re.compile(r"^[A-Z][A-Za-z.'’-]*$")
# "Title: Program Analyst", "Dates: 03/2021 – Present" in a role's head lines
LABELED_RE = re.compile(r"^(?P<label>[A-Z][A-Za-z /&-]{1,24}):\s*(?P<value>.*)$")
# Splits a head line into its parts: "Title — Org · City, ST", "Title @ Org", "Org  |  Title"
PART_SPLIT_RE = re.compile(r"\s+[–—|·@•◆]\s+|\s+-\s+|\s{2,}")
# A line that ends on one of these words (or a comma) runs on into the next line
DANGLING_RE = re.compile(r"(?:[,;&/]|\b(?:and|or|of|for|to|with|by|in|on|at|the|a|an|as|"
                         r"from|into|via|using|including))\s*$", re.I)
SENTENCE_END_RE = re.compile(r"[.!?;:)]\s*$")
# "Inc." or "P.E." at the end of a line doesn't end a sentence
ABBREV_END_RE = re.compile(r"(?:\b[A-Z][A-Za-z]{0,3}\.|(?:[A-Z]\.){2,})$")
ADDRESS_RE = re.compile(r"^\d+\s+\w.*\b(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr"
                        r"|Lane|Ln|Way|Suite|NE|NW|SE|SW)\b", re.I)
