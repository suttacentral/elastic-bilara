#!/bin/bash

# PostgreSQL 性能优化应用脚本
# 用途：应用数据库索引优化和配置更新

set -e  # 遇到错误立即退出

echo "=========================================="
echo "PostgreSQL 性能优化应用"
echo "=========================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查 Docker 是否运行
if ! docker ps >/dev/null 2>&1; then
    echo -e "${RED}错误: Docker 未运行${NC}"
    exit 1
fi

# 读取数据库配置
if [ -f .env ]; then
    source .env
else
    echo -e "${RED}错误: .env 文件不存在${NC}"
    exit 1
fi

DB_CONTAINER="${1:-bilara-db}"
DB_NAME="${POSTGRESQL_DATABASE:-bilara-db}"
DB_USER="${POSTGRESQL_USERNAME:-bilara-db}"

echo "数据库容器: $DB_CONTAINER"
echo "数据库名称: $DB_NAME"
echo "数据库用户: $DB_USER"
echo ""

# 检查容器是否存在
if ! docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
    echo -e "${RED}错误: 容器 $DB_CONTAINER 不存在或未运行${NC}"
    echo "当前运行的容器:"
    docker ps --format "table {{.Names}}\t{{.Status}}"
    exit 1
fi

# 步骤 1: 备份当前索引状态
echo -e "${YELLOW}步骤 1/4: 备份当前索引状态...${NC}"
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "
    SELECT schemaname, tablename, indexname
    FROM pg_indexes
    WHERE schemaname = 'public'
    ORDER BY tablename, indexname;
" > "indexes_backup_$(date +%Y%m%d_%H%M%S).txt"
echo -e "${GREEN}✓ 索引状态已备份${NC}"
echo ""

# 步骤 2: 应用索引
echo -e "${YELLOW}步骤 2/4: 创建性能索引...${NC}"
if [ -f "add_indexes.sql" ]; then
    docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" < add_indexes.sql
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ 索引创建成功${NC}"
    else
        echo -e "${RED}✗ 索引创建失败${NC}"
        exit 1
    fi
else
    echo -e "${RED}错误: add_indexes.sql 文件不存在${NC}"
    exit 1
fi
echo ""

# 步骤 3: 优化数据库
echo -e "${YELLOW}步骤 3/4: 运行 VACUUM ANALYZE 优化数据库...${NC}"
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "VACUUM ANALYZE;"
echo -e "${GREEN}✓ 数据库优化完成${NC}"
echo ""

# 步骤 4: 验证索引
echo -e "${YELLOW}步骤 4/4: 验证索引创建...${NC}"
echo "当前索引列表:"
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "
    SELECT
        tablename,
        indexname,
        pg_size_pretty(pg_relation_size(indexrelid)) as size
    FROM pg_stat_user_indexes
    WHERE schemaname = 'public'
      AND tablename IN ('notifications', 'remarks', 'user_preferences', 'translation_progress')
    ORDER BY tablename, indexname;
"
echo ""

# 显示表大小
echo "表大小统计:"
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "
    SELECT
        tablename,
        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size
    FROM pg_tables
    WHERE schemaname = 'public'
    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"
echo ""

echo -e "${GREEN}=========================================="
echo "优化完成！"
echo "==========================================${NC}"
echo ""
echo "后续步骤:"
echo "1. 重启后端服务以应用配置更改:"
echo "   docker-compose restart bilara-backend worker_pr worker_commit worker_sync"
echo ""
echo "2. 监控数据库 CPU 使用率:"
echo "   docker stats $DB_CONTAINER"
echo ""
echo "3. 查看慢查询 (10-30分钟后):"
echo "   docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c \\"
echo "   \"SELECT query, calls, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;\\"
echo ""
