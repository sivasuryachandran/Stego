// SAMPLE DATA ONLY: invented for layout/demo. Nothing here was measured.
// The UI replaces it with runs/<dir>/results.json, predictions.jsonl and ledger.jsonl when they exist.
window.STEGO_SAMPLE = (() => {
  const CATS = ["Anti-Assignment","License Grant","Cap On Liability","Audit Rights","Revenue/Profit Sharing",
    "Exclusivity","Insurance","Minimum Commitment","Termination For Convenience","Post-Termination Services",
    "Renewal Term","Change Of Control","Covenant Not To Sue","Non-Compete","Ip Ownership Assignment",
    "Non-Transferable License","Rofr/Rofo/Rofn","Liquidated Damages","Uncapped Liability","Warranty Duration"];

  let seed = 14;
  const rnd = () => (seed = (seed * 1664525 + 1013904223) % 4294967296) / 4294967296;

  // hand-written passages for the headline clauses; others get generic filler text
  const TXT = {
    "Change Of Control": "Either party may terminate this Agreement upon written notice if the other party undergoes a Change of Control, including any merger, sale of substantially all assets, or acquisition of more than fifty percent (50%) of voting securities.",
    "Uncapped Liability": "The limitations of liability in this Section shall not apply to either party's indemnification obligations, breach of confidentiality, or gross negligence, for which liability shall be unlimited.",
    "Cap On Liability": "In no event shall either party's aggregate liability under this Agreement exceed the total fees paid or payable in the twelve (12) months preceding the claim.",
    "Anti-Assignment": "Neither party may assign this Agreement, in whole or in part, without the prior written consent of the other party, which shall not be unreasonably withheld.",
    "Termination For Convenience": "Customer may terminate this Agreement for any reason or no reason upon sixty (60) days' prior written notice to Vendor.",
    "Audit Rights": "Customer shall have the right, upon ten (10) business days' notice, to audit Vendor's books and records relating to fees charged under this Agreement.",
    "Exclusivity": "During the Term, Distributor shall purchase the Products exclusively from Supplier and shall not market competing products in the Territory.",
    "Renewal Term": "This Agreement shall automatically renew for successive one (1) year terms unless either party gives notice of non-renewal at least ninety (90) days before the end of the then-current term.",
    "Non-Compete": "During the Term and for two (2) years thereafter, Vendor shall not provide substantially similar services to any direct competitor of Customer in the Territory.",
    "Liquidated Damages": "If Vendor fails to meet the delivery date, Vendor shall pay liquidated damages of one percent (1%) of the order value for each week of delay, up to ten percent (10%).",
    "Insurance": "Vendor shall maintain commercial general liability insurance of not less than $2,000,000 per occurrence throughout the Term.",
    "Ip Ownership Assignment": "All work product created by Vendor under this Agreement shall be owned by Customer, and Vendor hereby assigns all right, title and interest therein to Customer.",
  };
  const generic = c => `Provisions relating to ${c.toLowerCase()} appear in this section of the Agreement, as set out in the parties' respective obligations.`;

  // [title, pages, hand-set p's] ; unspecified categories get low-ish noisy p
  const defs = [
    ["Master Services Agreement — Northwind / Contoso", 34, {"Change Of Control":.97,"Uncapped Liability":.52,"Cap On Liability":.95,"Anti-Assignment":.98,"Termination For Convenience":.91,"Audit Rights":.88,"Renewal Term":.94,"Insurance":.96}],
    ["Distribution Agreement — Fabrikam / Tailspin", 27, {"Exclusivity":.99,"Non-Compete":.86,"Minimum Commitment":.93,"Anti-Assignment":.97,"Change Of Control":.41,"Rofr/Rofo/Rofn":.12,"Renewal Term":.9}],
    ["Software License — Adventure Works / Litware", 41, {"License Grant":.99,"Non-Transferable License":.96,"Cap On Liability":.62,"Uncapped Liability":.97,"Audit Rights":.93,"Warranty Duration":.89,"Ip Ownership Assignment":.58}],
    ["Supply Agreement — Wingtip / Proseware", 22, {"Liquidated Damages":.95,"Exclusivity":.5,"Termination For Convenience":.03,"Insurance":.9,"Renewal Term":.07,"Post-Termination Services":.77,"Change Of Control":.94}],
  ];

  const clause = (title, pages) => {
    const clauses = {};
    for (const c of CATS) {
      const set = defs.find(d => d[0] === title)[2][c];
      const p = set ?? (rnd() < .75 ? .01 + rnd() * .09 : .12 + rnd() * .3);
      const page = 1 + Math.floor(rnd() * pages);
      clauses[c] = { p: +p.toFixed(3), page, evidence: [{ page, text: TXT[c] || generic(c) }] };
    }
    return clauses;
  };

  const contracts = defs.map(([title, pages]) => ({ title, pages, ms: 3000 + Math.round(rnd() * 3500), clauses: clause(title, pages) }));

  const arm = (name, o) => Object.assign({ arm: name }, o);
  const rel = [[.05,420,.04],[.15,60,.12],[.25,34,.22],[.35,28,.3],[.45,22,.47],[.55,24,.58],[.65,26,.69],[.75,38,.8],[.85,70,.9],[.95,520,.97]]
    .map(([m, n, f], i) => ({ bin: `${(i / 10).toFixed(1)}-${((i + 1) / 10).toFixed(1)}`, n, mean_p: m, frac_yes: f }));

  const summary = [
    arm("A frontier LLM", { contracts: 82, failed_contracts: 0, accuracy: .93, macro_f1: .81, micro_f1: .84, "evidence_hit@1": .62, "evidence_hit@3": .78, latency_p50_ms: 38000, latency_p95_ms: 71000, cost_per_contract_usd: .41, llm_calls: 82 }),
    arm("B Stego (Drex only)", { contracts: 82, failed_contracts: 0, accuracy: .9, macro_f1: .74, micro_f1: .77, "evidence_hit@1": .55, "evidence_hit@3": .74, brier: .062, ece: .028, "selective_acc@80": .96, "selective_acc@90": .93, "selective_acc@100": .9, "acc_when_conf>=0.93": .97, "n_conf>=0.93": 1210, latency_p50_ms: 4200, latency_p95_ms: 7800, cost_per_contract_usd: .05, llm_calls: 0, drex_decisions_per_contract: 310, reliability: rel }),
    arm("C Drex-first cascade", { contracts: 82, failed_contracts: 0, accuracy: .94, macro_f1: .8, micro_f1: .83, "evidence_hit@1": .6, "evidence_hit@3": .77, latency_p50_ms: 9100, latency_p95_ms: 19000, cost_per_contract_usd: .11, llm_calls: 31, share_decided_by_drex: .84 }),
  ];
  const catf1 = {}; CATS.forEach(c => catf1[c] = +(.45 + rnd() * .5).toFixed(2));
  summary[1].per_category_f1 = catf1;

  const ledger = [];
  const t0 = Date.now() / 1000 - 600;
  contracts.slice(0, 2).forEach(ct => {
    for (let i = 0; i < 6; i++) ledger.push({ ts: t0 + ledger.length, arm: "drex", contract: ct.title, unit: `chunk${i}`, model: "drex-v2.0", latency_ms: 150 + Math.round(rnd() * 120), input_tokens: 900 + Math.round(rnd() * 400), n_questions: 20 });
  });
  ledger.push({ ts: t0 + 99, arm: "cascade", contract: contracts[0].title, unit: "uncertain:Uncapped Liability", model: "(llm baseline)", latency_ms: 2100, input_tokens: 4200, output_tokens: 160 });

  return { sample: true, theta: 0.5, tau: 0.9, drex_model: "drex-v2.0 (sample)", llm_model: "(sample)", categories: CATS, contracts, summary, ledger };
})();
