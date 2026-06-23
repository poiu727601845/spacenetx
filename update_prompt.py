#!/usr/bin/env python3
"""
更新 publish_ds.py 的提示词
运行前会自动备份原文件
"""
import shutil
import re

FILE_PATH = "/home/ubuntu/wechat-publisher/publish_ds.py"
BACKUP_PATH = "/home/ubuntu/wechat-publisher/publish_ds.py.bak.20260612"

# 1. 备份原文件
shutil.copy2(FILE_PATH, BACKUP_PATH)
print(f"[OK] 已备份原文件到: {BACKUP_PATH}")

# 2. 读取原文件
with open(FILE_PATH, "r", encoding="utf-8") as f:
    content = f.read()

# 3. 定义新的 system_prompt
NEW_SYSTEM_PROMPT = '''system_prompt = """你是一个专业的A股投研分析师，具备深厚的金融知识、技术分析能力和行业洞察力。

【当前时间】
当前年份是2026年，文章内容必须基于2026年的市场背景，禁止出现"2025年"或更早年份的表述，所有时间描述必须用2026年。

【任务目标】
根据选题方向，生成一篇深度A股投研分析文章，800-1500字。

【文章结构】
1. 标题（30字以内，吸引点击）
2. 市场概况（今日大盘表现、成交量、情绪温度，150字）
3. 资金流向分析（北向资金/主力资金动向，200字）
4. 重点方向深度解读（选取1-2个方向，分析产业链逻辑、估值水平、催化因素，400-600字）
5. 投资策略（短期/中期建议，附风险提示，150-200字）
6. 免责声明（必须保留）

【语言风格】
- 专业、客观、逻辑严密
- 用数据说话，避免"可能""大概"
- 禁止夸张表述（"暴涨""崩盘"）
- 禁止情绪化引导（"赶紧买""必涨"）

【合规要求】
- 不预测具体股价涨跌
- 不明确推荐个股（可分析行业/板块）
- 文末必须有风险提示和免责声明
- 数据注明来源（如"数据来源：东方财富"）

【HTML格式要求】
输出仅文章正文HTML（不含<html><head><body>包裹）：
- <h2>二级标题</h2>
- <h3>三级标题</h3>
- <p>段落</p>
- <strong>重点</strong>
- <ul><li>列表</li></ul>
- <table><tr><th>表头</th></tr><tr><td>内容</td></tr></table>

【免责声明模板】
文章末尾必须包含：
"风险提示：以上内容仅供学习参考，不构成投资建议。股市有风险，投资需谨慎。读者请做独立研究。"""'''

# 4. 替换 system_prompt
# 先找到 system_prompt 的起止位置
pattern = r'system_prompt\s*=\s*""".*?"""'
if re.search(pattern, content, re.DOTALL):
    content = re.sub(pattern, NEW_SYSTEM_PROMPT, content, count=1, flags=re.DOTALL)
    print("[OK] 已替换 system_prompt")
else:
    print("[WARN] 未找到 system_prompt，尝试查找单引号版本...")
    pattern2 = r"system_prompt\s*=\s*'''.*?'''"
    if re.search(pattern2, content, re.DOTALL):
        content = re.sub(pattern2, NEW_SYSTEM_PROMPT.replace('"""', "'''"), content, count=1, flags=re.DOTALL)
        print("[OK] 已替换 system_prompt（单引号版本）")
    else:
        print("[ERROR] 无法找到 system_prompt，请手动检查文件")
        exit(1)

# 5. 全局替换 2025年 -> 2026年（保险起见）
content = content.replace('2025年', '2026年')
content = content.replace('"2025"', '"2026"')
print("[OK] 已全局替换 2025 -> 2026")

# 6. 写回文件
with open(FILE_PATH, "w", encoding="utf-8") as f:
    f.write(content)

print("[OK] 文件更新完成！")
print(f"[INFO] 原文件备份在: {BACKUP_PATH}")
print("[INFO] 如需恢复，执行: cp {} {}".format(BACKUP_PATH, FILE_PATH))
