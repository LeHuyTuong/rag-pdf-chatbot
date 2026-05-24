# Literature Review Draft: Vietnamese Text Retrieval Embeddings Across Domains

## 1. Introduction

This draft addresses whether Vietnamese-specific embedding models outperform multilingual embedding
models for Vietnamese retrieval in news, legal, medical, and history domains. It is generated from
the screened records and evidence excerpts in `data/literature_matrix.csv`. It deliberately does
not assert a model winner until metric values and experimental comparability are manually verified
against full text. Evidence inventory: [Nguyen2026_P3C1AF4AB6A; P3C1AF4AB6A]; [Dang2026_P452D138CC5; P452D138CC5]; [Pham2026_P0B2625DE40; P0B2625DE40]; [Le2025_P0361B383C0; P0361B383C0]; [Enevoldsen2025_P048819CB98; P048819CB98]; [Nguyen2025_P06356296BC; P06356296BC]; [Nguyen2025_P761355BB9F; P761355BB9F]; [Zhang2024_P9F643D4414; P9F643D4414]; [Ba2024_P1E2585E7BA; P1E2585E7BA]; [Duc2024_P5182A0032F; P5182A0032F]; [Wang2024_P47282B6184; P47282B6184]; [Tien2024_PC628139497; PC628139497]; [Bac2024_P7340A11077; P7340A11077]; [Pham2022_PD63FF37D74; PD63FF37D74]; [Vu2011_PF27F8656D0; PF27F8656D0].

## 2. Background On Multilingual And Vietnamese-Specific Embedding Models

The current core set was selected because its retrievable metadata or open-access text identifies
Vietnamese/multilingual embedding, retrieval, or benchmark relevance. The table reports detected
terms only; a blank cell does not establish absence in the paper.

| ID | Paper | Detected Domain | Detected Models | Detected Metrics | Evidence Key |
| --- | --- | --- | --- | --- | --- |
| P3C1AF4AB6A | Which Works Best for Vietnamese? A Practical Study of Information Retrieval Methods across Domains | legal; medical | BM25 | nDCG; Recall; MRR; Precision | [Nguyen2026_P3C1AF4AB6A; P3C1AF4AB6A] |
| P452D138CC5 | ViRanker: A BGE-M3 & Blockwise Parallel Transformer Cross-Encoder for Vietnamese Reranking | general | BGE-M3; XLM-R; PhoBERT; mBERT; BM25 | nDCG; MRR; Accuracy | [Dang2026_P452D138CC5; P452D138CC5] |
| P0B2625DE40 | VN-MTEB: Vietnamese Massive Text Embedding Benchmark | general | LaBSE; PhoBERT | Not automatically identified | [Pham2026_P0B2625DE40; P0B2625DE40] |
| P0361B383C0 | Optimizing Legal Document Retrieval in Vietnamese with Semi-Hard Negative Mining | legal | BGE-M3; Sentence-BERT; BM25 | MRR; Accuracy; Precision | [Le2025_P0361B383C0; P0361B383C0] |
| P048819CB98 | MMTEB: Massive Multilingual Text Embedding Benchmark | general | multilingual-e5; E5; BM25 | Not automatically identified | [Enevoldsen2025_P048819CB98; P048819CB98] |
| P06356296BC | Improving Vietnamese-English Cross-Lingual Retrieval for Legal and General Domains | legal | BGE-M3 | nDCG; Recall; MRR; MAP | [Nguyen2025_P06356296BC; P06356296BC] |
| P761355BB9F | Advancing Vietnamese Information Retrieval with Learning Objective and Benchmark | general | DPR; BM25 | MAP; Accuracy; Precision | [Nguyen2025_P761355BB9F; P761355BB9F] |
| P9F643D4414 | mGTE: Generalized Long-Context Text Representation and Reranking Models for Multilingual Text Retrieval | general | BGE-M3; multilingual-e5; E5; XLM-R; mBERT; BM25 | nDCG; Recall; MAP; Precision | [Zhang2024_P9F643D4414; P9F643D4414] |
| P1E2585E7BA | Vietnamese Legal Information Retrieval in Question-Answering System | legal | BM25 | Accuracy; Precision | [Ba2024_P1E2585E7BA; P1E2585E7BA] |
| P5182A0032F | Towards Comprehensive Vietnamese Retrieval-Augmented Generation and Large Language Models | general | PhoBERT; Sentence-BERT | MRR; Accuracy | [Duc2024_P5182A0032F; P5182A0032F] |
| P47282B6184 | Multilingual E5 Text Embeddings: A Technical Report | general | multilingual-e5; E5; LaBSE; XLM-R; Sentence-BERT; DPR; BM25 | nDCG | [Wang2024_P47282B6184; P47282B6184] |
| PC628139497 | Improving Vietnamese Legal Document Retrieval using Synthetic Data | legal | BGE-M3; PhoBERT; Sentence-BERT; BM25 | Accuracy | [Tien2024_PC628139497; PC628139497] |
| P7340A11077 | Enhancing retrieval performance of embedding models via fine-tuning on synthetic data in RAG chatbot for Vietnamese military science domain | history | Not automatically identified | MAP | [Bac2024_P7340A11077; P7340A11077] |
| PD63FF37D74 | Multi-stage Information Retrieval for Vietnamese Legal Texts | legal | XLM-R; PhoBERT; Sentence-BERT; mBERT; BM25 | Not automatically identified | [Pham2022_PD63FF37D74; PD63FF37D74] |
| PF27F8656D0 | A Vietnamese information retrieval system for product-price | general | Not automatically identified | Recall; Accuracy; Precision | [Vu2011_PF27F8656D0; PF27F8656D0] |

