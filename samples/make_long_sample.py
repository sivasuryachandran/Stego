"""Generate samples/long_sample_msa.pdf: an INVENTED ~30-page agreement for demoing the race on a long contract.
Realistic boilerplate with real clause types planted at known sections. Not a real contract, not from CUAD.
Run:  .venv/bin/python samples/make_long_sample.py"""
import os
import random

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

import sys
COMPACT = "compact" in sys.argv   # ~13 pages: fits a free LLM tier
random.seed(14)
S = getSampleStyleSheet()
A, B = "Halcyon Logistics Group, Inc. (\"Customer\")", "Brightwater Systems Ltd. (\"Supplier\")"

FILLER = [
    "Each party shall perform its obligations under this Agreement in a professional and workmanlike manner and in accordance with generally accepted industry standards applicable to services of this kind.",
    "All notices required or permitted under this Agreement shall be in writing and shall be deemed given when delivered personally, one (1) business day after being sent by a recognized overnight courier, or three (3) business days after being mailed by registered post.",
    "The headings in this Agreement are for convenience only and shall not affect the interpretation of any provision. References to Sections are to Sections of this Agreement unless the context requires otherwise.",
    "If any provision of this Agreement is held to be invalid or unenforceable, the remaining provisions shall continue in full force and effect, and the parties shall negotiate in good faith a valid replacement provision that achieves the original intent.",
    "Neither party shall be liable for any delay or failure to perform caused by events beyond its reasonable control, including natural disasters, governmental action, labor disputes, or failures of public utilities, provided that it notifies the other party promptly.",
    "The parties are independent contractors. Nothing in this Agreement creates a partnership, joint venture, agency, or employment relationship, and neither party has authority to bind the other.",
    "Supplier shall maintain complete and accurate records relating to the Services for a period of three (3) years following the date on which the relevant Statement of Work is completed.",
    "Customer shall provide Supplier with timely access to personnel, information, and facilities reasonably necessary for Supplier to perform the Services, and Supplier shall not be responsible for delays caused by Customer's failure to do so.",
    "Each Statement of Work shall describe the scope of the Services, the deliverables, the schedule, the acceptance criteria, and the fees. In the event of a conflict, the terms of this Agreement control over any Statement of Work unless the Statement of Work expressly states otherwise.",
    "Supplier shall comply with all laws and regulations applicable to its performance of the Services, including those relating to anti-corruption, export controls, data protection, and employment.",
    "Invoices shall be issued monthly in arrears and are payable within thirty (30) days of receipt. Undisputed amounts not paid when due accrue interest at one percent (1%) per month or the maximum rate permitted by law, whichever is lower.",
    "Customer may dispute an invoice in good faith by notifying Supplier in writing within fifteen (15) days of receipt, identifying the disputed amount and the reasons, and shall pay all undisputed amounts when due.",
    "Each party shall protect the other party's Confidential Information using at least the same degree of care it uses for its own confidential information of similar importance, and in no event less than reasonable care.",
    "Confidential Information does not include information that is or becomes publicly available without breach of this Agreement, was already known to the receiving party, is independently developed, or is rightfully received from a third party.",
    "Supplier shall implement and maintain administrative, technical, and physical safeguards designed to protect Customer Data against unauthorized access, use, or disclosure, consistent with recognized industry frameworks.",
    "Upon written request, each party shall return or destroy the other party's Confidential Information, except that a party may retain copies as required by law or in routine backups, subject to continuing confidentiality obligations.",
    "This Agreement may be executed in counterparts, each of which is an original and all of which together constitute one instrument. Signatures delivered electronically are deemed original signatures.",
    "The failure of either party to enforce any provision of this Agreement shall not constitute a waiver of that provision or of the right to enforce it later. Any waiver must be in writing and signed by the waiving party.",
    "Supplier shall assign appropriately qualified personnel to the Services and shall replace any person reasonably requested by Customer to be removed, provided that the request is not based on unlawful grounds.",
    "Acceptance of each deliverable shall occur when Customer confirms in writing that it conforms to the acceptance criteria, or ten (10) business days after delivery if Customer has not given notice of non-conformity.",
]

