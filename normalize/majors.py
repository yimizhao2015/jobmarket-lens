"""Majors (fields of study) named with a posting's degree requirement.

Only the phrase after a degree mention ("Bachelor's degree in Computer Science, Engineering, or a related
field") is read, and only in the required part of the posting. Each listed field is matched against a fixed
dictionary of broad fields; the first entry that matches wins, so specific fields come before general ones.
A field the dictionary lacks, or "a related field" on its own, is not counted.
"""
import re

from .parse import required_part

FIELDS = [
    ("Nursing", r"nursing|(?-i:\bBSN\b|\bADN\b|\bRN\b)"),
    ("Pharmacy", r"pharmacy|pharm\.?d"),
    ("Biomedical engineering", r"biomedical engineering|bioengineering"),
    ("Electrical and computer engineering", r"electric|electronic|computer engineering|(?-i:\bECE\b|\bEE\b)"),
    ("Mechanical and aerospace engineering", r"mechanical|mechatronic|aerospace|aeronautic"),
    ("Chemical and materials engineering", r"chemical engineering|material|metallurg|polymer"),
    ("Civil and construction engineering", r"civil|structural|construction|surveying"),
    ("Industrial and manufacturing engineering", r"industrial engineering|manufacturing|operations research|systems engineering"),
    ("Data science and analytics", r"data science|analytics|\bdata\b(?! processing)"),
    ("Computer science", r"computer science|(?-i:\bCS\b|\bAI\b)|software|artificial intelligence|machine learning|robotics|computing"),
    ("Information technology and systems", r"information technology|(?-i:\bIT\b|\bCIS\b)|data processing|information systems|\bmis\b|cyber|information security|"
                                           r"computer information|informatics"),
    ("Mathematics and statistics", r"math|statistic|actuar|quantitative|operations research"),
    ("Engineering (any field)", r"engineering"),
    ("Life sciences", r"biolog|life science|biochem|microbio|molecular|biotech|genetic|neuroscience|pharmacolog|immunolog|"
                      r"biomedical science|toxicolog"),
    ("Physical sciences", r"physics|chemistry|optics|geolog|geoscience|earth science|astronom"),
    ("Environmental and agricultural sciences", r"environment|agricultur|agronom|forestry|natural resource|horticult|animal science|"
                                                r"food science|ecolog"),
    ("Health and medicine", r"medic|health|clinical|dietetic|nutrition|kinesiolog|exercise science|physical therapy|respiratory|"
                            r"radiolog|sonograph|dental|veterinar|physician"),
    ("Accounting", r"accounting|accountancy"),
    ("Finance and economics", r"financ|economic|banking|real estate|insurance"),
    ("Supply chain and logistics", r"supply chain|logistic|procurement|purchasing|transportation"),
    ("Human resources", r"human resource|(?-i:\bHR\b)|labor relations|organizational (psych|develop|behavior)"),
    ("Marketing and communications", r"marketing|communication|journalism|public relations|advertising|media"),
    ("Law and criminal justice", r"\blaw\b|legal|\bj\.?d\.?\b|juris|paralegal|criminal|criminolog"),
    ("Business and management", r"business|management|\bmba\b|administration|commerce|entrepreneur"),
    ("Psychology and social sciences", r"psycholog|sociolog|social science|political science|social work|international relations|"
                                       r"anthropolog|public policy|counsel"),
    ("Education", r"education|teaching"),
    ("Humanities", r"english|liberal arts|humanities|history|philosoph|language|linguistic|literature"),
    ("Architecture and design", r"architect|design|fine art|graphic|\barts?\b"),
    ("Hospitality", r"hospitality|culinary|hotel|restaurant"),
    ("Science or technical field (general)", r"\bstem\b|science|scientific|technical|technology"),
]
_FIELDS = [(name, re.compile(rx, re.I)) for name, rx in FIELDS]
NAMES = [name for name, _ in FIELDS]

# A degree mention followed by "in" / "of" and the list of fields, up to the end of the sentence or clause.
_PHRASE = re.compile(
    r"(?:degree|bachelor'?s|master'?s|\bb\.?s\.?c?|\bm\.?s\.?c?|\bb\.?a\.?|\bm\.?a\.?|\bmba|ph\.?d\.?|doctorate|major(?:ing)?)"
    r"\s*(?:\([^)]{0,40}\)\s*)?(?:degree\s*)?(?:,\s*)?(?:ideally |preferably |required )?(?:in|of)\s+([^.;:\n<>]{3,200})", re.I)
# Where the field list ends: experience, a preference clause, or the next requirement.
_STOP = re.compile(r"\b(?:or equivalent|or related|or a related|or other related|or similar|and/or|plus|with|and \d|\d+\+? years|"
                   r"from an? |required|preferred|desired|is a plus|experience|or relevant)\b", re.I)
_SPLIT = re.compile(r",|/|\bor\b|\band\b|&", re.I)
_TAGS = re.compile(r"<[^>]+>")


def find_majors(text):
    """Broad fields of study named with the degree requirement, in dictionary order."""
    req = _TAGS.sub(" ", required_part(text or ""))
    found = set()
    for m in _PHRASE.finditer(req):
        phrase = m[1]
        stop = _STOP.search(phrase)
        if stop:
            phrase = phrase[:stop.start()]
        for seg in _SPLIT.split(phrase):
            seg = seg.strip(" -()'\"")
            if len(seg) < 2 or len(seg) > 60:
                continue
            for name, rx in _FIELDS:
                if rx.search(seg):
                    found.add(name)
                    break
    return [n for n in NAMES if n in found]