## 3. Vietnamese Text Retrieval Benchmarks And Datasets

Dataset names extracted during screening should be checked against dataset definitions, splits, and
Vietnamese coverage before benchmark design. Current dataset-term evidence is linked below:

| Paper ID | Detected Dataset Terms | Citation |
| --- | --- | --- |
| P3C1AF4AB6A | BEIR; ALQAC | [Nguyen2026_P3C1AF4AB6A; P3C1AF4AB6A] |
| P452D138CC5 | mMARCO | [Dang2026_P452D138CC5; P452D138CC5] |
| P0B2625DE40 | MTEB; VN-MTEB; BEIR | [Pham2026_P0B2625DE40; P0B2625DE40] |
| P0361B383C0 | No controlled-vocabulary match | [Le2025_P0361B383C0; P0361B383C0] |
| P048819CB98 | MTEB; MMTEB | [Enevoldsen2025_P048819CB98; P048819CB98] |
| P06356296BC | PhoMT | [Nguyen2025_P06356296BC; P06356296BC] |
| P761355BB9F | MTEB; BEIR | [Nguyen2025_P761355BB9F; P761355BB9F] |
| P9F643D4414 | MTEB; MIRACL; MLDR; BEIR | [Zhang2024_P9F643D4414; P9F643D4414] |
| P1E2585E7BA | No controlled-vocabulary match | [Ba2024_P1E2585E7BA; P1E2585E7BA] |
| P5182A0032F | No controlled-vocabulary match | [Duc2024_P5182A0032F; P5182A0032F] |
| P47282B6184 | MTEB; MIRACL; Mr. TyDi | [Wang2024_P47282B6184; P47282B6184] |
| PC628139497 | BEIR | [Tien2024_PC628139497; PC628139497] |
| P7340A11077 | No controlled-vocabulary match | [Bac2024_P7340A11077; P7340A11077] |
| PD63FF37D74 | No controlled-vocabulary match | [Pham2022_PD63FF37D74; PD63FF37D74] |
| PF27F8656D0 | No controlled-vocabulary match | [Vu2011_PF27F8656D0; PF27F8656D0] |

## 4. Model Comparison Themes

### 4.1 Multilingual Embedding Models

The evidence matrix identifies multilingual-model terms for manual extraction of training scope,
language coverage, and reported retrieval results. The relevant source-linked records are:
[Dang2026_P452D138CC5; P452D138CC5]; [Pham2026_P0B2625DE40; P0B2625DE40]; [Le2025_P0361B383C0; P0361B383C0]; [Enevoldsen2025_P048819CB98; P048819CB98]; [Nguyen2025_P06356296BC; P06356296BC]; [Zhang2024_P9F643D4414; P9F643D4414]; [Wang2024_P47282B6184; P47282B6184]; [Tien2024_PC628139497; PC628139497]; [Pham2022_PD63FF37D74; PD63FF37D74]

### 4.2 Vietnamese-Specific Embedding Models

