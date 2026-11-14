"""Generate samples/sample_vendor_agreement.pdf (an invented contract) for demoing upload.
Run:  .venv/bin/python samples/make_sample.py"""
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

S = getSampleStyleSheet()
PAGES = [
    ("MASTER SERVICES AGREEMENT", [
        "This Master Services Agreement (the \"Agreement\") is entered into between Northwind Traders, Inc. (\"Customer\") and Contoso Software Ltd. (\"Vendor\"). This is an invented sample contract used only to demo Stego.",
        "1. Services. Vendor shall provide the software development and hosting services described in each Statement of Work.",
        "2. Fees. Customer shall pay the fees set out in each Statement of Work within thirty (30) days of invoice.",
        "3. Term and Renewal. This Agreement begins on the Effective Date and continues for three (3) years. It shall automatically renew for successive one (1) year terms unless either party gives notice of non-renewal at least ninety (90) days before the end of the then-current term.",
    ]),
    ("", [
        "4. Termination for Convenience. Customer may terminate this Agreement for any reason or no reason upon sixty (60) days' prior written notice to Vendor.",
        "5. Audit Rights. Customer shall have the right, upon ten (10) business days' notice, to audit Vendor's books and records relating to fees charged under this Agreement.",
        "6. Insurance. Vendor shall maintain commercial general liability insurance of not less than $2,000,000 per occurrence throughout the Term.",
    ]),
    ("", [
        "7. Intellectual Property. All work product created by Vendor under this Agreement shall be owned by Customer, and Vendor hereby assigns all right, title and interest therein to Customer. Vendor retains ownership of its pre-existing tools.",
        "8. License Grant. Vendor grants Customer a non-exclusive, non-transferable license to use Vendor's pre-existing tools embedded in the deliverables.",
        "9. Confidentiality. Each party shall protect the other's confidential information using reasonable care.",
    ]),
    ("", [
        "10. Limitation of Liability. In no event shall either party's aggregate liability under this Agreement exceed the total fees paid or payable in the twelve (12) months preceding the claim.",
        "11. Exceptions. The limitations of liability in Section 10 shall not apply to either party's indemnification obligations, breach of confidentiality, or gross negligence, for which liability shall be unlimited.",
        "12. Change of Control. Either party may terminate this Agreement upon written notice if the other party undergoes a Change of Control, including any merger, sale of substantially all assets, or acquisition of more than fifty percent (50%) of voting securities.",
    ]),
    ("", [
        "13. Assignment. Neither party may assign this Agreement, in whole or in part, without the prior written consent of the other party, which shall not be unreasonably withheld.",
        "14. Governing Law. This Agreement is governed by the laws of the State of California.",
        "15. Entire Agreement. This Agreement is the entire agreement between the parties.",
    ]),
]

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_vendor_agreement.pdf")
doc = SimpleDocTemplate(out, pagesize=letter, title="Sample Vendor Agreement")
flow = []
for i, (title, paras) in enumerate(PAGES):
    if i:
        flow.append(PageBreak())
    if title:
        flow += [Paragraph(title, S["Title"]), Spacer(1, 12)]
    for p in paras:
        flow += [Paragraph(p, S["BodyText"]), Spacer(1, 10)]
doc.build(flow)
print("wrote", out)
