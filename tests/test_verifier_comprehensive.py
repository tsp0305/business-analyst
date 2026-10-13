import pytest
from core.evidence import EvidenceLedger
from core.verifier import verify_answer, extract_numbers_from_text, is_number_verified

def test_extract_numbers_filtering():
    # Dates, years, and IDs should be filtered out
    text = (
        "In 2024, order E1 and employee EMP102 processed 500 orders on 2023-05-12. "
        "Revenue increased by 15.5% with total value $120000.50 and lost -25.0."
    )
    nums = extract_numbers_from_text(text)
    # 2024 (year), E1 (id), EMP102 (id), 2023-05-12 (date) must be excluded
    # 500, 15.5, 120000.5, -25.0 must be extracted
    assert 2024 not in nums
    assert 2023 not in nums
    assert 1 not in nums # from E1
    assert 102 not in nums # from EMP102
    assert 500.0 in nums
    assert 15.5 in nums
    assert 120000.5 in nums
    assert -25.0 in nums

def test_is_number_verified_derivations():
    ev_nums = [100.0, 20.0]

    # Exact
    assert is_number_verified(100.0, ev_nums)
    assert is_number_verified(20.0, ev_nums)

    # Difference: 100 - 20 = 80
    assert is_number_verified(80.0, ev_nums)
    assert is_number_verified(-80.0, ev_nums)

    # Sum: 100 + 20 = 120
    assert is_number_verified(120.0, ev_nums)

    # Ratio: 100 / 20 = 5 (and ratio as % = 500)
    assert is_number_verified(5.0, ev_nums)
    assert is_number_verified(500.0, ev_nums)

    # Percentage change: (20 - 100)/100 * 100 = -80% or (100 - 20)/20 * 100 = 400%
    assert is_number_verified(400.0, ev_nums)
    assert is_number_verified(-80.0, ev_nums)

    # Fabricated / unverified
    assert not is_number_verified(999.0, ev_nums)
    assert not is_number_verified(37.5, ev_nums)

def test_verifier_happy_comprehensive():
    ledger = EvidenceLedger()
    eid = ledger.add("compute_kpi", {"metric": "revenue"}, {"value": 250000.0, "prior": 200000.0})
    
    ans = {
        "summary": "Revenue was 250000 in 2024.",
        "findings": [
            {
                "claim": "Revenue grew by 25.0% compared to prior 200000",
                "numbers": [250000.0, 25.0],
                "evidence_ids": [eid]
            }
        ],
        "quantified_impact": "Total gain of 50000 across period",
        "root_cause": "Increased demand in 2023",
        "recommendation": "Maintain strategy"
    }
    
    res = verify_answer(ans, ledger)
    assert res["verified"]
    assert len(res["errors"]) == 0

def test_verifier_fabricated_in_findings():
    ledger = EvidenceLedger()
    eid = ledger.add("compute_kpi", {}, {"value": 50.0})

    ans = {
        "findings": [
            {
                "claim": "Revenue reached 9999",
                "numbers": [9999.0],
                "evidence_ids": [eid]
            }
        ]
    }
    res = verify_answer(ans, ledger)
    assert not res["verified"]
    assert any("9999" in err for err in res["errors"])

def test_verifier_fabricated_in_narrative_fields():
    ledger = EvidenceLedger()
    eid = ledger.add("compute_kpi", {}, {"value": 100.0})

    # Test summary fabrication
    ans1 = {
        "summary": "Revenue spiked to 8888 in 2024.",
        "evidence_ids": [eid],
        "findings": []
    }
    res1 = verify_answer(ans1, ledger)
    assert not res1["verified"]
    assert any("Field 'summary'" in err and "8888" in err for err in res1["errors"])

    # Test quantified_impact fabrication
    ans2 = {
        "summary": "Revenue was 100.",
        "quantified_impact": "Impact was 7777 dollars",
        "evidence_ids": [eid],
        "findings": []
    }
    res2 = verify_answer(ans2, ledger)
    assert not res2["verified"]
    assert any("Field 'quantified_impact'" in err and "7777" in err for err in res2["errors"])

def test_verifier_missing_evidence_id():
    ledger = EvidenceLedger()
    ans = {
        "findings": [
            {
                "claim": "Metric is 100",
                "numbers": [100],
                "evidence_ids": ["E999"]
            }
        ]
    }
    res = verify_answer(ans, ledger)
    assert not res["verified"]
    assert any("Evidence ID E999 does not exist" in err for err in res["errors"])

def test_verifier_ignores_dates_and_ids():
    ledger = EvidenceLedger()
    eid = ledger.add("trend_analysis", {}, {"last_period": 350.0})

    # Narrative with years, dates, and order codes
    ans = {
        "summary": "On 2024-04-10, order ORD9912 had 350 units in 2024.",
        "findings": [
            {
                "claim": "Last period value was 350 on 2024-04-10",
                "numbers": [350],
                "evidence_ids": [eid]
            }
        ]
    }
    res = verify_answer(ans, ledger)
    assert res["verified"]