Records tagged with Vietnamese/PhoBERT or Vietnamese retrieval terminology provide the starting
point for identifying monolingual baselines. A valid comparative claim requires matched corpora,
query sets, and metrics, which are not inferred automatically here. Sources:
[Nguyen2026_P3C1AF4AB6A; P3C1AF4AB6A]; [Dang2026_P452D138CC5; P452D138CC5]; [Pham2026_P0B2625DE40; P0B2625DE40]; [Le2025_P0361B383C0; P0361B383C0]; [Nguyen2025_P06356296BC; P06356296BC]; [Nguyen2025_P761355BB9F; P761355BB9F]; [Ba2024_P1E2585E7BA; P1E2585E7BA]; [Duc2024_P5182A0032F; P5182A0032F]; [Tien2024_PC628139497; PC628139497]; [Bac2024_P7340A11077; P7340A11077]; [Pham2022_PD63FF37D74; PD63FF37D74]; [Vu2011_PF27F8656D0; PF27F8656D0]

### 4.3 Domain-Specific Retrieval: News, Legal, Medical, History

- **News**: 0 core record(s) tagged by metadata/full-text term detection. No source coded in the current matrix.
- **Legal**: 6 core record(s) tagged by metadata/full-text term detection. [Nguyen2026_P3C1AF4AB6A; P3C1AF4AB6A]; [Le2025_P0361B383C0; P0361B383C0]; [Nguyen2025_P06356296BC; P06356296BC]; [Ba2024_P1E2585E7BA; P1E2585E7BA]; [Tien2024_PC628139497; PC628139497]; [Pham2022_PD63FF37D74; PD63FF37D74]
- **Medical**: 1 core record(s) tagged by metadata/full-text term detection. [Nguyen2026_P3C1AF4AB6A; P3C1AF4AB6A]
- **History**: 1 core record(s) tagged by metadata/full-text term detection. [Bac2024_P7340A11077; P7340A11077]

These counts are classifications in this screening dataset, not findings about retrieval quality.

## 5. Evaluation Metrics Used In Prior Work

Metric mentions extracted from metadata or available PDF text are listed for full-text coding.
Performance numbers are intentionally not transcribed without table-level verification.

| Paper ID | Metric Terms Located | Coding Note | Citation |
| --- | --- | --- | --- |
| P3C1AF4AB6A | nDCG; Recall; MRR; Precision | Verify definitions and values in source text. | [Nguyen2026_P3C1AF4AB6A; P3C1AF4AB6A] |
| P452D138CC5 | nDCG; MRR; Accuracy | Verify definitions and values in source text. | [Dang2026_P452D138CC5; P452D138CC5] |
| P0361B383C0 | MRR; Accuracy; Precision | Verify definitions and values in source text. | [Le2025_P0361B383C0; P0361B383C0] |
| P06356296BC | nDCG; Recall; MRR; MAP | Verify definitions and values in source text. | [Nguyen2025_P06356296BC; P06356296BC] |
| P761355BB9F | MAP; Accuracy; Precision | Verify definitions and values in source text. | [Nguyen2025_P761355BB9F; P761355BB9F] |
| P9F643D4414 | nDCG; Recall; MAP; Precision | Verify definitions and values in source text. | [Zhang2024_P9F643D4414; P9F643D4414] |
| P1E2585E7BA | Accuracy; Precision | Verify definitions and values in source text. | [Ba2024_P1E2585E7BA; P1E2585E7BA] |
| P5182A0032F | MRR; Accuracy | Verify definitions and values in source text. | [Duc2024_P5182A0032F; P5182A0032F] |
| P47282B6184 | nDCG | Verify definitions and values in source text. | [Wang2024_P47282B6184; P47282B6184] |
| PC628139497 | Accuracy | Verify definitions and values in source text. | [Tien2024_PC628139497; PC628139497] |
| P7340A11077 | MAP | Verify definitions and values in source text. | [Bac2024_P7340A11077; P7340A11077] |
| PF27F8656D0 | Recall; Accuracy; Precision | Verify definitions and values in source text. | [Vu2011_PF27F8656D0; PF27F8656D0] |

## 6. Research Gaps

