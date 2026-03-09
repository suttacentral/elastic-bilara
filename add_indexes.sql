-- PostgreSQL 性能优化索引脚本
-- 执行方式: docker exec -i bilara-db psql -U bilara-db -d bilara-db < add_indexes.sql

-- 1. 为 notifications 表添加索引
-- 检查索引是否已存在，避免重复创建
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'notifications'
        AND indexname = 'ix_notifications_github_id'
    ) THEN
        CREATE INDEX CONCURRENTLY ix_notifications_github_id
        ON notifications(github_id);
        RAISE NOTICE 'Created index: ix_notifications_github_id';
    ELSE
        RAISE NOTICE 'Index already exists: ix_notifications_github_id';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'notifications'
        AND indexname = 'ix_notifications_commit_id'
    ) THEN
        CREATE INDEX CONCURRENTLY ix_notifications_commit_id
        ON notifications(commit_id);
        RAISE NOTICE 'Created index: ix_notifications_commit_id';
    ELSE
        RAISE NOTICE 'Index already exists: ix_notifications_commit_id';
    END IF;
END $$;

-- 2. 为 remarks 表添加索引
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'remarks'
        AND indexname = 'idx_source_file_path'
    ) THEN
        CREATE INDEX CONCURRENTLY idx_source_file_path
        ON remarks(source_file_path);
        RAISE NOTICE 'Created index: idx_source_file_path';
    ELSE
        RAISE NOTICE 'Index already exists: idx_source_file_path';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'remarks'
        AND indexname = 'idx_segment_id'
    ) THEN
        CREATE INDEX CONCURRENTLY idx_segment_id
        ON remarks(segment_id);
        RAISE NOTICE 'Created index: idx_segment_id';
    ELSE
        RAISE NOTICE 'Index already exists: idx_segment_id';
    END IF;
END $$;

-- 3. 确保 user_preferences 表的 github_id 有索引
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'user_preferences'
        AND indexname like '%github_id%'
    ) THEN
        CREATE INDEX CONCURRENTLY ix_user_preferences_github_id
        ON user_preferences(github_id);
        RAISE NOTICE 'Created index: ix_user_preferences_github_id';
    ELSE
        RAISE NOTICE 'Index already exists for user_preferences.github_id';
    END IF;
END $$;

-- 4. 验证索引创建
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN ('notifications', 'remarks', 'user_preferences')
ORDER BY tablename, indexname;

-- 5. 分析表以更新统计信息
ANALYZE notifications;
ANALYZE remarks;
ANALYZE user_preferences;
ANALYZE translation_progress;

-- 完成提示
SELECT 'Indexes created successfully! Run VACUUM ANALYZE to optimize.' as status;
