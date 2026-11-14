"""Fallback clause definitions + evidence cues for live (non-CUAD) contracts.
The benchmark uses CUAD's own 'Details:' text; these are short paraphrases for uploads only.
CUES locate the evidence paragraph inside the page Drex ranked first (plain regex, no LLM)."""

DEFINITIONS = {
    "Anti-Assignment": "Is consent or notice required of a party if the contract is assigned to a third party?",
    "License Grant": "Does the contract contain a license granted by one party to its counterparty?",
    "Cap On Liability": "Does the contract include a cap on liability upon the breach of a party's obligation (e.g. fees paid in the last 12 months)?",
    "Audit Rights": "Does a party have the right to audit the books, records, or physical locations of the counterparty?",
    "Revenue/Profit Sharing": "Is one party required to share revenue or profit with the counterparty for any technology, goods, or services?",
    "Exclusivity": "Is there an exclusive dealing commitment, such as exclusive purchase, supply, or territory rights?",
    "Insurance": "Is there a requirement for a party to maintain insurance of a specified kind or amount?",
    "Minimum Commitment": "Is there a minimum order size, minimum purchase, or minimum product or fee commitment?",
    "Termination For Convenience": "Can a party terminate the contract without cause (e.g. on notice, for any reason)?",
    "Post-Termination Services": "Is a party subject to obligations after termination or expiration, such as transition or wind-down services?",
    "Renewal Term": "Does the contract describe a renewal term or automatic renewal?",
    "Change Of Control": "Does a change of control (merger, acquisition, sale of substantially all assets) give a party a right such as termination or consent?",
    "Covenant Not To Sue": "Is a party restricted from contesting the validity of the counterparty's IP or bringing a claim against it?",
    "Non-Compete": "Is there a restriction on a party's ability to compete with the counterparty or operate in a geography or business?",
    "Ip Ownership Assignment": "Does intellectual property created by one party become owned by the other party, or is IP assigned?",
    "Non-Transferable License": "Does the contract limit the ability of a party to transfer the license to a third party?",
    "Rofr/Rofo/Rofn": "Is there a right of first refusal, first offer, or first negotiation for the counterparty?",
    "Liquidated Damages": "Does the contract fix liquidated damages or a penalty for breach or delay?",
    "Uncapped Liability": "Is a party's liability uncapped upon the breach of its obligation in the contract (e.g. unlimited liability or carve-outs from the cap)?",
    "Warranty Duration": "Is there a duration or period specified for a warranty on goods or services?",
}

CUES = {
    "Anti-Assignment": r"assign", "License Grant": r"licen[cs]e", "Cap On Liability": r"aggregate liability|shall not exceed|liability.{0,40}(cap|limit)",
    "Audit Rights": r"audit|inspect", "Revenue/Profit Sharing": r"royalt|revenue shar|profit shar",
    "Exclusivity": r"exclusiv", "Insurance": r"insur", "Minimum Commitment": r"minimum",
    "Termination For Convenience": r"for (any|no) reason|convenience|without cause", "Post-Termination Services": r"(after|upon|following) (the )?(termination|expiration)",
    "Renewal Term": r"renew", "Change Of Control": r"change (of|in) control|merger|acquisition",
    "Covenant Not To Sue": r"not to sue|challenge|contest", "Non-Compete": r"compet",
    "Ip Ownership Assignment": r"intellectual property|work product|hereby assigns|owned by", "Non-Transferable License": r"non-?transfer|may not (sub)?license",
    "Rofr/Rofo/Rofn": r"first refusal|first offer|first negotiation", "Liquidated Damages": r"liquidated",
    "Uncapped Liability": r"unlimited|uncapped|shall not apply.{0,80}liabilit|gross negligence", "Warranty Duration": r"warrant",
}