The present automated matrix has not coded a validated, controlled head-to-head result across all
four target domains. That is a proposed review/benchmark question rather than a claim that no such
study exists. The immediate gap-coding task is to verify each core paper's dataset domain,
Vietnamese-language composition, model comparators, metric definitions, and numerical results.
Evidence base for this coding task: [Nguyen2026_P3C1AF4AB6A; P3C1AF4AB6A]; [Dang2026_P452D138CC5; P452D138CC5]; [Pham2026_P0B2625DE40; P0B2625DE40]; [Le2025_P0361B383C0; P0361B383C0]; [Enevoldsen2025_P048819CB98; P048819CB98]; [Nguyen2025_P06356296BC; P06356296BC]; [Nguyen2025_P761355BB9F; P761355BB9F]; [Zhang2024_P9F643D4414; P9F643D4414]; [Ba2024_P1E2585E7BA; P1E2585E7BA]; [Duc2024_P5182A0032F; P5182A0032F]; [Wang2024_P47282B6184; P47282B6184]; [Tien2024_PC628139497; PC628139497]; [Bac2024_P7340A11077; P7340A11077]; [Pham2022_PD63FF37D74; PD63FF37D74]; [Vu2011_PF27F8656D0; PF27F8656D0].

## 7. Proposed Research Direction

A subsequent empirical benchmark should compare the same Vietnamese query-document relevance sets
with multilingual and Vietnamese-specific encoders, stratified by news, legal, medical, and
history domains. It should report nDCG@10, Recall@10, MRR, MAP, latency, model size, and deployment
cost, and should preregister significance testing before interpreting H0/H1.

## 8. Conclusion

This reproducible screening run supplies a traceable candidate set, legally acquired open-access
full texts where available, and evidence excerpts for manual synthesis. Comparative conclusions are
deferred until numerical evidence is verified in the cited source papers.

## 9. References

