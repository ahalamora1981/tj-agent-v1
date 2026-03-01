-- sample_fts_memory.sql

-- 1. 创建使用 FTS5 引擎的虚拟表，专门用于高速全文检索
-- id 是不需要分词索引的字段 (UNINDEXED)
CREATE VIRTUAL TABLE IF NOT EXISTS prompt_memory USING fts5(
    id UNINDEXED,
    category,       -- 例如 'data_science', 'coding', 'finance'
    intent,         -- 意图描述，例如 '数据清洗脚本', 'ETF数据分析'
    prompt_template -- 具体的 Prompt 模板内容
);

-- 2. 插入测试数据的示例
INSERT INTO prompt_memory (id, category, intent, prompt_template) 
VALUES ('p_001', 'finance', 'A股ETF分析', '请帮我分析以下A股ETF的近期走势：{{ticker}}');

-- 3. 执行传统关键字匹配搜索的 SQL 示例
-- 利用 MATCH 语法，并按相关性打分 (rank) 排序
SELECT 
    id, 
    intent, 
    prompt_template, 
    rank 
FROM prompt_memory 
WHERE prompt_memory MATCH 'ETF 分析' 
ORDER BY rank 
LIMIT 3;