"""
从 HTML 页面解析计费数据
"""
import re
import httpx
from bs4 import BeautifulSoup


async def fetch_billing_data():
    """从 HTML 页面获取计费数据"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://154.92.5.72:8080/keys")

            if response.status_code != 200:
                return None

            html_content = response.text

            # 使用 BeautifulSoup 解析 HTML
            soup = BeautifulSoup(html_content, 'html.parser')

            # 查找包含使用量信息的元素
            # 根据你提供的截图，使用量信息格式为：
            # 今日: $0.0000
            # 近30天: $48.2567

            billing_data = []

            # 方法1: 查找所有包含"今日"和"近30天"的文本
            text_content = soup.get_text()

            # 提取所有"今日: $数字"的模式
            today_matches = re.findall(r'今日[：:]\s*\$?([\d.]+)', text_content)
            last30_matches = re.findall(r'近30天[：:]\s*\$?([\d.]+)', text_content)

            # 计算总和
            today_total = sum(float(x) for x in today_matches)
            last30_total = sum(float(x) for x in last30_matches)

            return {
                'today': round(today_total, 4),
                'last30days': round(last30_total, 4),
                'keys_count': len(today_matches)
            }

    except Exception as e:
        print(f"解析计费数据失败: {e}")
        return None


if __name__ == '__main__':
    import asyncio

    async def test():
        data = await fetch_billing_data()
        print(f"计费数据: {data}")

    asyncio.run(test())