- Long S. T. Nguyen; Tho Quan (2026). *Which Works Best for Vietnamese? A Practical Study of Information Retrieval Methods across Domains*. EACL (Findings) 2026. Source record: P3C1AF4AB6A.
- Phuong-Nam Dang; Kieu-Linh Nguyen; Thanh-Hieu Pham (2026). *ViRanker: A BGE-M3 & Blockwise Parallel Transformer Cross-Encoder for Vietnamese Reranking*. Lecture Notes in Networks and Systems. DOI: https://doi.org/10.1007/978-3-032-18316-3_34. Source record: P452D138CC5.
- Loc Pham; Tung Luu; Thu Vo; Minh Nguyen; Viet Hoang (2026). *VN-MTEB: Vietnamese Massive Text Embedding Benchmark*. Conference of the European Chapter of the Association for Computational Linguistics. DOI: https://doi.org/10.18653/v1/2026.findings-eacl.86. Source record: P0B2625DE40.
- V. Le; Duc-Vu Nguyen; Kiet Van Nguyen; N. Nguyen (2025). *Optimizing Legal Document Retrieval in Vietnamese with Semi-Hard Negative Mining*. International Conference on Computational Collective Intelligence. DOI: https://doi.org/10.48550/arxiv.2507.14619. Source record: P0361B383C0.
- Kenneth Enevoldsen; Isaac Chung; Imene Kerboua; Márton Kardos; Ashwin Mathur; David Stap; Jay Gala; Wissam Siblini; Dominik Krzemiński; Genta Indra Winata; Saba Sturua; Saiteja Utpala; Mathieu Ciancone; Marion Schaeffer; Sequeira, Gabriel; D. Misra; Shreeya Singh Dhakal; Jonathan Hvithamar Rystrøm; Roman Solomatin; Ömer Veysel Çağatan; Akash Kundu; Martin Bernstorff; Shitao Xiao; Akshita Sukhlecha; Bhavish Pahwa; Rafał Poświata; Kranthi Kiran GV; Shawon Ashraf; Daniel Auras; Björn Plüster; Jan Philipp Harries; Loïc Magne; Isabelle Mohr; Mariya Hendriksen; Dawei Zhu; Hippolyte Gisserot-Boukhlef; Tom Aarsen; Jan Kostkan; Konrad Wojtasik; Taemin Lee; Marek Šuppa; Crystina Zhang; Roberta Rocca; Mohammed Hamdy; Andrianos Michail; John Yang; Manuel Faysse; Aleksei Vatolin; Nandan Thakur; Manan Dey; Dipam Vasani; Pranjal A. Chitale; Simone Tedeschi; Nguyen Dinh Tai; Artem Snegirev; Michael Günther; Mengzhou Xia; Weijia Shi; Xing Han Lù; Jordan Clive; Krishnakumar, Gayatri; Maksimova, Anna; Silvan Wehrli; Maria Tikhonova; Henil Shalin Panchal; Aleksandr Abramov; Malte Ostendorff; Zheng Liu; Simon Clematide; Lester James V. Miranda; Alena Fenogenova; Guangyu Song; Ruqiya Bin Safi; Wen-Ding Li; Borghini, Alessia; Federico Cassano; Hongjin Su; Jimmy Lin; H. W. Yen; Lasse Hansen; Sara Hooker; Chenghao Xiao; Vaibhav Adlakha; Orion Weller; Siva Reddy; Niklas Muennighoff (2025). *MMTEB: Massive Multilingual Text Embedding Benchmark*. arXiv.org. DOI: https://doi.org/10.48550/arxiv.2502.13595. Source record: P048819CB98.
- Toan N. Nguyen; Nam Le Hai; Nguyễn Văn Hiệu; Dai An Nguyen; Linh Ngo Van; Thien Huu Nguyen; Dinh Viet Sang (2025). *Improving Vietnamese-English Cross-Lingual Retrieval for Legal and General Domains*. North American Chapter of the Association for Computational Linguistics. DOI: https://doi.org/10.18653/v1/2025.naacl-short.12. Source record: P06356296BC.
- Phu-Vinh Nguyen; Minh-Nam Tran; Long H. B. Nguyen; D. Dien (2025). *Advancing Vietnamese Information Retrieval with Learning Objective and Benchmark*. Pacific Asia Conference on Language, Information and Computation. DOI: https://doi.org/10.48550/arxiv.2503.07470. Source record: P761355BB9F.
- Xintong Zhang; Yanzhao Zhang; Dingkun Long; Wen Xie; Ziqi Dai; Jialong Tang; Huan Lin; Baosong Yang; Pengjun Xie; Fei Huang; Meishan Zhang; Wenjie Li; Min Zhang (2024). *mGTE: Generalized Long-Context Text Representation and Reranking Models for Multilingual Text Retrieval*. Conference on Empirical Methods in Natural Language Processing. DOI: https://doi.org/10.18653/v1/2024.emnlp-industry.103. Source record: P9F643D4414.
- Thiem Nguyen Ba; Vinh Doan The; Tung Pham Quang; Van, Toan Tran (2024). *Vietnamese Legal Information Retrieval in Question-Answering System*. arXiv (Cornell University). DOI: https://doi.org/10.48550/arxiv.2409.13699. Source record: P1E2585E7BA.
- Nguyen Quang Đuc; Le Hai Son; Nguyen Duc Nhan; Nguyen Dich Nhat Minh; Lê Thanh Hương; Dinh Viet Sang (2024). *Towards Comprehensive Vietnamese Retrieval-Augmented Generation and Large Language Models*. arXiv (Cornell University). DOI: https://doi.org/10.48550/arxiv.2403.01616. Source record: P5182A0032F.
- Liang Wang; Nan Yang; Xiaolong Huang; Linjun Yang; Rangan Majumder; Furu Wei (2024). *Multilingual E5 Text Embeddings: A Technical Report*. arXiv.org. DOI: https://doi.org/10.48550/arxiv.2402.05672. Source record: P47282B6184.
- Son Pham Tien; Hieu Nguyen Doan; A. D’Aì; Viet, Sang Dinh (2024). *Improving Vietnamese Legal Document Retrieval using Synthetic Data*. arXiv (Cornell University). DOI: https://doi.org/10.48550/arxiv.2412.00657. Source record: PC628139497.
- Nguyen Xuan Bac; Luu Van Sang; Nguyen Duc Vuong; Luong Quoc Le; Dang Duc Thinh (2024). *Enhancing retrieval performance of embedding models via fine-tuning on synthetic data in RAG chatbot for Vietnamese military science domain*. Journal of Military Science and Technology. DOI: https://doi.org/10.54939/1859-1043.j.mst.99.2024.109-118. Source record: P7340A11077.
- Nhat-Minh Pham; Ha-Thanh Nguyen; Trong-Hop Do (2022). *Multi-stage Information Retrieval for Vietnamese Legal Texts*. arXiv (Cornell University). DOI: https://doi.org/10.48550/arxiv.2209.14494. Source record: PD63FF37D74.
- Tien-Thanh Vu; Dat Quoc Nguyen (2011). *A Vietnamese information retrieval system for product-price*. 2011 IEEE International Conference on Granular Computing. DOI: https://doi.org/10.1109/grc.2011.6122681. Source record: PF27F8656D0.
