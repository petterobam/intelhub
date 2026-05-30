-- 001: reports 表添加 summary_path 列
-- 已在线上手动执行过，此脚本作为示例保留
ALTER TABLE reports ADD COLUMN summary_path VARCHAR(512);
