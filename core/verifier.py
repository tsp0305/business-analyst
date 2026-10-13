import re
from typing import Any, List, Set, Dict

YEAR_MIN = 1900
YEAR_MAX = 2099

def extract_numbers_from_text(text: str) -> List[float]:
    """
    Extracts numerical values from freeform text while filtering out:
    - Dates (e.g., 2024-01-15, 01/15/2024, 2023-04)
    - Alphanumeric ID strings / codes (e.g., E1, EMP101, ord_994, v2)
    - Standalone 4-digit years (1900-2099)
    """
    if not text or not isinstance(text, str):
        return []

    # 1. Strip date patterns
    cleaned = re.sub(r'\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b', ' ', text)
    cleaned = re.sub(r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b', ' ', cleaned)
    cleaned = re.sub(r'\b\d{4}[-/]\d{1,2}\b', ' ', cleaned)

    # 2. Strip identifier tokens like E1, EMP102, order_55, cust_01, v2
    cleaned = re.sub(r'[A-Za-z_]+\d+|\d+[A-Za-z_]+', ' ', cleaned)

    # 3. Strip thousand-separator commas between digits (e.g. 120,000 -> 120000)
    cleaned = re.sub(r'(?<=\d),(?=\d)', '', cleaned)

    # 4. Find candidate numbers (supporting negative and decimal numbers, optional % or $)
    raw_tokens = re.findall(r'(?<![A-Za-z0-9_])-?\$?\b\d+(?:\.\d+)?%?(?![A-Za-z0-9_])', cleaned)
    numbers = []
    for token in raw_tokens:
        clean_token = token.replace('%', '').replace('$', '').strip()
        try:
            val = float(clean_token)
            # Filter out calendar years
            if val.is_integer() and YEAR_MIN <= int(val) <= YEAR_MAX:
                continue
            numbers.append(val)
        except ValueError:
            continue
    return numbers

def extract_numbers_from_evidence(data: Any) -> List[float]:
    """Recursively extract all numeric values from structured evidence."""
    nums = []
    if isinstance(data, (int, float)) and not isinstance(data, bool):
        nums.append(float(data))
    elif isinstance(data, dict):
        for v in data.values():
            nums.extend(extract_numbers_from_evidence(v))
    elif isinstance(data, (list, tuple, set)):
        for item in data:
            nums.extend(extract_numbers_from_evidence(item))
    elif isinstance(data, str):
        nums.extend(extract_numbers_from_text(data))
    return nums

def is_number_verified(num: float, evidence_nums: List[float], tolerance: float = 0.05) -> bool:
    """
    Verifies if a number is directly present in evidence or derived via:
    - Difference (e1 - e2 or e2 - e1)
    - Sum (e1 + e2)
    - Ratio (e1 / e2 or e1 / e2 * 100)
    - Percentage change ((e1 - e2) / e2 * 100)
    """
    if not evidence_nums:
        return False

    abs_num = abs(num)

    # 1. Exact match (with absolute and 0.5% relative tolerance)
    for en in evidence_nums:
        if abs(num - en) <= tolerance or (abs(en) > 0 and abs(num - en) / abs(en) <= 0.005):
            return True
        if abs(abs_num - abs(en)) <= tolerance:
            return True

    # 2. Pairwise derivations
    active_nums = evidence_nums[:200]
    n = len(active_nums)

    for i in range(n):
        en1 = active_nums[i]
        for j in range(n):
            if i == j:
                continue
            en2 = active_nums[j]

            # Difference
            diff = en1 - en2
            if abs(num - diff) <= tolerance or abs(abs_num - abs(diff)) <= tolerance:
                return True
            if abs(diff) > 0 and abs(num - diff) / abs(diff) <= 0.005:
                return True

            # Sum
            total = en1 + en2
            if abs(num - total) <= tolerance or abs(abs_num - abs(total)) <= tolerance:
                return True
            if abs(total) > 0 and abs(num - total) / abs(total) <= 0.005:
                return True

            # Ratio
            if abs(en2) > 1e-9:
                ratio = en1 / en2
                if abs(num - ratio) <= tolerance or abs(abs_num - abs(ratio)) <= tolerance:
                    return True
                if abs(num - ratio * 100) <= tolerance or abs(abs_num - abs(ratio * 100)) <= tolerance:
                    return True

            # Percentage change ((en1 - en2) / en2 * 100)
            if abs(en2) > 1e-9:
                pct = ((en1 - en2) / en2) * 100
                if abs(num - pct) <= tolerance or abs(abs_num - abs(pct)) <= tolerance:
                    return True
                frac = (en1 - en2) / en2
                if abs(num - frac) <= tolerance or abs(abs_num - abs(frac)) <= tolerance:
                    return True

    return False

def verify_answer(answer: dict, ledger) -> dict:
    errors = []

    if not isinstance(answer, dict):
        return {"verified": True, "errors": []}

    # Collect all cited evidence IDs
    all_cited_eids = set()
    findings = answer.get("findings", [])
    if isinstance(findings, list):
        for f in findings:
            if isinstance(f, dict):
                for eid in f.get("evidence_ids", []):
                    all_cited_eids.add(eid)

    # Top-level evidence_ids if present
    for eid in answer.get("evidence_ids", []):
        all_cited_eids.add(eid)

    # Find any inline cited E-ids like E1, E2 in text fields
    for field in ("summary", "quantified_impact", "root_cause", "recommendation"):
        val = answer.get(field)
        if isinstance(val, str):
            for eid in re.findall(r'\bE\d+\b', val):
                all_cited_eids.add(eid)

    # Verify findings individually against their cited evidence
    for f in findings:
        if not isinstance(f, dict):
            continue
        claim = f.get("claim", "")
        eids = f.get("evidence_ids", [])
        
        # Numbers can be provided in 'numbers' list or extracted from 'claim'
        nums = []
        if "numbers" in f and isinstance(f["numbers"], list):
            for n in f["numbers"]:
                try:
                    nums.append(float(n))
                except (ValueError, TypeError):
                    pass
        else:
            nums = extract_numbers_from_text(claim)

        # Gather evidence numbers for this finding
        f_evidence_nums = []
        for eid in eids:
            ev = ledger.get(eid)
            if not ev:
                errors.append(f"Evidence ID {eid} does not exist.")
                continue
            f_evidence_nums.extend(extract_numbers_from_evidence(ev.get("result")))

        if nums and not eids:
            errors.append(f"Finding '{claim[:50]}': numbers {nums} cited without evidence IDs.")
        elif nums and not f_evidence_nums and not any(f"Evidence ID {eid} does not exist" for eid in eids):
            errors.append(f"No numbers found in evidence {eids} for claim '{claim[:50]}'.")

        for num in nums:
            if num.is_integer() and YEAR_MIN <= int(num) <= YEAR_MAX:
                continue
            if not is_number_verified(num, f_evidence_nums):
                errors.append(f"Finding '{claim[:50]}': Number {num} cannot be verified against cited evidence {eids}.")

    # Gather pool of numbers from all cited evidence for checking top-level text fields
    global_evidence_nums = []
    if all_cited_eids:
        for eid in all_cited_eids:
            ev = ledger.get(eid)
            if ev:
                global_evidence_nums.extend(extract_numbers_from_evidence(ev.get("result")))
    elif hasattr(ledger, "evidence") and ledger.evidence:
        # Fallback to all ledger evidence if no specific IDs were cited
        for ev in ledger.evidence.values():
            global_evidence_nums.extend(extract_numbers_from_evidence(ev.get("result")))

    # Check narrative text fields: summary, quantified_impact, root_cause, recommendation
    text_fields = ["summary", "quantified_impact", "root_cause", "recommendation"]
    for field in text_fields:
        field_val = answer.get(field)
        if not field_val or not isinstance(field_val, str):
            continue

        field_nums = extract_numbers_from_text(field_val)
        for num in field_nums:
            if not is_number_verified(num, global_evidence_nums):
                errors.append(f"Field '{field}': Number {num} cannot be verified against cited evidence.")

    if errors:
        return {"verified": False, "errors": errors}
    return {"verified": True, "errors": []}

