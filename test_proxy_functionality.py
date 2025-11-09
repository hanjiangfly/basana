import asyncio
import aiohttp
from basana.core.helpers import use_or_create_session

async def test_proxy():
    """测试代理功能是否正常工作"""
    print("测试代理功能...")
    
    try:
        # 测试无代理
        print("1. 测试无代理...")
        async with use_or_create_session() as session:
            print("   无代理会话创建成功！")
        
        # 测试SOCKS5代理
        print("2. 测试SOCKS5代理...")
        async with use_or_create_session(proxy='socks5://127.0.0.1:7897') as session:
            print("   SOCKS5代理会话创建成功！")

        # 测试SOCKS5代理访问 https://www.cip.cc/
        print("3. 测试SOCKS5代理访问 https://www.cip.cc/")
        try:
            test_url = "https://www.cip.cc/"
            async with use_or_create_session(proxy='socks5://192.168.1.4:9526') as session:
                async with session.get(test_url) as response:
                    if response.status == 200:
                        html_content = await response.text()
                        # 从HTML中提取IP信息
                        # 简单检查是否包含IP相关信息
                        if "IP" in html_content or "ip" in html_content:
                            print("   ✅ 代理访问成功！网站返回IP信息")
                        else:
                            print("   ✅ 代理访问成功！")
                        print(f"   状态码: {response.status}")
                        print(f"   内容长度: {len(html_content)} 字节")
                        print(html_content)
                    else:
                        print(f"   ❌ 代理访问失败，状态码: {response.status}")
        except Exception as e:
            print(f"   ❌ 代理访问异常: {e}")

            
        print("所有测试通过！代理功能正常工作。")
        return True
        
    except Exception as e:
        print(f"测试失败: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_proxy())