PLANTED = {  # section number -> (heading, clause text)
    4: ("Term and Renewal", "This Agreement commences on the Effective Date and continues for an initial term of three (3) years. Thereafter it shall automatically renew for successive one (1) year renewal terms unless either party gives written notice of non-renewal at least ninety (90) days before the end of the then-current term."),
    7: ("Exclusivity", "During the Term, Customer shall purchase the Services described in each Statement of Work exclusively from Supplier within the Territory, and Supplier shall not provide substantially similar Services to any direct competitor of Customer in the Territory."),
    9: ("Minimum Commitment", "Customer commits to purchase Services with aggregate fees of not less than two million dollars ($2,000,000) in each contract year. Any shortfall shall be invoiced by Supplier at the end of the contract year."),
    12: ("License Grant", "Supplier grants Customer a non-exclusive, non-transferable, worldwide license during the Term to use the Supplier Tools solely for Customer's internal business purposes. Customer shall not sublicense, rent, or otherwise make the Supplier Tools available to any third party."),
    14: ("Revenue Sharing", "Customer shall pay Supplier a royalty equal to four percent (4%) of net revenue that Customer receives from the commercialization of any product that incorporates the Deliverables, payable quarterly within forty-five (45) days after the end of each quarter."),
    16: ("Intellectual Property", "All work product created by Supplier specifically for Customer under this Agreement shall be owned exclusively by Customer, and Supplier hereby irrevocably assigns to Customer all right, title, and interest in and to such work product. Supplier retains ownership of its pre-existing tools and know-how."),
    18: ("Audit Rights", "Upon ten (10) business days' prior notice, Customer shall have the right, not more than once in any twelve-month period, to audit Supplier's books, records, and facilities relating to the Services and fees charged under this Agreement."),
    20: ("Warranty", "Supplier warrants that the Services will be performed in a professional manner and that each deliverable will conform to its specifications for a period of twelve (12) months following acceptance (the Warranty Period). Customer's sole remedy for breach of this warranty is re-performance or refund."),
    22: ("Insurance", "Supplier shall maintain, throughout the Term, commercial general liability insurance of not less than three million dollars ($3,000,000) per occurrence, professional liability insurance of not less than five million dollars ($5,000,000), and workers' compensation insurance as required by law."),
    24: ("Limitation of Liability", "In no event shall either party's aggregate liability arising out of or related to this Agreement exceed the total fees paid or payable by Customer under this Agreement in the twelve (12) months immediately preceding the event giving rise to the claim."),
    25: ("Exceptions to Limitation", "The limitations of liability in Section 24 shall not apply to either party's indemnification obligations, breach of confidentiality, or gross negligence or willful misconduct, for which liability shall be unlimited."),
    26: ("Liquidated Damages", "If Supplier fails to deliver a Milestone Deliverable by the date specified in the applicable Statement of Work, Supplier shall pay Customer liquidated damages of one percent (1%) of the Milestone fee for each week of delay, up to a maximum of ten percent (10%)."),
    28: ("Termination for Convenience", "Customer may terminate this Agreement or any Statement of Work for any reason or no reason upon sixty (60) days' prior written notice to Supplier. Upon such termination, Customer shall pay for Services performed through the effective date of termination."),
    29: ("Post-Termination Services", "Following expiration or termination, Supplier shall, at Customer's request, continue to provide transition assistance for up to one hundred eighty (180) days at the rates then in effect, so as to enable an orderly transfer of the Services."),
    31: ("Change of Control", "Either party may terminate this Agreement upon written notice if the other party undergoes a Change of Control, which includes any merger, sale of substantially all of its assets, or acquisition of more than fifty percent (50%) of its voting securities by a direct competitor of the terminating party."),
    32: ("Assignment", "Neither party may assign this Agreement or any rights hereunder, whether by operation of law or otherwise, without the prior written consent of the other party, which shall not be unreasonably withheld, except that no consent is required for an assignment to an affiliate."),
    34: ("Right of First Refusal", "If Supplier receives a bona fide offer from a third party to acquire or exclusively license the Deliverables, Supplier shall first offer the same terms to Customer, who shall have thirty (30) days to accept (a right of first refusal)."),
    36: ("Non-Compete", "During the Term and for a period of two (2) years thereafter, Supplier shall not, directly or indirectly, provide logistics software services to any business that competes with Customer in the Territory."),
    38: ("Covenant Not to Challenge", "Supplier agrees not to challenge, or assist any third party in challenging, the validity or ownership of Customer's trademarks or the work product assigned to Customer under this Agreement, and agrees not to bring any claim against Customer for the use thereof."),
    40: ("Governing Law", "This Agreement is governed by the laws of the State of Delaware, without regard to its conflict-of-laws principles. The parties submit to the exclusive jurisdiction of the state and federal courts located in Wilmington, Delaware."),
}

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "long_sample_compact.pdf" if COMPACT else "long_sample_msa.pdf")
doc = SimpleDocTemplate(out, pagesize=letter, title="Long Sample Agreement (invented)")
flow = [Paragraph("MASTER SUPPLY AND SERVICES AGREEMENT", S["Title"]), Spacer(1, 10),
        Paragraph(f"This Master Supply and Services Agreement is made between {A} and {B}. "
                  "<b>This is an invented sample contract generated for demonstrating Stego. It is not a real agreement and is not from CUAD.</b>", S["BodyText"]), Spacer(1, 14)]
for n in range(1, 46):
    heading, text = PLANTED.get(n, (None, None))
    heading = heading or random.choice(["General Provisions", "Services", "Fees and Payment", "Confidentiality", "Data Protection", "Personnel", "Acceptance", "Compliance", "Records", "Notices", "Relationship of the Parties", "Force Majeure"])
    flow.append(Paragraph(f"<b>{n}. {heading}.</b>", S["Heading3"]))
    paras = random.sample(FILLER, 1 if COMPACT else 5)
    if text:
        paras.insert(random.randint(1, 3), f"{n}.1 {text}")
    for t in paras:
        flow += [Paragraph(t, S["BodyText"]), Spacer(1, 6)]
    if n % (9 if COMPACT else 3) == 0:
        flow.append(PageBreak())
doc.build(flow)
print("wrote", out)
