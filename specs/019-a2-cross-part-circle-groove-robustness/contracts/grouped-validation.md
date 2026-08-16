# Contract: Grouped Robustness Validation

根因表CSV：

    sample_id,failure_family,selection_authority,selection_provenance
    normal:part-008,sparse-circle-boundary,algorithm-owner,readonly-diagnosis-YYYYMMDD

根因表不替代009分组权威。

分折CLI输入confirmed grouping、根因表和009封存lock，输出a2-robustness-fold-plan/1。
相同sample或SHA跨purpose时，必须在读取图像或results前拒绝。

只读审计CLI输入上述三项和历史results.jsonl，输出audit.json、groups.csv和annotation-queue.csv。
工具先建立目标SHA集，只解析目标且非封存JSONL行。报告固定accuracyEvaluated=false且
sealedRecordsParsed=0。
