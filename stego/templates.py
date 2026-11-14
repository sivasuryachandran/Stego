"""Contract-type templates for the APP path only. Not part of the benchmark.

The pre-registered benchmark covers the 20 CUAD categories (the "commercial" template). The templates below have no
gold labels, so their answers are NOT benchmarked: the UI and the seal say so. Urgent lists are policy flags, not ground truth.
"""
from . import config
from .defs import CUES, DEFINITIONS

TEMPLATES = {
    "commercial": {
        "label": "Commercial contract (CUAD 20)", "benchmarked": True,
        "categories": list(config.CATEGORIES), "definitions": dict(DEFINITIONS),
        "urgent": ["Uncapped Liability", "Change Of Control", "Liquidated Damages", "Non-Compete"], "cues": {},
        "detect": None,
    },
    "lease": {
        "label": "Lease", "benchmarked": False,
        "detect": "Is this document a lease or rental agreement for real property, with a landlord and a tenant and premises being let?",
        "categories": ["Rent Escalation", "Security Deposit", "Early Termination Right", "Renewal Option", "Assignment And Subletting",
                       "Tenant Insurance Requirement", "Maintenance And Repairs", "Late Fees And Default", "Landlord Entry Rights", "Holdover Rent"],
        "definitions": {
            "Rent Escalation": "The rent increases over the term by a fixed step, a percentage, or an index adjustment.",
            "Security Deposit": "The tenant must pay a deposit held as security for its obligations, and the lease says how it is held, applied or returned.",
            "Early Termination Right": "A party may end the lease before the stated term expires, with notice or a fee.",
            "Renewal Option": "The tenant or landlord may extend or renew the lease term.",
            "Assignment And Subletting": "The lease says whether the tenant may assign the lease or sublet the premises, for example only with the landlord's consent, or not at all.",
            "Tenant Insurance Requirement": "The tenant must carry liability or property insurance, or name the landlord as an additional insured.",
            "Maintenance And Repairs": "The lease allocates responsibility for repairs and upkeep of the premises, the building or common areas.",
            "Late Fees And Default": "The lease sets late payment charges, or defines events of default and the landlord's remedies such as eviction or acceleration of rent.",
            "Landlord Entry Rights": "The landlord may enter the premises, with or without advance notice.",
            "Holdover Rent": "A tenant who stays after the term ends must pay increased rent or other charges.",
        },
        "urgent": ["Late Fees And Default", "Holdover Rent"],
        "cues": {"Rent Escalation": r"escalat|increase[sd]? (in|of|by)|CPI|consumer price|annual adjustment",
                 "Security Deposit": r"security deposit", "Early Termination Right": r"terminat\w+ (this )?lease|early termination|prior to the expiration",
                 "Renewal Option": r"renew|extend (the )?term|option to extend", "Assignment And Subletting": r"assign|sublet|sublease",
                 "Tenant Insurance Requirement": r"insurance|additional insured", "Maintenance And Repairs": r"repair|maintenance|maintain",
                 "Late Fees And Default": r"late (fee|charge)|event of default|default", "Landlord Entry Rights": r"enter the premises|right of entry|access to the premises",
                 "Holdover Rent": r"holdover|hold over|holds over|remain[s]? in possession"},
    },
    "loan": {
        "label": "Loan", "benchmarked": False,
        "detect": "Is this document a loan, credit, mortgage or promissory note agreement, with a lender and a borrower, a principal amount and interest?",
        "categories": ["Interest Rate", "Prepayment Penalty", "Events Of Default", "Acceleration", "Collateral Or Security Interest",
                       "Guaranty", "Financial Covenants", "Late Payment Charge", "Cross-Default", "Balloon Payment"],
        "definitions": {
            "Interest Rate": "The agreement states the interest rate or how it is set, such as a fixed rate or an index plus a margin.",
            "Prepayment Penalty": "The borrower must pay a fee or premium for repaying early, or early repayment is restricted.",
            "Events Of Default": "The agreement lists the events that count as a default by the borrower.",
            "Acceleration": "After a default the lender may declare the entire balance immediately due.",
            "Collateral Or Security Interest": "The loan is secured by collateral, a lien, a mortgage or a security interest.",
            "Guaranty": "A third party guarantees repayment of the loan.",
            "Financial Covenants": "The borrower must maintain financial ratios or thresholds, or meet financial reporting obligations.",
            "Late Payment Charge": "A late fee or a higher default interest rate applies to late payments.",
            "Cross-Default": "A default under another agreement or debt of the borrower is a default under this one.",
            "Balloon Payment": "A large final payment is due at maturity.",
        },
        "urgent": ["Prepayment Penalty", "Acceleration", "Balloon Payment"],
        "cues": {"Interest Rate": r"interest rate|per annum|prime rate|LIBOR|SOFR|margin", "Prepayment Penalty": r"prepay|prepayment",
                 "Events Of Default": r"event[s]? of default", "Acceleration": r"accelerat|immediately due|due and payable",
                 "Collateral Or Security Interest": r"collateral|security interest|lien|mortgage|deed of trust", "Guaranty": r"guarant",
                 "Financial Covenants": r"covenant|ratio|net worth|financial statements", "Late Payment Charge": r"late (fee|charge|payment)|default rate",
                 "Cross-Default": r"cross.?default|other (indebtedness|agreement)", "Balloon Payment": r"balloon|final payment|maturity date"},
    },
    "health_insurance": {
        "label": "Health insurance", "benchmarked": False,
        "detect": "Is this document a health insurance policy, evidence of coverage or benefits plan, with an insurer, an insured person, covered services and cost sharing?",
        "categories": ["Deductible", "Out-Of-Pocket Maximum", "Coverage Exclusions", "Pre-Existing Condition Limits", "Prior Authorization",
                       "Network Restrictions", "Premium Change Rights", "Cancellation And Termination", "Appeals Process", "Coordination Of Benefits"],
        "definitions": {
            "Deductible": "The insured must pay a stated amount before coverage pays benefits.",
            "Out-Of-Pocket Maximum": "There is an annual limit on what the insured pays in cost sharing.",
            "Coverage Exclusions": "The policy lists services, treatments or conditions that are not covered.",
            "Pre-Existing Condition Limits": "A waiting period, limit or exclusion applies to conditions that existed before coverage began.",
            "Prior Authorization": "Certain services require approval from the insurer before they are covered.",
            "Network Restrictions": "Coverage or cost sharing differs between in-network and out-of-network providers.",
            "Premium Change Rights": "The insurer may change the premium or cost sharing during the term or at renewal.",
            "Cancellation And Termination": "The policy states when coverage may be cancelled, terminated or not renewed.",
            "Appeals Process": "The policy describes how the insured can appeal or dispute a denied claim.",
            "Coordination Of Benefits": "The policy sets rules for when another insurer or plan also covers the insured.",
        },
        "urgent": ["Coverage Exclusions", "Pre-Existing Condition Limits", "Premium Change Rights"],
        "cues": {"Deductible": r"deductible", "Out-Of-Pocket Maximum": r"out.of.pocket", "Coverage Exclusions": r"exclu|not covered|limitations",
                 "Pre-Existing Condition Limits": r"pre.?existing", "Prior Authorization": r"prior authori|pre.?authori|precertif",
                 "Network Restrictions": r"in.network|out.of.network|participating provider", "Premium Change Rights": r"premium[s]? (may|will|can)|change (the )?premium|rate change",
                 "Cancellation And Termination": r"cancel|terminat|non.?renew|rescind", "Appeals Process": r"appeal|grievance|denied claim",
                 "Coordination Of Benefits": r"coordination of benefits|other (coverage|insurance|plan)"},
    },
}

DETECT_MIN = 0.60


def template_cues():
    out = {}
    for t in TEMPLATES.values():
        out.update(t["cues"])
    return out


def detect_questions():
    return {f"t_{k}": {"type": "noul", "instructions": t["detect"]} for k, t in TEMPLATES.items() if t["detect"]}


def pick_template(scores):
    """scores: {template key: max p over the first chunks}. Returns the best template at or above DETECT_MIN, else commercial."""
    best = max(scores, key=scores.get) if scores else None
    return best if best and scores[best] >= DETECT_MIN else "commercial"
