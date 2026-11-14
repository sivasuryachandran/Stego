"""Generate samples/sample_demo_compact.pdf: an invented, dense 4-page reseller and services agreement for the demo.
Most of the 20 clause types appear (so the board is rich), two are left out on purpose (right of first refusal, covenant not to sue),
and a couple are worded softly. Four pages, one page per chunk, so a race finishes quickly.
Run:  .venv/bin/python samples/make_demo_sample.py"""
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

S = getSampleStyleSheet()
H = ParagraphStyle("h", parent=S["Heading2"], fontSize=13, spaceAfter=6)
B = ParagraphStyle("b", parent=S["BodyText"], fontSize=9.6, leading=12.4, spaceAfter=5)
PAGES = [
    ("MASTER TECHNOLOGY AND RESELLER AGREEMENT", [
        "This Master Technology and Reseller Agreement (the \"Agreement\") is made as of March 3, 2026 (the \"Effective Date\") between Harbor Analytics, Inc., a Delaware corporation (\"Customer\"), and Brightline Cloud Ltd., a company incorporated in England and Wales (\"Vendor\"). This is an invented sample contract used only to demonstrate Stego.",
        "1. Services. Vendor shall provide the cloud analytics platform, implementation, hosting and support services described in each Statement of Work (each an \"SOW\"). Vendor shall perform the services in a professional and workmanlike manner.",
        "2. Fees and Minimum Commitment. Customer shall pay the fees in each SOW within thirty (30) days of invoice. Customer commits to purchase a minimum of $1,200,000 of services in each contract year (the \"Annual Minimum\"), and shall pay the shortfall if purchases fall below the Annual Minimum.",
        "3. Term and Renewal. This Agreement begins on the Effective Date and continues for three (3) years. It renews automatically for successive one (1) year renewal terms unless either party gives written notice of non-renewal at least ninety (90) days before the end of the then-current term.",
        "4. License Grant. Vendor grants Customer a non-exclusive, worldwide license to access and use the platform and its documentation during the Term for Customer's internal business purposes and for resale to end customers as permitted in Section 6.",
        "5. Restrictions on the License. The license granted in Section 4 is non-transferable and non-sublicensable except to a Customer affiliate with Vendor's prior written consent. Customer shall not transfer the license to any third party.",
        "6. Exclusivity. During the Term, Customer shall be Vendor's exclusive reseller of the platform in the United States and Canada (the \"Territory\"), and Vendor shall not appoint any other reseller or sell directly to end customers in the Territory.",
    ]),
    ("", [
        "7. Revenue Share. Customer shall pay Vendor fifteen percent (15%) of all gross revenue Customer receives from reselling the platform, in addition to the fees in Section 2, and shall report resale revenue quarterly.",
        "8. Work Product. All custom software, reports and other work product created by Vendor specifically for Customer under an SOW shall be owned by Customer, and Vendor hereby assigns to Customer all right, title and interest in that work product. Vendor retains ownership of its pre-existing tools.",
        "9. Audit Rights. Upon ten (10) business days' notice, and not more than once per year, each party may audit the other party's books, records and facilities relating to fees, revenue share and security compliance under this Agreement.",
        "10. Insurance. Vendor shall maintain, throughout the Term, commercial general liability insurance of at least $2,000,000 per occurrence, cyber liability insurance of at least $5,000,000, and shall name Customer as an additional insured.",
        "11. Warranty. Vendor warrants that the services will conform to the applicable SOW for a period of twelve (12) months after acceptance (the \"Warranty Period\"). Vendor shall re-perform non-conforming services at no charge during the Warranty Period.",
        "12. Service Levels and Delay Damages. If Vendor misses a delivery date in an SOW, Vendor shall pay Customer liquidated damages equal to two percent (2%) of the SOW fees for each week of delay, up to ten percent (10%). The parties agree these amounts are a reasonable estimate of loss and not a penalty.",
        "13. Confidentiality. Each party shall protect the other party's confidential information with at least reasonable care and use it only to perform this Agreement.",
    ]),
    ("", [
        "14. Limitation of Liability. Except as stated in Section 15, neither party's aggregate liability arising out of this Agreement shall exceed the total fees paid or payable in the twelve (12) months preceding the event giving rise to the claim.",
        "15. Exceptions to the Cap. The limitation in Section 14 does not apply to a party's indemnification obligations, breach of confidentiality, gross negligence or willful misconduct, for which that party's liability is unlimited.",
        "16. Termination for Convenience. Customer may terminate this Agreement or any SOW for any reason or no reason upon ninety (90) days' prior written notice to Vendor, without further liability other than fees for services performed through the termination date.",
        "17. Transition Services. Following termination or expiration, Vendor shall continue to provide the services and reasonable transition assistance for up to one hundred eighty (180) days at the then-current rates, and shall return or delete Customer data on request.",
        "18. Change of Control. If either party undergoes a Change of Control, which includes any merger, sale of substantially all of its assets, or acquisition of more than fifty percent (50%) of its voting securities by a direct competitor of the other party, the other party may terminate this Agreement on thirty (30) days' written notice.",
        "19. Assignment. Neither party may assign this Agreement, in whole or in part, without the prior written consent of the other party, which shall not be unreasonably withheld, except that either party may assign to a successor to all or substantially all of its business upon notice.",
    ]),
    ("", [
        "20. Non-Competition. During the Term and for twelve (12) months afterwards, Customer shall not market, resell or develop a competing cloud analytics platform within the Territory.",
        "21. Publicity. Neither party shall issue a press release about this Agreement without the other party's prior written approval.",
        "22. Governing Law and Disputes. This Agreement is governed by the laws of the State of New York. The parties shall first try to resolve any dispute by good-faith negotiation between senior executives for thirty (30) days before commencing litigation in the courts of New York County.",
        "23. Notices. Notices must be in writing and delivered by courier or email with confirmation to the addresses in the signature block, and are effective on receipt.",
        "24. Entire Agreement. This Agreement, together with each SOW, is the entire agreement between the parties and supersedes all prior discussions. Amendments must be in writing and signed by both parties.",
        "Signed by the parties' authorised representatives as of the Effective Date.   Harbor Analytics, Inc. (Customer)  ______________   Brightline Cloud Ltd. (Vendor)  ______________",
    ]),
]
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_demo_compact.pdf")
doc = SimpleDocTemplate(out, pagesize=letter, title="Sample Demo Agreement (invented)", leftMargin=54, rightMargin=54, topMargin=54, bottomMargin=54)
flow = []
for i, (title, paras) in enumerate(PAGES):
    if i:
        flow.append(PageBreak())
    if title:
        flow += [Paragraph(title, H), Spacer(1, 6)]
    flow += [Paragraph(p, B) for p in paras]
doc.build(flow)
print("wrote", out)
