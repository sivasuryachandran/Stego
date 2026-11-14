"""Generate three invented sample documents (lease, loan, health insurance) for the contract-type templates.
Run:  python samples/make_template_samples.py
Each document deliberately OMITS some clauses so a template run has both present and absent answers (see EXPECTED_ABSENT)."""
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

S = getSampleStyleSheet()
DOCS = {
    "sample_lease": ("COMMERCIAL LEASE AGREEMENT", [
        ["This Commercial Lease Agreement (the \"Lease\") is made between Harbor Point Properties LLC (\"Landlord\") and Brightside Bakery Inc. (\"Tenant\") for the premises at 410 Market Street, Suite 12 (the \"Premises\"). This is an invented sample used only to demo Stego.",
         "1. Term and Rent. The Lease runs for five (5) years from the Commencement Date. Tenant shall pay base rent of $4,200 per month, payable on the first day of each month.",
         "2. Rent Increases. Base rent shall increase by three percent (3%) on each anniversary of the Commencement Date.",
         "3. Security Deposit. Tenant shall deposit $8,400 with Landlord as security for Tenant's obligations. Landlord shall hold the deposit and return the balance within thirty (30) days after the Lease ends, less amounts applied to unpaid rent or damage."],
        ["4. Renewal. Tenant may renew this Lease for one additional term of five (5) years by giving written notice at least one hundred eighty (180) days before the term ends.",
         "5. Early Termination. Tenant may terminate this Lease after the third year by giving ninety (90) days' written notice and paying a termination fee equal to three (3) months of rent.",
         "6. Assignment and Subletting. Tenant shall not assign this Lease or sublet any part of the Premises without Landlord's prior written consent, which Landlord may withhold in its sole discretion.",
         "7. Insurance. Tenant shall maintain commercial general liability insurance of at least $1,000,000 per occurrence and shall name Landlord as an additional insured."],
        ["8. Maintenance and Repairs. Tenant shall keep the interior of the Premises in good repair. Landlord shall maintain the roof, structure and common areas.",
         "9. Late Charges and Default. Rent not received within five (5) days of its due date incurs a late charge of five percent (5%). If Tenant fails to cure a default within ten (10) days after notice, Landlord may terminate this Lease and re-enter the Premises.",
         "10. Entry. Landlord may enter the Premises upon twenty-four (24) hours' notice to inspect, repair or show the Premises to prospective tenants.",
         "11. Governing Law. This Lease is governed by the laws of the State of Oregon."],
    ], ["Holdover Rent"]),
    "sample_loan": ("LOAN AGREEMENT", [
        ["This Loan Agreement (the \"Agreement\") is made between First Meridian Bank (\"Lender\") and Cedar Ridge Farms LLC (\"Borrower\"). This is an invented sample used only to demo Stego.",
         "1. The Loan. Lender agrees to lend Borrower the principal amount of $750,000 (the \"Loan\"). Borrower shall repay the Loan in sixty (60) equal monthly installments of principal and interest.",
         "2. Interest. The Loan bears interest at a variable rate per annum equal to the Prime Rate published by Lender plus two percent (2.00%), adjusted on the first day of each calendar quarter.",
         "3. Prepayment. Borrower may prepay the Loan in whole or in part, provided that Borrower pays Lender a prepayment premium of two percent (2%) of the amount prepaid during the first three years."],
        ["4. Security. The Loan is secured by a first-priority security interest in all of Borrower's equipment and by a first deed of trust on the real property at 88 Ridge Road.",
         "5. Guaranty. Payment of the Loan is personally guaranteed by Marta Olsen pursuant to a separate Guaranty delivered on the date of this Agreement.",
         "6. Late Charge. Any installment not paid within ten (10) days after its due date is subject to a late charge of five percent (5%) of the overdue amount.",
         "7. Events of Default. Each of the following is an Event of Default: (a) failure to pay any amount when due; (b) any false representation by Borrower; (c) Borrower's insolvency or bankruptcy."],
        ["8. Remedies and Acceleration. Upon an Event of Default, Lender may declare the entire unpaid balance of the Loan, together with accrued interest, immediately due and payable.",
         "9. Governing Law. This Agreement is governed by the laws of the State of Washington.",
         "10. Entire Agreement. This Agreement is the entire agreement between the parties regarding the Loan."],
    ], ["Financial Covenants", "Cross-Default", "Balloon Payment"]),
    "sample_health_policy": ("HEALTH INSURANCE POLICY: EVIDENCE OF COVERAGE", [
        ["This Evidence of Coverage (the \"Policy\") is issued by Pinecrest Health Plan (\"we\") to the person named on the Schedule of Benefits (\"you\"). This is an invented sample used only to demo Stego.",
         "1. Deductible. You must pay the first $2,000 of covered charges each calendar year (the \"Deductible\") before we pay benefits, except for preventive care.",
         "2. Out-of-Pocket Maximum. Your cost sharing for covered services in a calendar year will not exceed $7,500 for one person. After you reach this limit we pay 100% of covered charges for the rest of the year.",
         "3. Network. Benefits are highest when you use a Pinecrest participating provider. If you use an out-of-network provider we pay 60% of the allowed amount and you pay the balance."],
        ["4. Prior Authorization. Inpatient admissions, elective surgery and advanced imaging require our prior authorization. If you do not obtain it, we may reduce or deny your benefits.",
         "5. Exclusions. This Policy does not cover cosmetic surgery, experimental treatments, services that are not medically necessary, or care received outside the United States except in an emergency.",
         "6. Premium Changes. We may change your premium or your cost sharing on each policy anniversary by giving you at least sixty (60) days' written notice.",
         "7. Cancellation. We may cancel this Policy if you fail to pay premium, or if you commit fraud or make an intentional misrepresentation. You may cancel at any time by written notice."],
        ["8. Appeals. If we deny a claim you may file an appeal within one hundred eighty (180) days. We will give you a written decision within thirty (30) days, and you may request an external review.",
         "9. Governing Law. This Policy is governed by the laws of the State of Colorado.",
         "10. Entire Contract. This Policy and the Schedule of Benefits are the entire contract between you and us."],
    ], ["Pre-Existing Condition Limits", "Coordination Of Benefits"]),
}

EXPECTED_ABSENT = {k: v[2] for k, v in DOCS.items()}

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    for name, (title, pages, _absent) in DOCS.items():
        out = os.path.join(here, name + ".pdf")
        doc = SimpleDocTemplate(out, pagesize=letter, title=title)
        flow = []
        for i, paras in enumerate(pages):
            if i:
                flow.append(PageBreak())
            else:
                flow += [Paragraph(title, S["Title"]), Spacer(1, 12)]
            for p in paras:
                flow += [Paragraph(p, S["BodyText"]), Spacer(1, 10)]
        doc.build(flow)
        print("wrote", out)
